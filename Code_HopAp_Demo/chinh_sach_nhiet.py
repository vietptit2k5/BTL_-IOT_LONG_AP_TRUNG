"""Pure control rules shared by offline experiments and the independent Pi test."""
from dataclasses import dataclass
import math


@dataclass
class SoftGuard:
    target: float = 37.5
    band: float = .5
    active: bool = False
    count: int = 0

    def update(self, temperature):
        if not math.isfinite(temperature):
            raise ValueError('Nhiệt độ không hữu hạn.')
        if self.active:
            if temperature <= self.target - self.band:
                self.active = False
        elif temperature >= self.target + self.band:
            self.active = True
            self.count += 1
        return self.active


def nearest(actions, heat, fan):
    return min(range(len(actions)), key=lambda i: abs(actions[i][0]-heat)+abs(actions[i][1]-fan))


class ReferenceController:
    def __init__(self, config, target, actions):
        self.config, self.target, self.actions = config, target, actions
        self.heater_on = None
        self.integral = 0.

    def select(self, temperature, delta, dt=5.):
        c = self.config
        if self.heater_on is None:
            self.heater_on = temperature < self.target
        low, high = min(f for _, f in self.actions), max(f for _, f in self.actions)
        fan = (low if c['fan_mode']=='low' else high if c['fan_mode']=='high'
               else high if temperature > self.target+.2 or delta > .05 else low)
        maximum = max(h for h, _ in self.actions)
        if c['kind']=='thermostat':
            if temperature < self.target-c['band']:
                self.heater_on = True
            elif temperature > self.target+c['band']:
                self.heater_on = False
            heat = maximum if self.heater_on else 0.
        else:
            error = self.target-temperature
            proposed = self.integral+c['ki']*error*dt
            raw = c['kp']*error+proposed-c['kd']*delta/dt
            if not ((raw>maximum and error>0) or (raw<0 and error<0)):
                self.integral = proposed
            heat = min(maximum,max(0.,c['kp']*error+self.integral-c['kd']*delta/dt))
        return nearest(self.actions, heat, fan)
