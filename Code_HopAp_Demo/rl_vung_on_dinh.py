"""Pure state/reward for a NEW band controller. No GPIO and no policy deployment."""
TARGET = 37.5
BAND = .2
STATE_COUNT = 2430  # 9 errors x 3 trends x 5 memories x 9 previous actions x 2 guards


def state_id(temperature, delta, memory, previous_action, guard):
    e = temperature-37.5
    b = 0
    for edge in (-.6,-.3,-.2,-.08,.08,.2,.3,.6):
        if e >= edge:
            b += 1
    trend = 0 if delta < -.03 else 2 if delta > .03 else 1
    stored = 0
    for edge in (.25,.45,.55,.75):
        if memory >= edge:
            stored += 1
    return ((((b*3+trend)*5+stored)*9+previous_action)*2+int(guard))


def reward(before, after, heat, fan, old_heat, old_fan, switch_weight, recovery_weight, triggered):
    # A change is permitted inside the band; its cost competes with future exits.
    e = abs(after-37.5)
    outside = max(0.,e-.2)/.2
    previous_outside = max(0.,abs(before-37.5)-.2)/.2
    inside = e <= .2+1e-9
    value = (1.-.5*(e/.2)**2 if inside else -1.-recovery_weight*outside-2.*outside**2)
    value += .5*(previous_outside-outside)
    changed = heat != old_heat or fan != old_fan
    change = (1. if changed else 0.)+abs(heat-old_heat)+.5*abs(fan-old_fan)
    # Less switching cost outside the region: recovering must remain possible.
    value -= switch_weight*(1. if inside else .15)*change
    if triggered:
        value -= 25.
    return value
