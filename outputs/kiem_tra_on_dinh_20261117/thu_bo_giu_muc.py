from pathlib import Path
import json,sys,random,statistics,math,itertools,csv
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Code_HopAp_Demo'))
import phan_tich_reward as study
import toi_uu_rl_offline as rl
from bo_giu_muc_thu_nghiem import HoldLevels
from chinh_sach_nhiet import SoftGuard
sys.stdout.reconfigure(encoding='utf-8')
p=json.loads(Path('Code_HopAp_Demo/goi_thu_rl_20261117.json').read_text(encoding='utf-8'))
model=study.ThermalModel(**p['model']);actions=p['actions'];pol=p['policy']
paths=[Path('Du_lieu_giu_nhiet/20261117_084602_831190/du_lieu.csv'),Path('Du_lieu_giu_nhiet/ket_qua_giu_nhiet/20261117_092305_477345/du_lieu.csv')]
banks=[];initials=[]
for path in paths:
 s=study.read_log(path);raw=list(csv.DictReader(path.open(encoding='utf-8-sig')))
 start=min(float(r['elapsed_s']) for r in raw if r['event']=='COMMAND' and r['phase'].startswith('kiem_tra'));end=min(float(r['elapsed_s']) for r in raw if r['event']=='STOP')
 rows=[r for r in study.transitions(s,25) if start-5<=r['t'] and r['t']+5<=end]
 banks.append([r['next_temperature']-model.step(r['temperature'],r['previous_delta'],r['memory_before'],r['h'],r['f'])[0] for r in rows])
 initials.append(rows[0])
rng=random.Random(171730);cases=[]
for i in range(64):
 bank=banks[i%2];noise=[]
 while len(noise)<120:
  at=rng.randrange(len(bank)-5);noise.extend(bank[at:at+6])
 cases.append((initials[i%2],noise[:120]))

def run(config,case):
 initial,noise=case;t,d,m=initial['temperature'],initial['previous_delta'],initial['memory_before']
 guard=SoftGuard();supervisor=HoldLevels(config,actions);ae=inband=guardsteps=0;changes=fc=0;previous=None;longest=span=0
 for k in range(120):
  now=k*5
  if guard.update(t):
   j=supervisor.protection(now);guardsteps+=1
  else:
   st=rl.state(t,d,m,False,37.5,.5,1)
   try:j=supervisor.select(now,t,pol['q'][st],pol['visits'][st])
   except ValueError:return (5,0,999,999,0,1)
  if previous is not None and j!=previous:
   changes+=1;fc+=actions[j][1]!=actions[previous][1];longest=max(longest,span);span=0
  span+=5;previous=j
  t,d,m=model.step(t,d,m,*actions[j],noise[k]);ae+=abs(t-37.5);inband+=abs(t-37.5)<=.5
  if not model.low<=t<=model.high:return (5,0,999,999,0,1)
 return (ae/120,inband/120*100,changes,fc,max(longest,span),guardsteps/120)

results=[]
for dwell,fan,band in itertools.product((15,20,30),(30,60),(.1,.15)):
 c=dict(lamp_hold_s=dwell,fan_hold_s=fan,stable_band_c=band,stable_trend_c_per_min=.15,trend_window_s=20,max_lamp_step=.25)
 vals=[run(c,case) for case in cases];v=[statistics.mean(row[i] for row in vals) for i in range(6)]
 print(c,'MAE BAND CHG FAN LONG GUARD',*[round(x,3) for x in v],flush=True)
 results.append(dict(config=c,mean_mae_c=v[0],mean_in_band_pct=v[1],mean_changes=v[2],
                     mean_fan_changes=v[3],mean_longest_joint_hold_s=v[4],mean_guard_rate=v[5]))
Path(__file__).with_name('thu_giu_muc_MO_PHONG.json').write_text(json.dumps(dict(
 status='REJECTED_NOT_FOR_HARDWARE',evidence='frozen model with residual block resampling; NOT new hardware observations',
 cases=64,seed=171730,trials=results),indent=2),encoding='utf-8')
