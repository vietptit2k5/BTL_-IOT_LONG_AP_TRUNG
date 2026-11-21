"""Semi-Markov Q-learning with nominal30s in-band/10s outside actions.
Measured OLD model only; never accesses GPIO or replaces the Pi package.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from numba import njit
import hoc_ba_giai_doan as stages
from lich_ap_ba_giai_doan import PROFILE
import giu_hanh_dong_rl as timing

window=njit(cache=True)(timing.action_steps)
interrupt=njit(cache=True)(timing.interrupt_action)


@njit(cache=True)
def macro(parameters,actions,t,d,m,previous,active,a,target,band,sw,rw,noise,forcing,k):
    count=min(window(t,target,band,active),len(noise)-k)
    path=np.zeros((6,4));total=0.;discount=1.;invalid=False;n=0
    for j in range(count):
        nt,nd,nm=stages.step(t,d,m,actions[a,0],actions[a,1],parameters,noise[k+j]+forcing[k+j])
        ng=stages.guard_update(nt,active)
        invalid=not np.isfinite(nt) or nt<parameters[9] or nt>parameters[10]
        r=(-100.*(len(noise)-k-j) if invalid else
           stages.goal_reward(t,nt,actions[a,0],actions[a,1],actions[previous,0],actions[previous,1],sw,rw,
                              ng and not active,target,band))
        total+=discount*r;discount*=.99
        path[j]=np.array([nt,nd,nm,1. if active else 0.]);n+=1
        stop=invalid or interrupt(t,nt,target,band,ng)
        t,d,m,previous,active=nt,nd,nm,a,ng
        if stop:break
    return t,d,m,active,total,discount,n,invalid,path


@njit(cache=True)
def train(parameters,actions,pool,target,band,episodes,seed,sw,rw):
    np.random.seed(seed)
    q=np.zeros((2430,9));v=np.zeros((2430,9),np.int64)
    for ep in range(episodes):
        item=pool[np.random.randint(len(pool))]
        t=np.random.uniform(max(parameters[9],target-.7),min(parameters[10]-.01,target+.5))
        d,m,previous=item[1],item[2],int(item[3]);active=stages.guard_update(t,False)
        noise=np.random.normal(0,parameters[11],120)
        forcing=np.full(120,(np.random.randint(3)-1)*.008)
        epsilon=max(.025,.9*np.exp(-ep/max(1400.,episodes/5)))
        k=0
        while k<120:
            s=stages.goal_state(t,d,m,previous,active,target,band)
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
            nt,nd,nm,ng,r,discount,n,invalid,_=macro(parameters,actions,t,d,m,previous,active,a,target,band,sw,rw,noise,forcing,k)
            future=0.
            if not invalid:
                ns=stages.goal_state(nt,nd,nm,a,ng,target,band)
                future=q[ns,1] if ng else np.max(q[ns])
            v[s,a]+=1
            alpha=max(.015,.3/(1+v[s,a]/30)**.6)
            q[s,a]+=alpha*(r+discount*future-q[s,a])
            if invalid:break
            t,d,m,previous,active=nt,nd,nm,a,ng;k+=n
    return q,v


@njit(cache=True)
def rollout(parameters,actions,initial,noise,forcing,target,band,q,v):
    t,d,m,previous=initial[0],initial[1],initial[2],int(initial[3]);active=False
    inside=0;error=0.;hchanges=0;fchanges=0;decisions=0;unknown=0;guards=0;invalid=False;pair_changes=0
    longest=0;run=0;k=0;trace=np.zeros((len(noise),7))
    while k<len(noise):
        active=stages.guard_update(t,active)
        a=1
        if not active:
            s=stages.goal_state(t,d,m,previous,False,target,band)
            a=-1;best=-1e100
            for j in range(9):
                if v[s,j]>0 and q[s,j]>best:a=j;best=q[s,j]
            if a<0:a=4;unknown+=1
        hchanges+=actions[a,0]!=actions[previous,0]
        pair_changes+=a!=previous
        fchanges+=actions[a,1]!=actions[previous,1];decisions+=1
        nt,nd,nm,ng,_,_,n,invalid,path=macro(parameters,actions,t,d,m,previous,active,a,target,band,0.,0.,noise,forcing,k)
        for j in range(n):
            temperature=path[j,0]
            ok=abs(temperature-target)<=band+1e-9
            inside+=ok;error+=abs(temperature-target);guards+=path[j,3]>0
            run=run+1 if ok else 0;longest=max(longest,run)
            trace[k+j]=np.array([(k+j+1)*5.,temperature,actions[a,0]*100,actions[a,1]*100,path[j,3],
                                 1. if j==0 else 0.,float(n)*5])
        k+=n
        if invalid:break
        t,d,m,previous,active=nt,nd,nm,a,ng
    metrics=np.array([100*inside/len(noise),(error+5*(len(noise)-k))/len(noise),float(hchanges),float(fchanges),
                      longest*5.,float(decisions),unknown/max(1,decisions),guards/len(noise),1. if invalid else 0.,float(pair_changes)])
    return metrics,trace


NAMES=['in_band_pct','mae_c','lamp_changes','fan_changes','longest_in_band_s','decisions',
       'unseen_decision_fraction','guard_fraction','invalid_fraction','pair_changes']


def evaluate(parameters,actions,cases,target,band,q,v):
    rows=np.array([rollout(parameters,actions,s,n,f,target,band,q,v)[0] for s,n,f in zip(*cases)])
    return dict(zip(NAMES,rows.mean(axis=0).tolist()))


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--giai-doan',type=int,choices=(1,2,3),default=2)
    p.add_argument('--episodes',type=int,default=64000)
    args=p.parse_args(argv)
    if args.episodes<500:p.error('Ít nhất500episode.')
    source_path=stages.base.ROOT/'Code_HopAp_Demo/goi_thu_rl_20261117.json'
    source=json.loads(source_path.read_text(encoding='utf-8'));m=source['model']
    parameters=np.array(m['coefficients']+[m['center'],m['fan_center'],m['tau'],m['low'],m['high'],m['noise_sd']])
    actions=np.array(source['actions'],float)
    import phan_tich_reward as measured
    log=stages.base.ROOT/'Du_lieu_khao_sat/20261117_070909_628598/du_lieu.csv'
    rows=measured.transitions(measured.read_log(log),m['tau'])
    pool=np.array([[r['temperature'],r['previous_delta'],r['memory_before'],
                   int(np.argmin(abs(actions[:,0]-r['h'])+abs(actions[:,1]-r['f'])))]
                  for r in rows if abs(r['temperature']-37.5)<=1.])
    stage=args.giai_doan-1;spec=PROFILE['stages'][stage];target=spec['target_c'];band=(spec['upper_c']-spec['lower_c'])/2
    args.out.mkdir(parents=True,exist_ok=False)
    protocol=dict(purpose='TEMPORALLY_EXTENDED_Q_LEARNING_SIMULATION_ONLY',stage=spec,dt_model_s=5,
        nominal_inside_hold_s=30,nominal_outside_hold_s=10,guard_check_s=5,
        interrupt='band entry/exit or soft guard; no post-training output filter',
        discount='SMDP: sum(gamma^j*r_j) + gamma^n*maxQ(next), gamma=.99 per5s',
        episodes=args.episodes,seeds=[11,29,47],grid=[.25,.5,1.],recovery_weight=4.,
        validation_seed=204001+stage,test_seed=204101+stage,deploy_allowed=False,
        source_package_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        source_csv_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        diagnostic_acceptance='No invalid/unseen; band occupancy loses at most0.5pp vs reference; pair changes reduce at least20%.',
        limits='Old empty-box model, not new measurements; nominal30s may be interrupted before deadline; biological bands unvalidated.')
    (args.out/'giao_thuc.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    validation=stages.bank(pool,parameters,target,204001+stage,128);options=[]
    for sw in (.25,.5,1.):
        for seed in (11,29,47):
            q,v=train(parameters,actions,pool,target,band,args.episodes,seed,sw,4.)
            met=evaluate(parameters,actions,validation,target,band,q,v)
            options.append((dict(seed=seed,switch_weight=sw,validation=met),q,v))
            print(f'switch={sw:g}, seed={seed}: vùng={met["in_band_pct"]:.2f}%, đổi bóng={met["lamp_changes"]:.1f}',flush=True)
    def rank(item):
        r=item[0]['validation'];bad=(r['invalid_fraction']>0 or r['unseen_decision_fraction']>0 or r['guard_fraction']>.02 or r['in_band_pct']<95)
        return (bad,100-r['in_band_pct']+.15*r['lamp_changes']+.05*r['fan_changes'])
    chosen,q,v=min(options,key=rank)
    (args.out/'lua_chon_da_chot.json').write_text(json.dumps(chosen,indent=2),encoding='utf-8')
    test=stages.bank(pool,parameters,target,204101+stage,192)
    result=evaluate(parameters,actions,test,target,band,q,v)
    reference_path=stages.base.ROOT/'outputs/rl_ba_giai_doan_20261120_final/Q_BA_GIAI_DOAN_MO_PHONG.npz'
    ref=np.load(reference_path)
    goals=ref['goals']
    old=stages.evaluate(parameters,actions,goals,stage,test,0,ref['q'],ref['visits'])
    pair_counts=[]
    for initial,noise,forcing in zip(*test):
        _,oldtrace=stages.rollout(parameters,actions,goals,np.full(120,stage,np.int64),initial,noise,forcing,0,ref['q'],ref['visits'])
        previous=actions[int(initial[3])]*100
        changes=0
        for point in oldtrace:
            applied=point[5:7]
            changes+=not np.array_equal(applied,previous)
            previous=applied
        pair_counts.append(changes)
    old['pair_changes']=float(np.mean(pair_counts))
    accepted=(result['invalid_fraction']==0 and result['unseen_decision_fraction']==0
              and result['in_band_pct']>=old['in_band_pct']-.5
              and result['pair_changes']<=.8*old['pair_changes'])
    status='PASS_SIMULATION_ONLY' if accepted else 'REJECTED_SIMULATION_TRADEOFF'
    report=dict(status=status,candidate=result,reference_5s=old,selected=chosen,deploy_allowed=False,
                conclusions='Compare band occupancy AND action changes. Nominal30s alone does not prove quality or hardware effectiveness.')
    (args.out/'ket_qua.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    np.savez_compressed(args.out/'Q_ACTION_KEO_DAI_MO_PHONG.npz',q=q,visits=v)
    _,trace=rollout(parameters,actions,test[0][0],test[1][0],test[2][0],target,band,q,v)
    with (args.out/'trace_MO_PHONG.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['seconds','temperature_c','lamp_pct','fan_pct','guard','decision_start','macro_s']);w.writerows(trace.tolist())
    text=['# Q-learning hành động kéo dài — chỉ mô phỏng','',status,'',f'Mốc {target}°C, vùng ±{band:.2f}°C.','',
          '|Policy|Trong vùng %|Đổi bóng/10phút|Đổi quạt/10phút|Đoạn trong vùng dài nhất s|',
          '|---|---|---|---|---|',
          f"|Q5s tham chiếu|{old['in_band_pct']:.2f}|{old['lamp_changes']:.1f}|{old['fan_changes']:.1f}|{old['longest_in_band_s']:.1f}|",
          f"|Q hành động kéo dài|{result['in_band_pct']:.2f}|{result['lamp_changes']:.1f}|{result['fan_changes']:.1f}|{result['longest_in_band_s']:.1f}|",'',
          'Giữ dự kiến30s trong vùng,10s ngoài vùng; được ngắt sớm khi qua biên hoặc bảo vệ. Không đảm bảo mọi lần giữ đủ30s.',
          'Reward được tích lũy từng bước5s và bootstrap theo gamma^n; không chỉ lấy Q cũ rồi chặn đầu ra.',
          'Q5s tham chiếu ở đây là ứng viên ba giai đoạn mô phỏng, không phải Q-table đang chạy trên Pi. Xem pair_changes trong JSON để đánh giá đổi action chung.',
          'Chưa chạy trên Pi, không sửa chương trình đo hoặc chính sách đang hoạt động.']
    (args.out/'KET_QUA.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(args.out,flush=True)


if __name__=='__main__':main()
