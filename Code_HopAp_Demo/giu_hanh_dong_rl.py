"""Timing contract for experimental temporally extended RL actions. No GPIO."""
DT_S = 5.
INSIDE_STEPS = 6  # 30s nominal commitment while remaining inside the requested band
OUTSIDE_STEPS = 2  # 10s nominal recovery decision interval


def in_band(temperature,target,band):
    return abs(temperature-target) <= band+1e-9


def action_steps(temperature,target,band,guard):
    if guard:
        return 1
    return INSIDE_STEPS if abs(temperature-target) <= band+1e-9 else OUTSIDE_STEPS


def interrupt_action(before,after,target,band,guard_after):
    # End on region transition, so stored heat can be handled before the next long hold.
    return guard_after or (abs(before-target)<=band+1e-9) != (abs(after-target)<=band+1e-9)
