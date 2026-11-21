"""REJECTED EXPERIMENT: stateful command holding for RL + supervisor.

This changes the complete policy; old RL hardware results do not validate it.
Offline tests degraded thermal control; this class is NOT used by any Pi runner.
Independent thermal/sensor protection must remain outside this class.
"""
from collections import deque
import math


class HoldLevels:
    def __init__(self,config,actions):
        self.config=dict(config);self.actions=actions
        bounds=dict(lamp_hold_s=(10,60),fan_hold_s=(30,120),stable_band_c=(.05,.2),
            stable_trend_c_per_min=(.05,.3),trend_window_s=(10,30),max_lamp_step=(.25,.5))
        for k,(lo,hi) in bounds.items():
            v=self.config[k]
            if not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:
                raise ValueError(f'Tham số giữ mức {k} không hợp lệ.')
        self.current=None
        self.last_lamp_change=self.last_fan_change=None
        self.points=deque()
        self.stable_holds=self.dwell_holds=self.lamp_changes=self.fan_changes=0
        self.last_reason='INIT'
        self.last_trend=None

    def _observe_temperature(self,now,temperature):
        if self.points and now<self.points[-1][0]:
            raise ValueError('Đồng hồ giữ mức không tăng.')
        if not self.points or now>self.points[-1][0]:
            self.points.append((now,temperature))
        while self.points and now-self.points[0][0]>self.config['trend_window_s']+1e-8:
            self.points.popleft()
        if len(self.points)<3 or self.points[-1][0]-self.points[0][0]<10:
            return None
        mt=sum(t for t,_ in self.points)/len(self.points)
        mv=sum(v for _,v in self.points)/len(self.points)
        den=sum((t-mt)**2 for t,_ in self.points)
        return 60*sum((t-mt)*(v-mv) for t,v in self.points)/den

    def _apply(self,index,now):
        if self.current is None:
            self.last_lamp_change=self.last_fan_change=now
        else:
            old,new=self.actions[self.current],self.actions[index]
            if old[0]!=new[0]:
                self.last_lamp_change=now;self.lamp_changes+=1
            if old[1]!=new[1]:
                self.last_fan_change=now;self.fan_changes+=1
        self.current=index
        return index

    def select(self,now,temperature,values,visits):
        if not math.isfinite(now) or not math.isfinite(temperature):
            raise ValueError('Dữ liệu giữ mức không hữu hạn.')
        seen=[i for i,n in enumerate(visits) if n>0]
        if not seen:
            raise ValueError('State chưa học; bộ giữ mức không được che giấu lỗi này.')
        trend=self._observe_temperature(now,temperature)
        self.last_trend=trend
        if self.current is None:
            self.last_reason='FIRST_Q_ACTION'
            return self._apply(max(seen,key=lambda i:values[i]),now)
        error=abs(temperature-37.5)
        if error<=self.config['stable_band_c'] and trend is not None and abs(trend)<=self.config['stable_trend_c_per_min']:
            self.stable_holds+=1;self.last_reason='HOLD_STABLE'
            return self.current
        current=self.actions[self.current]
        eligible=[]
        for i in seen:
            h,f=self.actions[i]
            if h!=current[0] and now-self.last_lamp_change<self.config['lamp_hold_s']-1e-8:
                continue
            if f!=current[1] and now-self.last_fan_change<self.config['fan_hold_s']-1e-8:
                continue
            # Limit changes near the target; allow stronger recovery when well below it.
            if error<=.3 and abs(h-current[0])>self.config['max_lamp_step']+1e-8:
                continue
            eligible.append(i)
        if not eligible:
            self.dwell_holds+=1;self.last_reason='HOLD_DWELL'
            return self.current
        selected=max(eligible,key=lambda i:values[i])
        self.last_reason='Q_WITH_HOLD_LIMITS' if selected!=self.current else 'KEEP_CURRENT_Q'
        return self._apply(selected,now)

    def protection(self,now):
        """Record the external safety override immediately, ignoring every hold constraint."""
        safe=next(i for i,a in enumerate(self.actions) if a[0]==0 and a[1]==1)
        self.last_reason='SAFETY_OVERRIDE'
        return self._apply(safe,now)

    def metadata(self):
        return dict(config=self.config,stable_hold_decisions=self.stable_holds,
            dwell_hold_decisions=self.dwell_holds,lamp_changes=self.lamp_changes,fan_changes=self.fan_changes,
            last_reason=self.last_reason,last_trend_c_per_min=self.last_trend,
            policy_type='FROZEN_Q_PLUS_STATEFUL_HOLD_SUPERVISOR',online_learning=False)
