"""Identify the Nov20 empty-box response and train candidates; never imports GPIO."""
import argparse
from bisect import bisect_right
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Code_HopAp_Demo'))
import phan_tich_reward as measured
import hoc_vung_on_dinh as base
import hoc_action_keo_dai as temporal


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def group_at(session, t):
    samples = session['samples']
    i = bisect_right([s['t'] for s in samples], t)-1
    match = re.match(r'id_(\d+)_', samples[max(0,i)]['phase'])
    return int(match[1]) if match else 0


def fit(rows, tau):
    center = 37.5
    x = np.array([measured.features(r['temperature'], r['previous_delta'], r['memory'], r['f'], center, .875) for r in rows])
    y = np.array([r['delta'] for r in rows])
    coef, _, rank, _ = np.linalg.lstsq(x,y,rcond=None)
    if rank != 6:
        raise ValueError('Rank deficient model')
    residual = y-x@coef
    return measured.ThermalModel(coef.tolist(),center,.875,tau,29.,38.125,float(np.std(residual,ddof=6)))


def metrics(model, rows, horizon):
    errors=[]; persistence=[]; endpoints=[]
    for start in range(0,len(rows)-horizon+1,horizon):
        block=rows[start:start+horizon]
        if block[-1]['t']-block[0]['t'] > (horizon-1)*5+.01:
            continue
        first=block[0];t=first['temperature'];d=first['previous_delta'];m=first['memory_before']
        for row in block:
            t,d,m=model.step(t,d,m,row['h'],row['f'])
            errors.append(t-row['next_temperature'])
            persistence.append(first['temperature']-row['next_temperature'])
        endpoints.append(t-block[-1]['next_temperature'])
    rmse=lambda v:float(np.sqrt(np.mean(np.square(v)))) if v else None
    return dict(samples=len(errors),rmse_c=rmse(errors),persistence_rmse_c=rmse(persistence),endpoint_rmse_c=rmse(endpoints))


def identify(session, out):
    # Whole response cycles 1..8 develop the model. Cycles 9/10 stay untouched
    # until tau is frozen. All preparations/probes/post-cooling in a cycle stay together.
    options=[]
    for tau in (5.,10.,25.,45.,60.):
        rows=measured.transitions(session,tau)
        for r in rows:r['group']=group_at(session,r['t'])
        rows=[r for r in rows if r['group'] and r['temperature']>=29. and r['next_temperature']<=38.125]
        folds=[]
        for g in range(1,9):
            train=[r for r in rows if r['group']<=8 and r['group']!=g]
            val=[r for r in rows if r['group']==g]
            model=fit(train,tau)
            folds.append(dict(group=g,step5=metrics(model,val,1),free30=metrics(model,val,6),free60=metrics(model,val,12)))
        score=float(np.mean([f['free30']['rmse_c'] for f in folds]))
        options.append((score,tau,rows,folds))
    _,tau,rows,folds=min(options,key=lambda o:o[0])
    development=[r for r in rows if r['group']<=8]
    frozen=fit(development,tau)
    held=[dict(group=g,step5=metrics(frozen,[r for r in rows if r['group']==g],1),
               free30=metrics(frozen,[r for r in rows if r['group']==g],6),
               free60=metrics(frozen,[r for r in rows if r['group']==g],12)) for g in (9,10)]
    cv30=float(np.mean([f['free30']['rmse_c'] for f in folds]))
    cv60=float(np.mean([f['free60']['rmse_c'] for f in folds]))
    passed=(cv30<=.15 and cv60<=.25 and all(f['free60']['rmse_c']<=.4 for f in folds+held)
            and all(f['free30']['rmse_c']<f['free30']['persistence_rmse_c'] for f in held)
            and frozen.coefficients[1]<0 and frozen.coefficients[3]>0)
    report=dict(tau_selection=[dict(tau=o[1],cv30_rmse_c=o[0]) for o in options],tau_s=tau,
        cv_folds=folds,held_out_cycles=held,cv30_rmse_c=cv30,cv60_rmse_c=cv60,
        acceptance='CV30<=0.15C; CV60<=0.25C; every cycle60<=0.4C; held30 beats persistence; heat gain positive and passive cooling negative',
        model_passed=bool(passed),development_model=asdict(frozen),
        final_model=asdict(fit(rows,tau)),final_refit_note='All cycles refit AFTER model structure validation; no independent whole-run validation yet.',
        causal_limits='One empty-box run, no ambient sensor. Closed-loop preparation is included; partial probes identify short transitions, not long-run equilibria.')
    write(out/'nhan_dang_mo_hinh.json',report)
    return report,rows


def audit(session,out):
    source=Path(session['path'])
    config=json.loads((source.parent/'cau_hinh.json').read_text(encoding='utf-8'))
    trials=config['profile']['records']
    summary=[]
    for trial in trials:
        # Preserve source trial fields and add observed sample statistics.
        item=dict(trial)
        number=trial.get('trial',trial.get('index'))
        if number is None:
            number=len(summary)+1
        samples=[r for r in session['samples'] if r['phase']==f'id_{int(number):02d}_kich_thich']
        if samples:
            times=np.array([r['t'] for r in samples]);temps=np.array([r['temperature'] for r in samples])
            weights=np.diff(times)
            item['observed_samples']=len(samples)
            item['observed_min_c']=float(temps.min());item['observed_max_c']=float(temps.max())
            item['observed_mean_c']=float(np.average(temps[:-1],weights=weights)) if weights.sum() else None
            item['observed_in_373_377_pct']=float(np.average((abs(temps[:-1]-37.5)<=.2+1e-9)*100,weights=weights)) if weights.sum() else None
        summary.append(item)
    result=dict(source_sha256=session['sha256'],sensor_ids=session['sensors'],samples=len(session['samples']),
        issues=session['issues'],trials=summary,
        note='Legacy read_log schedule warning does not apply to profile schema; actual profile.completed checked separately.',
        completed=config['profile']['completed'],hardware_exit_code=config['hardware_program_exit_code'])
    write(out/'phan_tich_du_lieu.json',result)
    return result


def training(report,rows,out,episodes):
    m=report['final_model']
    parameters=np.array(m['coefficients']+[m['center'],m['fan_center'],m['tau'],m['low'],m['high'],m['noise_sd']])
    old=json.loads((ROOT/'Code_HopAp_Demo/goi_thu_rl_20261117.json').read_text(encoding='utf8'))
    actions=np.array(old['actions'],float)
    pool=np.array([[r['temperature'],r['previous_delta'],r['memory_before'],
                    int(np.argmin(abs(actions[:,0]-r['h'])+abs(actions[:,1]-r['f'])))]
                    for r in rows if 36.6<=r['temperature']<=37.9])
    protocol=dict(episodes=episodes,seeds=[11,29,47],switch_weights=[.25,.5,1.,2.],recovery_weight=4.,
        decision_versions=['Q_5s','SMDP_inside30_outside10'],validation_seed=205001,test_seed=205101,
        model_sha256=hashlib.sha256((out/'nhan_dang_mo_hinh.json').read_bytes()).hexdigest(),
        goal='37.3..37.7C, center37.5, minimize real action changes; no mandatory deadband lock',
        acceptance='model passes; test occupancy>=95%; zero invalid/unseen; guard<=1%; 20% fewer pair changes than old Q with occupancy loss<=0.5pp',
        experimental_pilot_only=True)
    write(out/'giao_thuc_huan_luyen.json',protocol)
    validation=base.cases(pool,parameters,205001,128)
    options=[]
    for kind in ('Q_5s','SMDP_inside30_outside10'):
        for sw in (.25,.5,1.,2.):
            for seed in (11,29,47):
                if kind=='Q_5s':
                    q,v,_=base.train(parameters,actions,pool,episodes,seed,sw,4.)
                    met=base.evaluate(parameters,actions,validation,0,q,v)
                else:
                    q,v=temporal.train(parameters,actions,pool,37.5,.2,episodes,seed,sw,4.)
                    met=temporal.evaluate(parameters,actions,validation,37.5,.2,q,v)
                print(kind,sw,seed,'band',round(met['in_band_pct'],2),'lamp',round(met['lamp_changes'],2),'unknown',round(met.get('unseen_fraction',met.get('unseen_decision_fraction',0)),4),flush=True)
                options.append((dict(kind=kind,switch_weight=sw,seed=seed,validation=met),q,v))
    def rank(item):
        met=item[0]['validation']
        unknown=met.get('unseen_fraction',met.get('unseen_decision_fraction',0))
        bad=met['invalid_fraction']>0 or unknown>0 or met['guard_fraction']>.01 or met['in_band_pct']<95
        return (bad,100-met['in_band_pct']+.12*met['lamp_changes']+.04*met['fan_changes'])
    chosen,q,v=min(options,key=rank)
    write(out/'chon_tren_validation.json',chosen)
    write(out/'thu_he_so.json',[o[0] for o in options])
    test=base.cases(pool,parameters,205101,192)
    if chosen['kind']=='Q_5s':
        candidate=base.evaluate(parameters,actions,test,0,q,v)
    else:candidate=temporal.evaluate(parameters,actions,test,37.5,.2,q,v)
    oldq=np.array(old['policy']['q']);oldv=np.array(old['policy']['visits'],np.int64)
    oldmetrics=base.evaluate(parameters,actions,test,1,oldq,oldv)
    relay=base.evaluate(parameters,actions,test,2,oldq,oldv)
    # Pair changes counted directly for BOTH baselines and candidate from traces.
    pairs={name:[] for name in ('candidate','old_q','relay')}
    for initial,noise,forcing in zip(*test):
        traces={}
        if chosen['kind']=='Q_5s':traces['candidate']=base.rollout(parameters,actions,initial,noise,forcing,0,q,v)[1]
        else:traces['candidate']=temporal.rollout(parameters,actions,initial,noise,forcing,37.5,.2,q,v)[1]
        traces['old_q']=base.rollout(parameters,actions,initial,noise,forcing,1,oldq,oldv)[1]
        traces['relay']=base.rollout(parameters,actions,initial,noise,forcing,2,oldq,oldv)[1]
        for name,trace in traces.items():
            previous=100*actions[int(initial[3])]
            outputs=trace[:,2:4]
            pairs[name].append(int(np.any(outputs[0]!=previous))+int(np.sum(np.any(outputs[1:]!=outputs[:-1],axis=1))))
    for name,met in (('candidate',candidate),('old_q',oldmetrics),('relay',relay)):
        met['pair_changes']=float(np.mean(pairs[name]))
    passed=(report['model_passed'] and candidate['in_band_pct']>=95 and candidate['invalid_fraction']==0
        and candidate.get('unseen_fraction',candidate.get('unseen_decision_fraction',0))==0
        and candidate['guard_fraction']<=.01 and candidate['in_band_pct']>=oldmetrics['in_band_pct']-.5
        and candidate['pair_changes']<=.8*oldmetrics['pair_changes'])
    result=dict(status='ELIGIBLE_MONITORED_EMPTY_BOX_PILOT' if passed else 'NOT_ELIGIBLE_FOR_PI',
        candidate=candidate,old_q_on_new_model=oldmetrics,relay_on_new_model=relay,
        evidence='SIMULATION from actual Nov20 measurements; not hardware validation',selection=chosen)
    write(out/'ket_qua_huan_luyen.json',result)
    package=dict(version=1,purpose='NOV20_EMPTY_BOX_PILOT',supervised_pilot_allowed=bool(passed),
        production_deploy_allowed=False,target_c=37.5,band_c=.2,state_count=2430,
        state_encoder='band_previous_action_v1',kind=chosen['kind'],dt_s=5,actions=actions.tolist(),model=m,
        sensor_id='28-000000ca6c1f',data_sha256=hashlib.sha256((ROOT/'Du_lieu_dap_ung/du_lieu.csv').read_bytes()).hexdigest(),
        policy=dict(q=q.tolist(),visits=v.tolist()),validation=result)
    write(out/'goi_rl_moi.json',package)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--episodes',type=int,default=64000)
    parser.add_argument('--chi-phan-tich',action='store_true')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    session=measured.read_log(ROOT/'Du_lieu_dap_ung/du_lieu.csv')
    info=audit(session,args.out)
    if info['issues'] or not info['completed'] or info['hardware_exit_code']!=0:
        raise ValueError('Source run has faults or is incomplete')
    report,rows=identify(session,args.out)
    print('MODEL',report['model_passed'],'CV30',report['cv30_rmse_c'],'CV60',report['cv60_rmse_c'],flush=True)
    if not args.chi_phan_tich:training(report,rows,args.out,args.episodes)


if __name__=='__main__':main()
