"""Train/evaluate band Q-learning in the EXISTING measured model, never on GPIO.

Use Anaconda Python (numpy/numba). Output is SIMULATION ONLY, not Pi-loadable.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Code_HopAp_Demo'))
import rl_vung_on_dinh as logic

encode = njit(cache=True)(logic.state_id)
reward = njit(cache=True)(logic.reward)
STATE_COUNT = logic.STATE_COUNT


@njit(cache=True)
def step(t,d,m,h,f,parameters,noise):
    c=parameters
    nm=m+(h-m)*(1-np.exp(-5/c[8]))
    fc=f-c[7]
    nd=c[0]+c[1]*(t-c[6])+c[2]*d+c[3]*nm+c[4]*fc+c[5]*nm*fc+noise
    return t+nd,nd,nm


@njit(cache=True)
def old_state(t,d,m,guard):
    b=0
    for edge in (-2.,-1.,-.5,-.15,.15,.5,1.,2.):
        if t-37.5>=edge:b+=1
    tr=0 if d<-.05 else 2 if d>.05 else 1
    mem=0 if m<1/3 else 2 if m>2/3 else 1
    return 2*((b*3+tr)*3+mem)+int(guard)


@njit(cache=True)
def guard_update(t,active):
    return t>37 if active else t>=38


@njit(cache=True)
def train(parameters,actions,pool,episodes,seed,switch_weight,recovery_weight):
    np.random.seed(seed)
    q=np.zeros((STATE_COUNT,9));visits=np.zeros((STATE_COUNT,9),np.int64)
    learning=np.zeros((episodes//500,3))
    for ep in range(episodes):
        item=pool[np.random.randint(len(pool))]
        t,d,m,previous=item[0],item[1],item[2],int(item[3])
        if np.random.random()<.5:
            t=np.random.uniform(36.6,38.1)
        disturbance=(np.random.randint(3)-1)*.008
        active=guard_update(t,False)
        eps=max(.025,.9*np.exp(-ep/max(1400.,episodes/5)))
        total=0.;inside=0;changes=0
        for k in range(120):
            s=encode(t,d,m,previous,active)
            a=1
            if not active:
                if np.random.random()<eps:a=np.random.randint(9)
                else:
                    best=-1e100
                    ties=0
                    for j in range(9):
                        if q[s,j]>best+1e-10:
                            a=j;best=q[s,j];ties=1
                        elif abs(q[s,j]-best)<1e-10:
                            ties+=1
                            if np.random.random()<1./ties:a=j
            h,f=actions[a]
            nt,nd,nm=step(t,d,m,h,f,parameters,np.random.normal(0,parameters[11])+disturbance)
            invalid=not np.isfinite(nt) or nt<parameters[9] or nt>parameters[10]
            nxt=guard_update(nt,active)
            r=(-100.*(120-k) if invalid else reward(t,nt,h,f,actions[previous,0],actions[previous,1],
                                                     switch_weight,recovery_weight,nxt and not active))
            future=0.
            if not invalid:
                sn=encode(nt,nd,nm,a,nxt)
                future=q[sn,1] if nxt else np.max(q[sn])
            visits[s,a]+=1
            alpha=max(.015,.3/(1+visits[s,a]/30)**.6)
            q[s,a]+=alpha*(r+.99*future-q[s,a])
            total+=r;inside+=abs(nt-37.5)<=.2+1e-9;changes+=a!=previous
            if invalid:break
            t,d,m,previous,active=nt,nd,nm,a,nxt
        if (ep+1)%500==0:
            learning[(ep+1)//500-1]=np.array([total,inside/120.,float(changes)])
    return q,visits,learning


@njit(cache=True)
def rollout(parameters,actions,initial,noises,forcing,mode,q,visits):
    t,d,m,previous=initial[0],initial[1],initial[2],int(initial[3])
    active=False;total_error=0.;inband=0;invalid=0;unseen=0;guards=0
    lamp_changes=0;fan_changes=0;run=0;longest=0
    outside_run=1 if abs(t-37.5)>.2+1e-9 else 0
    return_sum=0.;excursions=0;executed=0
    cold=0;hot=0;maximum=t;minimum=t
    trace=np.zeros((len(noises),5))
    for k in range(len(noises)):
        active=guard_update(t,active)
        a=1
        if active:guards+=1
        elif mode==2: # deadband relay, same supported action set
            a=previous
            if t<37.3:a=8
            elif t>37.7:a=1
        elif mode==3:a=4 # fixed 50/75 reference
        else:
            s=old_state(t,d,m,False) if mode==1 else encode(t,d,m,previous,False)
            best=-1e100;a=-1
            for j in range(9):
                if visits[s,j]>0 and q[s,j]>best:
                    a=j;best=q[s,j]
            if a<0:
                unseen+=1
                # Evaluation fallback is explicitly counted; never called learned.
                a=4
        lamp_changes+=actions[a,0]!=actions[previous,0]
        fan_changes+=actions[a,1]!=actions[previous,1]
        nt,nd,nm=step(t,d,m,actions[a,0],actions[a,1],parameters,noises[k]+forcing[k])
        trace[k]=np.array([(k+1)*5.,nt,actions[a,0]*100,actions[a,1]*100,1. if active else 0.])
        if not np.isfinite(nt) or nt<parameters[9] or nt>parameters[10]:
            invalid=1
            break
        total_error+=abs(nt-37.5);maximum=max(maximum,nt);minimum=min(minimum,nt)
        executed+=1
        ok=abs(nt-37.5)<=.2+1e-9
        if ok:
            inband+=1;run+=1;longest=max(longest,run)
            if outside_run:
                return_sum+=outside_run*5;excursions+=1;outside_run=0
        else:
            outside_run+=1;run=0;cold+=nt<37.3;hot+=nt>37.7
        t,d,m,previous=nt,nd,nm,a
    if outside_run:
        # Censored return receives remaining-horizon penalty, not a fake fast return.
        return_sum+=len(noises)*5;excursions+=1
    count=len(noises)
    metrics=np.array([inband/count*100,(total_error+5*(count-executed))/count,float(lamp_changes),float(fan_changes),
                      longest*5.,return_sum/max(1,excursions),float(invalid),unseen/count,guards/count,
                      maximum,minimum,hot/count*100,cold/count*100])
    return metrics,trace


METRICS=['in_band_pct','mae_c','lamp_changes','fan_changes','longest_in_band_s',
         'recovery_penalized_s','invalid_fraction','unseen_fraction','guard_fraction',
         'max_temperature_c','min_temperature_c','hot_pct','cold_pct']


def cases(pool,parameters,seed,count=64,steps=120):
    rng=np.random.default_rng(seed)
    initial=pool[rng.integers(0,len(pool),count)].copy()
    # Same declared starting temperatures and disturbances for every controller.
    for i in range(count):
        initial[i,0]=(37.5,37.0,37.9,37.3)[i%4]
    noise=rng.normal(0,parameters[11],(count,steps))
    forcing=np.zeros_like(noise)
    for i in range(count):
        if i%4==1:forcing[i,40:]=-.008
        if i%4==2:forcing[i,40:]=.008
    return initial,noise,forcing


def evaluate(parameters,actions,bank,mode,q,visits):
    all_m=np.array([rollout(parameters,actions,s,n,f,mode,q,visits)[0] for s,n,f in zip(*bank)])
    return dict(zip(METRICS,all_m.mean(axis=0).tolist()))


def rank(m):
    return (m['invalid_fraction']>0,m['unseen_fraction']>.005,m['guard_fraction']>.01,
            (100-m['in_band_pct'])+.08*m['lamp_changes']+.04*m['fan_changes']
            +.01*m['recovery_penalized_s'])


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--episodes',type=int,default=64000)
    p.add_argument('--nguon',type=Path,default=ROOT/'Code_HopAp_Demo/goi_thu_rl_20261117.json')
    args=p.parse_args(argv)
    if args.episodes<500 or args.episodes%500:p.error('Episodes là bội số 500, tối thiểu 500.')
    source=json.loads(args.nguon.read_text(encoding='utf-8'))
    m=source['model'];actions=np.array(source['actions'],dtype=float)
    if actions.shape!=(9,2) or list(actions[1])!=[0,1] or list(actions[4])!=[.5,.75]:
        raise ValueError('Tập action khác giao thức đã đo.')
    parameters=np.array(m['coefficients']+[m['center'],m['fan_center'],m['tau'],m['low'],m['high'],m['noise_sd']])
    import phan_tich_reward as measured
    log=ROOT/'Du_lieu_khao_sat/20261117_070909_628598/du_lieu.csv'
    rows=measured.transitions(measured.read_log(log),m['tau'])
    pool=[]
    for r in rows:
        if abs(r['temperature']-37.5)<=1.:
            previous=int(np.argmin(np.abs(actions[:,0]-r['h'])+np.abs(actions[:,1]-r['f'])))
            pool.append([r['temperature'],r['previous_delta'],r['memory_before'],previous])
    pool=np.array(pool)
    if len(pool)<20:raise ValueError('Thiếu trạng thái khởi đầu đo thực quanh mục tiêu.')
    args.out.mkdir(parents=True,exist_ok=False)
    seeds=(11,29,47);grid=[(s,r) for s in (.25,.5,1.,2.) for r in (2.,4.)]
    validation=cases(pool,parameters,20261124,128)
    oldq=np.array(source['policy']['q']);oldv=np.array(source['policy']['visits'],np.int64)
    protocol=dict(target_c=37.5,lower_c=37.3,upper_c=37.7,dt_s=5,state_count=STATE_COUNT,
        state='9 error x 3 trend x 5 heater memory x 9 previous action x 2 guard',
        source_package_sha256=hashlib.sha256(args.nguon.read_bytes()).hexdigest(),
        source_csv_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),episodes=args.episodes,seeds=seeds,
        grid=grid,validation_seed=20261124,test_seed=20261125,
        development_note='Earlier v1/v2 simulations reviewed; new validation/test seeds fixed before this run. Seed selection now uses validation, never test.',
        augmentation='50% simulated initial T uniform36.6..38.1 with measured d/m/previous; persistent synthetic forcing -0.008/0/+0.008 C per5s',
        evidence='SIMULATION DEVELOPMENT ON EXISTING SHORT-HORIZON MODEL; NEW LONG MEASUREMENTS NOT YET AVAILABLE',
        deploy_allowed=False,ranking='invalid, unseen, guard feasibility first; then outside_pct + .08 lamp_changes + .04 fan_changes + .01 penalized_recovery_s',
        weights_are_design_candidates_not_physical_constants=True)
    protocol['code_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (Path(__file__).resolve(),ROOT/'Code_HopAp_Demo/rl_vung_on_dinh.py')}
    (args.out/'giao_thuc.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    old_validation=evaluate(parameters,actions,validation,1,oldq,oldv)
    def choose_key(met):
        qualified=(met['invalid_fraction']==0 and met['unseen_fraction']==0 and met['guard_fraction']<=.01
                   and met['in_band_pct']>=old_validation['in_band_pct']
                   and met['lamp_changes']<=.8*old_validation['lamp_changes']
                   and met['recovery_penalized_s']<=1.1*old_validation['recovery_penalized_s'])
        return (not qualified,*rank(met))
    protocol['selection']='Select weights AND seed on validation only; qualify against oldQ for band occupancy, recovery and >=20% fewer lamp changes before weighted ranking.'
    protocol['reward_formula']='inside: 1 - .5*(abs(T-37.5)/.2)^2; outside: -1 - recovery*out -2*out^2; +.5 progress; -switch*(inside?1:.15)*(action_changed+abs(dH)+.5abs(dF)); -25 guard'
    (args.out/'giao_thuc.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    trials=[];policies={};curves=[]
    for sw,rw in grid:
        metrics=[];snapshots=[]
        for seed in seeds:
            start=time.monotonic()
            q,v,learning=train(parameters,actions,pool,args.episodes,seed,sw,rw)
            met=evaluate(parameters,actions,validation,0,q,v);metrics.append(met)
            snapshots.append((seed,q,v))
            for i,row in enumerate(learning):curves.append([sw,rw,seed,(i+1)*500,*row.tolist()])
            print(f'switch={sw:g}, recovery={rw:g}, seed={seed}: vùng={met["in_band_pct"]:.2f}%, đổi bóng={met["lamp_changes"]:.1f}, unseen={met["unseen_fraction"]:.3f}; {time.monotonic()-start:.1f}s',flush=True)
        mean={k:sum(met[k] for met in metrics)/len(metrics) for k in METRICS}
        trials.append(dict(switch_weight=sw,recovery_weight=rw,validation=mean,by_seed=metrics))
        policies[(sw,rw)]=snapshots
    options=[dict(switch_weight=r['switch_weight'],recovery_weight=r['recovery_weight'],seed=seed,validation=met)
             for r in trials for seed,met in zip(seeds,r['by_seed'])]
    (args.out/'thu_cac_he_so.json').write_text(json.dumps(trials,indent=2),encoding='utf-8')
    best=min(options,key=lambda r:choose_key(r['validation']))
    # Freeze both reward and training seed on validation, before touching final test cases.
    (args.out/'lua_chon_da_chot.json').write_text(json.dumps(best,indent=2),encoding='utf-8')
    selected=policies[(best['switch_weight'],best['recovery_weight'])]
    test=cases(pool,parameters,20261125,192)
    test_seeds=[]
    for seed,q,v in selected:
        test_seeds.append(dict(seed=seed,metrics=evaluate(parameters,actions,test,0,q,v)))
    q,v=next((sq,sv) for seed,sq,sv in selected if seed==best['seed'])
    baselines={name:evaluate(parameters,actions,test,mode,oldq,oldv)
               for name,mode in [('old_q',1),('deadband_relay',2),('fixed_50_75',3)]}
    candidate=next(row['metrics'] for row in test_seeds if row['seed']==best['seed']);old=baselines['old_q']
    paired=[]
    for initial,noises,forcing in zip(*test):
        a=rollout(parameters,actions,initial,noises,forcing,0,q,v)[0]
        b=rollout(parameters,actions,initial,noises,forcing,1,oldq,oldv)[0]
        paired.append((a,b))
    differences=np.array([a-b for a,b in paired])
    bootstrap=np.random.default_rng(20261126)
    intervals={}
    for column in (0,2,3,4,5):
        draws=differences[bootstrap.integers(0,len(paired),(2000,len(paired))),column].mean(axis=1)
        intervals[METRICS[column]]=dict(candidate_minus_old=float(differences[:,column].mean()),
                                       conditional_95pct_interval=np.quantile(draws,[.025,.975]).tolist())
    with (args.out/'tung_kich_ban_MO_PHONG.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['case','controller']+METRICS)
        for i,(a,b) in enumerate(paired):
            w.writerow([i,'candidate',*a.tolist()]);w.writerow([i,'old_q',*b.tolist()])
    passed=(candidate['invalid_fraction']==0 and candidate['unseen_fraction']==0
            and candidate['guard_fraction']<=.01 and candidate['in_band_pct']>=old['in_band_pct']
            and candidate['lamp_changes']<=.8*old['lamp_changes']
            and candidate['recovery_penalized_s']<=1.1*old['recovery_penalized_s'])
    export=dict(purpose='SIMULATION_ONLY_BAND_CANDIDATE',deploy_allowed=False,supervised_pilot_allowed=False,
        target_c=37.5,band_c=.2,state_count=STATE_COUNT,state_encoder='band_previous_action_v1',
        seed=best['seed'],dt_s=5,actions=actions.tolist(),model=m,reward_weights=best,
        q=q.tolist(),visits=v.tolist(),source_package_sha256=protocol['source_package_sha256'])
    (args.out/'Q_UNG_VIEN_CHUA_DUOC_CHAY_PI.json').write_text(json.dumps(export,allow_nan=False),encoding='utf-8')
    result=dict(status='PASS_SIMULATION_ONLY' if passed else 'FAIL_SIMULATION_GATE',selected=best,
                candidate=candidate,selected_seed=best['seed'],test_by_seed=test_seeds,baselines=baselines,
                paired_simulation_differences=intervals,
                limitations=['Not independent hardware evidence','Only one existing measured model',
                             'No new long-run response CSV','Reward selection uses simulation validation',
                             'Recovery metric penalizes unfinished excursions; not proof of fastest possible return'],
                deploy_allowed=False)
    (args.out/'ket_qua.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    with (args.out/'duong_hoc.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['switch','recovery','seed','episode','last_episode_reward','last_episode_in_band_fraction','last_episode_action_changes']);w.writerows(curves)
    with (args.out/'so_sanh.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['controller']+METRICS)
        for name,met in dict(candidate=candidate,**baselines).items():w.writerow([name]+[met[k] for k in METRICS])
    trace_rows=[]
    for name,mode,tq,tv in [('candidate',0,q,v),('old_q',1,oldq,oldv)]:
        _,trace=rollout(parameters,actions,test[0][0],test[1][0],test[2][0],mode,tq,tv)
        trace_rows += [[name,*r.tolist()] for r in trace]
    with (args.out/'trace_MO_PHONG.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['controller','seconds','temperature_c','lamp_pct','fan_pct','guard']);w.writerows(trace_rows)
    lines=['# Q-learning vùng 37.3–37.7°C','',result['status'],'',
           'Mục tiêu trung tâm 37.5°C; đây là mô phỏng phát triển, chưa được phép chạy Pi.','',
           '|Controller|Trong vùng %|MAE °C|Đổi bóng/10 phút|Đổi quạt/10 phút|Đoạn trong vùng dài nhất s|Hồi phục có phạt s|',
           '|---|---|---|---|---|---|---|']
    for name,met in dict(candidate=candidate,**baselines).items():
        lines.append(f'|{name}|'+ '|'.join(f'{met[k]:.3f}' for k in METRICS[:6])+'|')
    lines += ['', 'Không áp bộ lọc giữ action lên Q-table cũ. Chính sách mới được huấn luyện với previous action trong state và chi phí đổi mức trong reward.',
              'Các chỉ số là trung bình 192 kịch bản mô phỏng, mỗi kịch bản 600s. Đoạn trong vùng dài nhất là trung bình độ dài tối đa của từng kịch bản. Recovery có phạt các đoạn chưa trở về, không phải chứng minh thời gian tối thiểu.',
              'Xem chênh lệch ghép cặp và khoảng bootstrap trong ket_qua.json; khoảng này chỉ phản ánh các kịch bản trong cùng mô hình, không bao gồm sai số mô hình hoặc độ chính xác cảm biến.',
              'Dữ liệu thật đo dài chưa có; mô hình cũ chỉ được kiểm chứng tốt ở chân trời ngắn. Không khẳng định giữ ổn định cả hộp/trứng hoặc tối ưu toàn cục.',
              'Q-table Pi cũ không bị sửa. Cần kiểm tra mô hình và lượt thử thật độc lập trước khi triển khai.']
    (args.out/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(result['status'],args.out,flush=True)


if __name__=='__main__':main()
