#!/usr/bin/env python3
"""Thử Q-table mới 10 phút trên hộp rỗng, có giám sát; không học online."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import do_nhiet_hop as core
from chinh_sach_nhiet import SoftGuard
from rl_vung_on_dinh import state_id

PACKAGE_SHA256 = '882c7746f332a1a99985bc6c269c516cd1210f741f5204b164d9cdd0cec787b8'
DATA_SHA256 = '31b35425b9d9a143d90277a2d8cbe8845eae21fdbf412479ab50738bfe6e5847'
ACTIONS = [[0.,.75],[0.,1.],[.25,.75],[.25,1.],[.5,.75],[.5,1.],[.75,.75],[.75,1.],[1.,.75]]
RECOVERY_ENTER_C = 36.6  # Lower end of simulated training starts, not a learned cutoff.
RECOVERY_EXIT_C = 37.0   # Same handover temperature as the tested initial warm-up.
RECOVERY_TIMEOUT_S = 450.


def read_package(path):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PACKAGE_SHA256:
        raise ValueError('Gói Q khác bản đã kiểm tra; từ chối bật tải.')
    data=json.loads(raw)
    required=dict(version=1,purpose='NOV20_EMPTY_BOX_PILOT',supervised_pilot_allowed=True,
        production_deploy_allowed=False,target_c=37.5,band_c=.2,state_count=2430,
        state_encoder='band_previous_action_v1',kind='Q_5s',dt_s=5,
        sensor_id='28-000000ca6c1f',data_sha256=DATA_SHA256)
    if any(data.get(k)!=v for k,v in required.items()) or data['actions']!=ACTIONS:
        raise ValueError('Sai mục tiêu, encoder hoặc giao thức gói thử.')
    for name in ('q','visits'):
        table=data['policy'][name]
        if len(table)!=2430 or any(len(row)!=9 for row in table):
            raise ValueError('Sai kích thước Q/visits.')
        if name=='q' and any(not isinstance(v,(int,float)) or not math.isfinite(v) for row in table for v in row):
            raise ValueError('Q không hữu hạn.')
        if name=='visits' and any(type(v) is not int or v<0 for row in table for v in row):
            raise ValueError('Visits không hợp lệ.')
    return data


class NewPilot:
    def __init__(self,package):
        self.package=package
        self.guard=SoftGuard()
        self.started=self.hold_started=self.last_control=None
        self.sample_at=self.sample_temperature=None
        self.output_at=None;self.last_heat=0.;self.memory=0.;self.previous=1
        self.sensor_bound=False;self.completed=False;self.decision=None
        self.decisions=0;self.states=set();self.initial_temperature=None
        self.recovery_started=None;self.recovery_count=0;self.recovery_total_s=0.
        self.recovery_reason=None;self.last_now=None

    def bind_sensor(self,sensor_id):
        if sensor_id!=self.package['sensor_id']:
            raise core.SensorError('Đầu dò khác dữ liệu huấn luyện; dừng.')
        self.sensor_bound=True

    def observe_output(self,now,lamp_pct,fan_pct):
        if not all(math.isfinite(v) for v in (now,lamp_pct,fan_pct)):
            raise ValueError('Lệnh đầu ra không hữu hạn.')
        if not (0<=lamp_pct<=100 and 0<=fan_pct<=100):
            raise ValueError('Duty ngoài miền.')
        if self.output_at is not None:
            dt=now-self.output_at
            if dt<0:raise ValueError('Thời gian điều khiển đi lùi.')
            self.memory+=(self.last_heat-self.memory)*(-math.expm1(-dt/self.package['model']['tau']))
        self.output_at=now;self.last_heat=lamp_pct/100
        self.previous=min(range(9),key=lambda i:abs(ACTIONS[i][0]-lamp_pct/100)+abs(ACTIONS[i][1]-fan_pct/100))

    def __call__(self,now,reading):
        t=reading.temperature
        if not self.sensor_bound or self.output_at is None:
            raise core.SensorError('Chưa liên kết cảm biến hoặc lệnh đầu ra.')
        if t is None or not math.isfinite(t) or not math.isfinite(reading.at) or not 0<=now-reading.at<3:
            raise core.SensorError('Số đo nhiệt không hợp lệ/quá hạn.')
        self.last_now=now
        if self.started is None:
            if t>30:raise ValueError('Hộp còn trên 30°C; để nguội rồi chạy lại.')
            self.started=now;self.initial_temperature=t
        was_guard=self.guard.active;self.guard.update(t)
        if self.hold_started is None:
            if now-self.started>=900:raise ValueError('Hết 900s làm ấm; dừng.')
            if not self.guard.active and t>=37:
                self.hold_started=now
            else:
                # Keep a fresh, approximately 5s trend across the warm/hold transition.
                if self.sample_at is None or reading.at-self.sample_at>=5:
                    self.sample_at=reading.at;self.sample_temperature=t
                return core.AutoDecision('lam_am_rl_moi',0 if self.guard.active else 75,100,
                    'Làm ấm tối đa 900s; chưa tính 600s kiểm tra.')
        if now-self.hold_started>=600:
            self.finish_recovery(now)
            self.completed=True
            return None
        if self.guard.active:
            self.finish_recovery(now)
            self.last_control=None
            return core.AutoDecision('kiem_tra_rl_moi_bao_ve',0,100,'Ngắt mềm 38→37°C; vẫn tính thời gian giữ nhiệt.')
        if was_guard:self.last_control=None
        # Supervisor checks every fresh control loop, independent of the Q decision
        # period. Keep the hold clock running: recovery is part of measured quality.
        if self.recovery_started is not None or t<RECOVERY_ENTER_C:
            decision=self.recover(now,reading,'below_training_start_range')
            if decision is not None:return decision
        if self.last_control is None or now-self.last_control>=5:
            model=self.package['model']
            if not model['low']<=t<=model['high']:
                raise ValueError('Nhiệt ngoài miền mô hình; dừng, không ngoại suy.')
            d=0. if self.sample_at is None or reading.at<=self.sample_at else (t-self.sample_temperature)*5/(reading.at-self.sample_at)
            state=state_id(t,d,self.memory,self.previous,False)
            seen=[i for i,n in enumerate(self.package['policy']['visits'][state]) if n>0]
            if not seen:
                if t<RECOVERY_EXIT_C:
                    return self.recover(now,reading,'unseen_cold_state')
                raise ValueError(f'State {state} chưa học trong/gần vùng mục tiêu; dừng, không tự tăng sưởi.')
            action=max(seen,key=lambda i:self.package['policy']['q'][state][i])
            h,f=ACTIONS[action]
            self.decision=core.AutoDecision('kiem_tra_rl_moi',h*100,f*100,
                f'Q mới; state={state}; dT5={d:+.4f}; memory={self.memory:.4f}; xét 5s, phạt đổi mức; không học online.')
            self.last_control=now;self.sample_at=reading.at;self.sample_temperature=t
            self.decisions+=1;self.states.add(state)
        return self.decision

    def finish_recovery(self,now):
        if self.recovery_started is not None:
            self.recovery_total_s+=max(0.,now-self.recovery_started)
            self.recovery_started=None
            self.last_control=None

    def recover(self,now,reading,reason):
        if self.recovery_started is None:
            self.recovery_started=now;self.recovery_count+=1;self.recovery_reason=reason
        if now-self.recovery_started>=RECOVERY_TIMEOUT_S:
            raise ValueError('Làm ấm phục hồi quá 450s chưa đạt 37°C; dừng.')
        if reading.temperature>=RECOVERY_EXIT_C:
            self.finish_recovery(now)
            return None
        # Update the trend throughout recovery and preserve applied-output memory,
        # so Q receives the real incoming thermal state rather than a reset state.
        if self.sample_at is None or reading.at-self.sample_at>=5:
            self.sample_at=reading.at;self.sample_temperature=reading.temperature
        self.last_control=None
        return core.AutoDecision('kiem_tra_rl_moi_phuc_hoi',75,100,
            f'Làm ấm phục hồi ({self.recovery_reason}); lên 37°C giao lại Q; tối đa 450s; vẫn tính vào 600s thử.')

    def metadata(self):
        return dict(completed=self.completed,initial_temperature_c=self.initial_temperature,
            warm_elapsed_s=None if self.hold_started is None else self.hold_started-self.started,
            requested_hold_seconds=600,decisions=self.decisions,states=sorted(self.states),
            soft_guard_count=self.guard.count,q_updates=0,package_sha256=PACKAGE_SHA256,
            target_c=37.5,lower_c=37.3,upper_c=37.7,control_period_s=5,
            hard_cutoff_c=38.5,soft_guard_c=[38,37],supervisor_version=2,
            recovery_enter_c=RECOVERY_ENTER_C,recovery_exit_c=RECOVERY_EXIT_C,
            recovery_timeout_s=RECOVERY_TIMEOUT_S,recovery_count=self.recovery_count,
            recovery_active=self.recovery_started is not None,
            recovery_elapsed_s=self.recovery_total_s+(0. if self.recovery_started is None else max(0.,self.last_now-self.recovery_started)),
            recovery_counts_toward_hold=True)


def summarize(log,config):
    with Path(log).open(encoding='utf-8-sig',newline='') as stream:raw=list(csv.DictReader(stream))
    starts=[float(r['elapsed_s']) for r in raw if r['event']=='COMMAND' and r['phase'].startswith('kiem_tra_rl_moi')]
    if not starts:return dict(status='NO_HOLD_DATA',errors=[r['note'] for r in raw if r['event']=='ERROR'])
    start=min(starts)
    stop=min(float(r['elapsed_s']) for r in raw if r['event'] in ('STOP','ERROR','END') and float(r['elapsed_s'])>=start)
    samples=[]
    for r in raw:
        if r['event']=='MEASUREMENT' and r['temperature_c'] and 0<=float(r['temperature_age_s'])<3:
            t=float(r['elapsed_s'])-float(r['temperature_age_s']);v=float(r['temperature_c'])
            if math.isfinite(t) and math.isfinite(v) and (not samples or t>samples[-1][0]):samples.append((t,v))
    duration=inside=error=run=longest=0.;used=[]
    for (t,v),(tn,_) in zip(samples,samples[1:]):
        dt=max(0.,min(tn,stop)-max(t,start))
        if tn-t>3 or not dt:
            run=0.;continue
        ok=37.3-1e-9<=v<=37.7+1e-9
        duration+=dt;inside+=dt*ok;error+=dt*abs(v-37.5);used.append(v)
        run=run+dt if ok else 0.;longest=max(longest,run)
    commands=[r for r in raw if r['gpio_control']=='1' and r['event'] in ('COMMAND','OUTPUT_CHANGE') and start<=float(r['elapsed_s'])<stop]
    hchanges=fchanges=pchanges=0
    previous=None
    for r in commands:
        pair=float(r['lamp_command_pct']),float(r['fan_command_pct'])
        if previous is not None:
            hchanges+=pair[0]!=previous[0];fchanges+=pair[1]!=previous[1];pchanges+=pair!=previous
        previous=pair
    errors=[r['note'] for r in raw if r['event']=='ERROR']
    complete=(config['profile']['completed'] and config['hardware_program_exit_code']==0 and not errors and duration>=588)
    return dict(status='COMPLETED_PHYSICAL_PILOT' if complete else 'INCOMPLETE_PHYSICAL_PILOT',
        source_sha256=hashlib.sha256(Path(log).read_bytes()).hexdigest(),covered_s=duration,hold_span_s=stop-start,
        in_band_pct=100*inside/duration if duration else None,mae_c=error/duration if duration else None,
        min_c=min(used) if used else None,max_c=max(used) if used else None,
        lamp_changes=hchanges,fan_changes=fchanges,pair_changes=pchanges,longest_in_band_s=longest,
        soft_guard_count=config['profile']['soft_guard_count'],errors=errors,
        supervisor_version=config['profile'].get('supervisor_version',1),
        recovery_count=config['profile'].get('recovery_count',0),
        recovery_elapsed_s=config['profile'].get('recovery_elapsed_s',0.),
        note='Physical single-probe empty-box pilot; warm-up/post-cooling excluded, guard included. Initial command into hold excluded from change counts. No matched simultaneous baseline.')


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--dht11',action='store_true')
    parser.add_argument('--khong-oled',action='store_true')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args(argv)
    data=read_package(Path(__file__).with_name('goi_rl_moi_20261120.json'))
    policy=NewPilot(data)
    if args.dry_run:
        print('Q mới: 2430 states / 9 actions, 37.3–37.7°C, xét 5s, q_updates=0.\n'
              'Hộp rỗng, đầu dò đúng ID, bắt đầu <=30°C. Làm ấm <=900s, giữ 600s.\n'
              'Trong lúc giữ: dưới 36.6°C làm ấm phục hồi bóng 75%/quạt 100%; lên 37°C giao lại Q.\n'
              'State chưa học dưới 37°C cũng được làm ấm phục hồi. Tối đa 450s/lượt; vẫn tính vào 600s thử.\n'
              'Bảo vệ mềm 38→37°C, dừng 38.5°C hoặc mất số đo 3s. Không GPIO trong dry-run.')
        return 0
    folder=args.out or Path(__file__).resolve().parent/'ket_qua_rl_moi'/datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    folder.mkdir(parents=True,exist_ok=False)
    config=dict(profile=policy.metadata(),hardware_program_exit_code=None,dht11=args.dht11,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    path=folder/'cau_hinh.json'
    path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
    print(f'KẾT QUẢ: {folder}\nBắt đầu thử hộp rỗng có giám sát; Ctrl+C để dừng.',flush=True)
    command=['giu','--bong','0','--quat','100','--giay','1505','--csv',str(folder/'du_lieu.csv'),
             '--sensor',data['sensor_id'],'--ngat-nhiet','38.5','--tan-so-quat','100']
    if args.dht11:command.append('--dht11')
    if args.khong_oled:command.append('--khong-oled')
    code=core.main(command,control_policy=policy,max_session_seconds=core.MAX_SURVEY_SECONDS)
    config.update(profile=policy.metadata(),hardware_program_exit_code=code)
    path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
    if (folder/'du_lieu.csv').exists():
        result=summarize(folder/'du_lieu.csv',config)
        (folder/'ket_qua.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return code if code else 0 if policy.completed else 1


if __name__=='__main__':raise SystemExit(main())
