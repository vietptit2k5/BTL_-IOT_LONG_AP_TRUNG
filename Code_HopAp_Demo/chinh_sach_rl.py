"""Frozen Q-policy for an explicit, supervised empty-box pilot; no learning."""
import hashlib
import json
import math
from pathlib import Path

import toi_uu_rl_offline as rl


class PilotError(RuntimeError):
    pass


def policy_digest(policy):
    return hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def read_pilot(path):
    path=Path(path)
    data=json.loads(path.read_text(encoding='utf-8'))
    if (data.get('purpose')!='SUPERVISED_EMPTY_BOX_PILOT_ONLY'
        or data.get('supervised_pilot_allowed') is not True
        or data.get('automatic_deploy_allowed') is not False
        or data.get('original_candidate_deploy_allowed') is not False):
        raise ValueError('Chỉ nhận gói pilot hộp rỗng có giám sát, không nhận Q-table tự triển khai.')
    required=dict(version=1,target_c=37.5,band_c=.5,state_count=162,dt_s=5,fan_pwm_hz=100,
                  state_encoder='9e_3d_3m_guard_v2',max_initial_temperature_c=30)
    if any(data.get(k)!=v for k,v in required.items()):
        raise ValueError('Gói pilot không khớp bộ mã hóa/giới hạn đã kiểm tra.')
    if data['independent_validation'].get('status')!='PASS_SHORT_HORIZON_ONLY':
        raise ValueError('Thiếu kiểm tra ngắn hạn trên lượt giữ nhiệt độc lập.')
    actions=data['actions'];policy=data['policy'];n=len(actions)
    if n!=9 or len({tuple(a) for a in actions})!=n or any(
        len(a)!=2 or a[0] not in (0,.25,.5,.75,1) or a[1] not in (.75,1) or a==[1,1]
        for a in actions) or [0.,1.] not in actions:
        raise ValueError('Action pilot khác tập chín tổ hợp đã được kiểm tra.')
    if policy.get('seed')!=11 or data.get('policy_sha256')!=policy_digest(policy):
        raise ValueError('Policy đã bị thay đổi hoặc không phải seed pilot cố định 11.')
    for key in ('q','visits'):
        table=policy[key]
        if len(table)!=162 or any(len(row)!=n for row in table):
            raise ValueError('Sai kích thước bảng Q/visits.')
        if key=='q' and any(not isinstance(v,(int,float)) or not math.isfinite(v) for row in table for v in row):
            raise ValueError('Bảng Q có giá trị không hữu hạn.')
        if key=='visits' and any(type(v) is not int or v<0 for row in table for v in row):
            raise ValueError('Bảng số lần thăm không hợp lệ.')
    model=data['model']
    if not all(isinstance(model[k],(int,float)) and math.isfinite(model[k]) for k in ('low','high','tau')):
        raise ValueError('Miền mô hình không hợp lệ.')
    if not (0<model['tau']<=120 and model['low']<=37 and 38<=model['high']<=40):
        raise ValueError('Miền mô hình không chứa vùng thử nhiệt.')
    data['_package_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return data


class FrozenPilot:
    def __init__(self,package):
        self.package=package
        self.actions=package['actions']
        self.policy=package['policy']
        self.memory=0.
        self.last_time=None
        self.last_heat=0.
        self.sensor_bound=False
        self.decisions=0
        self.states=set()

    def bind_sensor(self,sensor_id):
        if sensor_id!=self.package['sensor_id']:
            raise PilotError('Đầu dò khác lượt kiểm tra mô hình; chưa chạy RL.')
        self.sensor_bound=True

    def check_initial(self,temperature):
        if temperature>self.package['max_initial_temperature_c']:
            raise PilotError('Hộp còn trên 30°C. Để nguội gần 26–27°C như lượt đối chứng rồi chạy lại pilot.')

    def observe_output(self,now,lamp_pct,fan_pct):
        if not all(math.isfinite(v) for v in (now,lamp_pct,fan_pct)):
            raise PilotError('Không nhận được trạng thái lệnh đầu ra hợp lệ.')
        if not 0<=lamp_pct<=100 or not 0<=fan_pct<=100:
            raise PilotError('Duty đầu ra ngoài giới hạn.')
        if self.last_time is not None:
            dt=now-self.last_time
            if dt<0:
                raise PilotError('Đồng hồ điều khiển không tăng.')
            self.memory+=(self.last_heat-self.memory)*(-math.expm1(-dt/self.package['model']['tau']))
        self.last_time=now
        self.last_heat=lamp_pct/100

    def select(self,temperature,delta):
        if not self.sensor_bound or self.last_time is None:
            raise PilotError('Chưa liên kết cảm biến/quan sát đầu ra; cần chép đầy đủ phiên bản code mới.')
        if not all(math.isfinite(v) for v in (temperature,delta,self.memory)):
            raise PilotError('State RL không hữu hạn.')
        if not self.package['model']['low']<=temperature<=self.package['model']['high']:
            raise PilotError('Nhiệt ngoài miền mô hình; dừng pilot, không ngoại suy Q-table.')
        s=rl.state(temperature,delta,self.memory,False,37.5,.5,max(h for h,f in self.actions))
        seen=[i for i,n in enumerate(self.policy['visits'][s]) if n]
        if not seen:
            raise PilotError(f'State {s} chưa được học; dừng pilot, không bật sưởi bằng action phỏng đoán.')
        i=max(seen,key=lambda i:self.policy['q'][s][i])
        self.decisions+=1;self.states.add(s)
        return i,s

    def metadata(self):
        return dict(seed=11,package_sha256=self.package.get('_package_sha256'),decisions=self.decisions,
            visited_states=sorted(self.states),q_updates=0,heater_memory=self.memory,
            observer_source='applied PWM command, not measured heater power',automatic_deploy_allowed=False)
