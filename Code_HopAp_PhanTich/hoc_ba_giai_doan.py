"""Three independent goal-conditioned Q tables selected by incubation stage.
Training/evaluation in OLD measured model only. No GPIO, no Pi deployment.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from numba import njit
import hoc_vung_on_dinh as base
from lich_ap_ba_giai_doan import PROFILE, stage_for_day

encode=base.encode
reward=base.reward
step=base.step
guard_update=base.guard_update
STATE_COUNT=2430


@njit(cache=True)
def goal_state(t,d,m,previous,guard,target,band):
    # Existing local encoder translated/scaled around the requested goal.
    return encode(37.5+(t-target)*.2/band,d,m,previous,guard)


@njit(cache=True)
def goal_reward(t,nt,h,f,oh,of,sw,rw,triggered,target,band):
    return reward(37.5+(t-target)*.2/band,37.5+(nt-target)*.2/band,h,f,oh,of,sw,rw,triggered)


@njit(cache=True)
def train(parameters,actions,pool,target,band,episodes,seed,sw,rw):
    np.random.seed(seed)
    q=np.zeros((STATE_COUNT,9));visits=np.zeros((STATE_COUNT,9),np.int64)
    for ep in range(episodes):
        item=pool[np.random.randint(len(pool))]
        # Deliberately simulated starting T; d/m/previous taken from measured pool.
        t=np.random.uniform(max(parameters[9],target-.7),min(parameters[10]-.01,target+.5))
        d,m,previous=item[1],item[2],int(item[3])
        disturbance=(np.random.randint(3)-1)*.008
        active=guard_update(t,False)
        epsilon=max(.025,.9*np.exp(-ep/max(1400.,episodes/5)))
        for k in range(120):
            s=goal_state(t,d,m,previous,active,target,band)
            a=1
            if not active:
                if np.random.random()<epsilon:a=np.random.randint(9)
                else:
                    best=-1e100;ties=0
                    for j in range(9):
                        if q[s,j]>best+1e-10:a=j;best=q[s,j];ties=1
                        elif abs(q[s,j]-best)<1e-10:
                            ties+=1
                            if np.random.random()<1./ties:a=j
            h,f=actions[a]
            nt,nd,nm=step(t,d,m,h,f,parameters,np.random.normal(0,parameters[11])+disturbance)
            invalid=not np.isfinite(nt) or nt<parameters[9] or nt>parameters[10]
            ng=guard_update(nt,active)
            r=-100.*(120-k) if invalid else goal_reward(t,nt,h,f,actions[previous,0],actions[previous,1],sw,rw,ng and not active,target,band)
            future=0.
            if not invalid:
                ns=goal_state(nt,nd,nm,a,ng,target,band)
                future=q[ns,1] if ng else np.max(q[ns])
            visits[s,a]+=1
            alpha=max(.015,.3/(1+visits[s,a]/30)**.6)
            q[s,a]+=alpha*(r+.99*future-q[s,a])
            if invalid:break
            t,d,m,previous,active=nt,nd,nm,a,ng
    return q,visits


@njit(cache=True)
def rollout(parameters,actions,goals,schedule,initial,noise,forcing,mode,q,visits):
    t,d,m,previous=initial[0],initial[1],initial[2],int(initial[3])
    active=False;total_error=0.;inside=0;guards=0;unknown=0;invalid=0
    lamp_changes=0;fan_changes=0;run=0;longest=0;outside=0;recovery=0.;exits=0;executed=0
    high=t;low=t;hot=0;cold=0
    trace=np.zeros((len(schedule),9))
    last_stage=schedule[0]
    if abs(t-goals[last_stage,0])>goals[last_stage,1]+1e-9:outside=1
    for k in range(len(schedule)):
        stage=schedule[k];target,band=goals[stage]
        if stage!=last_stage:
            run=0
            if outside:recovery+=len(schedule)*5;exits+=1
            outside=1 if abs(t-target)>band+1e-9 else 0
        active=guard_update(t,active)
        a=1
        if active:guards+=1
        elif mode==1:
            a=previous
            if t<target-band:a=8
            elif t>target+band:a=1
        elif mode==2:a=4
        else:
            s=goal_state(t,d,m,previous,False,target,band)
            best=-1e100;a=-1
            for j in range(9):
                if visits[stage,s,j]>0 and q[stage,s,j]>best:
                    best=q[stage,s,j];a=j
            if a<0:unknown+=1;a=4 # explicit diagnostic fallback, never deployable
        lamp_changes+=actions[a,0]!=actions[previous,0]
        fan_changes+=actions[a,1]!=actions[previous,1]
        nt,nd,nm=step(t,d,m,actions[a,0],actions[a,1],parameters,noise[k]+forcing[k])
        trace[k]=np.array([(k+1)*5.,float(stage),target,band,nt,actions[a,0]*100,actions[a,1]*100,
                           1. if active else 0.,nm])
        if not np.isfinite(nt) or nt<parameters[9] or nt>parameters[10]:invalid=1;break
        executed+=1;total_error+=abs(nt-target);high=max(high,nt);low=min(low,nt)
        if abs(nt-target)<=band+1e-9:
            inside+=1;run+=1;longest=max(longest,run)
            if outside:recovery+=outside*5;exits+=1;outside=0
        else:
            outside+=1;run=0;hot+=nt>target+band;cold+=nt<target-band
        t,d,m,previous,last_stage=nt,nd,nm,a,stage
    if outside:recovery+=len(schedule)*5;exits+=1
    count=len(schedule)
    met=np.array([inside/count*100,(total_error+5*(count-executed))/count,float(lamp_changes),float(fan_changes),
                  longest*5.,recovery/max(1,exits),float(invalid),unknown/count,guards/count,high,low,hot/count*100,cold/count*100])
    return met,trace


def bank(pool,parameters,target,seed,count):
    rng=np.random.default_rng(seed)
    initial=pool[rng.integers(0,len(pool),count)].copy()
    for i in range(count):initial[i,0]=(target,target-.5,min(parameters[10]-.01,target+.35),target-.2)[i%4]
    noise=rng.normal(0,parameters[11],(count,120));forcing=np.zeros_like(noise)
    for i in range(count):
        if i%4==1:forcing[i,40:]=-.008
        elif i%4==2:forcing[i,40:]=.008
    return initial,noise,forcing


def evaluate(parameters,actions,goals,stage,cases,mode,q,v):
    schedule=np.full(120,stage,np.int64)
    metrics=np.array([rollout(parameters,actions,goals,schedule,initial,noise,forcing,mode,q,v)[0]
                      for initial,noise,forcing in zip(*cases)])
    return dict(zip(base.METRICS,metrics.mean(axis=0).tolist()))


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--episodes',type=int,default=64000)
    args=p.parse_args(argv)
    if args.episodes<500 or args.episodes%500:p.error('Episodes là bội số 500, tối thiểu 500.')
    package=base.ROOT/'Code_HopAp_Demo/goi_thu_rl_20261117.json'
    source=json.loads(package.read_text(encoding='utf-8'));m=source['model']
    parameters=np.array(m['coefficients']+[m['center'],m['fan_center'],m['tau'],m['low'],m['high'],m['noise_sd']])
    actions=np.array(source['actions'],dtype=float)
    import phan_tich_reward as measured
    log=base.ROOT/'Du_lieu_khao_sat/20261117_070909_628598/du_lieu.csv'
    rows=measured.transitions(measured.read_log(log),m['tau'])
    pool=np.array([[r['temperature'],r['previous_delta'],r['memory_before'],
                    int(np.argmin(np.abs(actions[:,0]-r['h'])+np.abs(actions[:,1]-r['f'])))]
                   for r in rows if abs(r['temperature']-37.5)<=1.])
    if len(pool)<20:raise ValueError('Thiếu dữ liệu đo thực.')
    goals=np.array([[s['target_c'],(s['upper_c']-s['lower_c'])/2] for s in PROFILE['stages']])
    args.out.mkdir(parents=True,exist_ok=False)
    grid=[(s,r) for s in (.25,.5,1.) for r in (2.,4.)];seeds=(11,29,47)
    protocol=dict(profile=PROFILE,model=m,actions=actions.tolist(),state_count_per_stage=2430,
        separate_q_tables=3,episodes_per_stage_seed=args.episodes,grid=grid,seeds=seeds,
        source_package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
        source_csv_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        validation_seeds=[203001+i for i in range(3)],test_seeds=[203101+i for i in range(3)],
        selection='Validation only; require in-band>=95%, no invalid/unseen, guard<=2% before weighted ranking.',
        evidence='SIMULATION ENGINEERING BANDS, NOT BIOLOGICALLY VALIDATED; old empty-box model, no embryo heat model',
        deploy_allowed=False)
    protocol['code_sha256']={str(path.relative_to(base.ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__).resolve(),Path(base.__file__).resolve(),base.ROOT/'Code_HopAp_Demo/rl_vung_on_dinh.py',
                     base.ROOT/'Code_HopAp_Demo/lich_ap_ba_giai_doan.py')}
    (args.out/'giao_thuc.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    allq=np.zeros((3,2430,9));allv=np.zeros((3,2430,9),np.int64);chosen=[];trials=[]
    for stage in range(3):
        target,band_width=goals[stage];validation=bank(pool,parameters,target,203001+stage,128)
        options=[]
        for sw,rw in grid:
            for seed in seeds:
                q,v=train(parameters,actions,pool,target,band_width,args.episodes,seed,sw,rw)
                tq=allq.copy();tv=allv.copy();tq[stage]=q;tv[stage]=v
                met=evaluate(parameters,actions,goals,stage,validation,0,tq,tv)
                row=dict(stage=stage,seed=seed,switch_weight=sw,recovery_weight=rw,validation=met)
                trials.append(row);options.append((row,q,v))
                print(f'Giai đoạn {stage+1}, switch={sw:g}, recovery={rw:g}, seed={seed}: vùng {met["in_band_pct"]:.2f}%, đổi bóng {met["lamp_changes"]:.1f}',flush=True)
        def key(item):
            met=item[0]['validation']
            qualified=(met['in_band_pct']>=95 and met['invalid_fraction']==0 and met['unseen_fraction']==0 and met['guard_fraction']<=.02)
            return (not qualified,*base.rank(met))
        row,q,v=min(options,key=key);allq[stage]=q;allv[stage]=v;chosen.append(row)
    (args.out/'lua_chon_da_chot.json').write_text(json.dumps(chosen,indent=2),encoding='utf-8')
    (args.out/'thu_he_so.json').write_text(json.dumps(trials,indent=2),encoding='utf-8')
    results=[]
    for stage in range(3):
        test=bank(pool,parameters,goals[stage,0],203101+stage,192)
        candidate=evaluate(parameters,actions,goals,stage,test,0,allq,allv)
        baseline=evaluate(parameters,actions,goals,stage,test,1,allq,allv)
        passed=(candidate['in_band_pct']>=95 and candidate['invalid_fraction']==0
                and candidate['unseen_fraction']==0 and candidate['guard_fraction']<=.02)
        results.append(dict(stage=PROFILE['stages'][stage],candidate=candidate,deadband_reference=baseline,
                            simulation_gate_passed=passed))
    result=dict(status='SIMULATION_ONLY',deploy_allowed=False,biological_tolerance_validated=False,results=results,
        all_stages_simulation_gate_passed=all(r['simulation_gate_passed'] for r in results),
        limitations=['One old empty-box model; no independent hardware trial',
                     'Stage1 engineering band extends below published37.8..38.0 and touches guard38',
                     'Stages2/3 tolerances are engineering choices, not source recommendations',
                     'Embryo heat generation and changed egg thermal mass not identified'])
    (args.out/'ket_qua.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    np.savez_compressed(args.out/'Q_BA_GIAI_DOAN_MO_PHONG.npz',q=allq,visits=allv,goals=goals,actions=actions)
    export=dict(purpose='THREE_STAGE_SIMULATION_ONLY',deploy_allowed=False,supervised_pilot_allowed=False,
        profile=PROFILE,model=m,actions=actions.tolist(),policies=[dict(**chosen[i],q=allq[i].tolist(),visits=allv[i].tolist()) for i in range(3)])
    (args.out/'UNG_VIEN_KHONG_CHAY_PI.json').write_text(json.dumps(export,ensure_ascii=False),encoding='utf-8')
    # Accelerated schedule illustration; no reset of heat memory or previous action at stage boundaries.
    schedule=np.repeat(np.arange(3,dtype=np.int64),120)
    rng=np.random.default_rng(203201)
    _,trace=rollout(parameters,actions,goals,schedule,np.array([37.8,0.,.5,4.]),rng.normal(0,parameters[11],360),np.zeros(360),0,allq,allv)
    with (args.out/'CHUYEN_GIAI_DOAN_MO_PHONG.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['seconds','stage_id','target_c','band_c','temperature_c','lamp_pct','fan_pct','guard','heat_memory']);w.writerows(trace.tolist())
    lines=['# Ba giai đoạn — kết quả mô phỏng','',
           'Chỉ là dung sai kỹ thuật đề xuất. Chưa xác nhận điều kiện ấp thật, chưa thay Q-table Pi.','',
           '|Ngày|Mốc °C|Vùng kỹ thuật °C|Trong vùng %|Đổi bóng/10 phút|Bảo vệ % bước|Đạt gate mô phỏng|',
           '|---|---|---|---|---|---|---|']
    for row in results:
        s=row['stage'];c=row['candidate']
        lines.append(f"|{s['days'][0]}–{s['days'][1]}|{s['target_c']}|{s['lower_c']}–{s['upper_c']}|{c['in_band_pct']:.2f}|{c['lamp_changes']:.1f}|{100*c['guard_fraction']:.2f}|{row['simulation_gate_passed']}|")
    lines += ['', 'Các chỉ số là trung bình 192 kịch bản 600s riêng từng giai đoạn, cùng mô hình cũ. Không chứng minh ổn định 21 ngày hay tỷ lệ nở.',
              'Guard38→37°C giữ nguyên. Vùng đầu chạm ngưỡng guard; không coi đạt gate mô phỏng là cho phép dùng sinh học.',
              'CSV chuyển giai đoạn dùng 10 phút/giai đoạn để minh họa phần mềm, giữ nguyên bộ nhớ nhiệt; không mô phỏng phát triển phôi theo ngày.',
              'Lịch thật tham chiếu nguồn: ngày1–10:37.8..38.0; ngày11–17:37.5; ngày18–21:37.2. Dung sai của demo là đề xuất riêng.']
    (args.out/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Đã huấn luyện ba policy mô phỏng. Chưa triển khai:',args.out,flush=True)


if __name__=='__main__':main()
