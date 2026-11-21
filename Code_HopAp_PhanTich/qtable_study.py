"""Offline design study ONLY. No GPIO; all plant parameters are assumed.

Run: python qtable_study.py --episodes 10000
Then: python qtable_study.py --test
Requires numpy, numba, matplotlib. No incubating eggs are used.
"""
from pathlib import Path
import argparse
import csv
import json
import time
import numpy as np
from numba import njit

OUT = Path(__file__).parent / 'results'
TARGET = 37.5
EDGES = np.array([-3., -1.5, -.6, -.2, .2, .5, .8, 1.])
HEAT = np.array([0., .35, 1.])  # illustrative, must be identified on hardware
FAN = np.array([.5, .75, 1.])   # no stopping the circulation fan
NAMES = ['mae_after_300s_C', 'in_band_after_300s_pct', 'hot_area_C_min',
         'max_T_C', 'estimated_energy_Wh', 'first_in_band_s',
         'guard_control_steps', 'heater_change_sum', 'fallback_steps',
         'rms_error_after_300s_C']


@njit(cache=True)
def state_id(temp, old_temp, memory, mode):
    b = np.searchsorted(EDGES, temp - TARGET, side='right')
    if mode == 0:
        return b
    delta = temp - old_temp
    tr = 0 if delta < -.08 else (2 if delta > .08 else 1)
    if mode == 1:
        return b * 3 + tr
    # Separate rapid trends from slow drift when anticipating stored heat.
    tr5 = 0 if delta < -.3 else (1 if delta < -.08 else (
        2 if delta <= .08 else (3 if delta <= .3 else 4)))
    mem = 0 if memory < .2 else (2 if memory > .65 else 1)
    return (b * 5 + tr5) * 3 + mem


@njit(cache=True)
def sample_params():
    # air/wall effective capacity, four dummy eggs + bowl thermal mass,
    # wall/vent loss, air/load coupling, heater lag, sensor lag,
    # passive evaporation heat loss, circulation effect on wall losses.
    return np.array([np.random.uniform(90., 170.), np.random.uniform(800., 1500.),
                     np.random.uniform(.50, .90), np.random.uniform(.6, 1.2),
                     np.random.uniform(3., 12.), np.random.uniform(4., 14.),
                     np.random.uniform(.1, .5), np.random.uniform(.05, .20)])


@njit(cache=True)
def physical_step(ta, tm, h, sensor, filt, uh, uf, p, ambient, door_open, leak):
    # One simulated second. Internal fan affects mixing/coupling, NOT a fictitious
    # independently controllable exhaust flow. Heat loss remains to ambient.
    h += (uh - h) * (1. - np.exp(-1. / p[4]))
    coupling = p[3] * (.3 + .9 * uf)
    loss = p[2] * (1. + p[7] * (uf - .5)) * leak
    if door_open:
        loss += 5.
    power = 21. * h + 1.8 * uf
    exchange = coupling * (ta - tm)
    ta += (power - loss * (ta - ambient) - exchange - p[6]) / p[0]
    tm += exchange / p[1]
    sensor += (ta - sensor) * (1. - np.exp(-1. / p[5]))
    observed = np.round((sensor + np.random.normal(0., .025)) / .0625) * .0625
    filt += .4 * (observed - filt)
    return ta, tm, h, sensor, filt


@njit(cache=True)
def train(episodes, mode, joint, whot, wenergy, seed):
    np.random.seed(seed)
    ns = 9 if mode == 0 else (27 if mode == 1 else 135)
    na = 9 if joint else 3
    q = np.zeros((ns, na))
    visits = np.zeros((ns, na), dtype=np.int64)
    rewards = np.zeros(episodes)
    steps = 240  # 20 simulated minutes, control every 5 seconds
    for ep in range(episodes):
        p = sample_params()
        ambient = np.random.uniform(24., 33.)
        if np.random.random() < .55:
            ta = np.random.uniform(36.4, 38.1)
            tm = ta - np.random.uniform(0., .5)
        else:
            ta = np.random.uniform(ambient, 36.4)
            tm = ta
        h = 0.
        sensor = ta
        filt = ta
        previous = ta
        older = ta
        memory = 0.
        last_uh = 0.
        door_start = np.random.randint(30, 180)
        with_door = np.random.random() < .6
        changed_loss = np.random.random() < .4
        epsilon = max(.03, 1. - .97 * ep / max(1., episodes * .8))
        alpha = max(.03, .2 - .17 * ep / max(1., episodes * .8))
        gamma = .99
        s = state_id(filt, older, memory, mode)
        total = 0.
        for k in range(steps):
            start_temp = filt
            if np.random.random() < epsilon:
                a = np.random.randint(na)
            else:
                # Randomize ties during training to avoid fixed action-0 bias.
                best = np.max(q[s])
                ids = np.where(q[s] >= best - 1e-10)[0]
                a = ids[np.random.randint(len(ids))]
            ih = a // 3 if joint else a
            jf = a % 3 if joint else 0
            uh = HEAT[ih]
            uf = FAN[jf]
            cost = 0.
            energy = 0.
            intervened = False
            for second in range(5):
                # Simulation guard only; not a validated live-egg safety value.
                actual_h = uh
                actual_f = uf
                if filt >= 38.5:
                    actual_h = 0.
                    actual_f = FAN[0]
                    intervened = True
                ta, tm, h, sensor, filt = physical_step(
                    ta, tm, h, sensor, filt, actual_h, actual_f, p, ambient,
                    with_door and door_start <= k < door_start + 2,
                    1.25 if changed_loss and k >= 120 else 1.)
                memory += (actual_h - memory) * (1. - np.exp(-1. / 15.))
                err = filt - TARGET
                cost += abs(err) / .5 + whot * (max(0., err - .3) / .5) ** 2
                energy += (21. * actual_h + 1.8 * actual_f) / 21.
            reward = -cost / 5. - wenergy * energy / 5. - .01 * abs(uh - last_uh)
            if intervened:
                reward -= 50.
            sn = state_id(filt, previous, memory, mode)
            q[s, a] += alpha * (reward + gamma * np.max(q[sn]) - q[s, a])
            visits[s, a] += 1
            total += reward
            older, previous = previous, start_temp
            last_uh = uh
            s = sn
        # A fixed-duration rollout is a time truncation: bootstrap is retained.
        # Guard intervention does not end the episode and cannot be used to escape
        # a long sequence of negative rewards.
        rewards[ep] = total
    return q, visits, rewards


@njit(cache=True)
def rollout(q, visits, mode, joint, controller, ctl, p, ambient, initial, kind,
            seed, horizon=1800):
    np.random.seed(seed)
    ta = initial
    tm = initial
    h = 0.
    sensor = initial
    filt = initial
    older = initial
    previous = initial
    memory = 0.
    last_uh = 0.
    heat_on = initial < TARGET
    integ = 0.
    trace = np.zeros((horizon // 5, 8))
    sum_abs = sum_sq = count_band = 0.
    hot_area = energy = changes = 0.
    max_t = -100.
    guard_steps = fallback_steps = 0
    first = float(horizon)
    nsteady = 0
    for k in range(horizon // 5):
        start_temp = filt
        if controller == 0:
            band = ctl[0]
            center = TARGET + ctl[1]
            if filt <= center - band:
                heat_on = True
            elif filt >= center + band:
                heat_on = False
            uh = 1. if heat_on else 0.
            uf = FAN[0]
        elif controller == 1:
            err = TARGET - filt
            deriv = (filt - previous) / 5.
            proposal = integ + ctl[1] * err * 5.
            u_raw = ctl[0] * err + proposal - ctl[2] * deriv
            # Conditional-integration anti-windup.
            if not ((u_raw > 1. and err > 0.) or (u_raw < 0. and err < 0.)):
                integ = proposal
            uh = min(1., max(0., ctl[0] * err + integ - ctl[2] * deriv))
            uf = FAN[0]
        else:
            s = state_id(filt, older, memory, mode)
            if np.sum(visits[s]) == 0:
                # Explicitly counted rule fallback, never described as learned.
                ih = 0 if filt >= TARGET else 1
                jf = 0
                fallback_steps += 1
            else:
                best_value = -1e100
                a = 0
                for j in range(q.shape[1]):
                    if visits[s, j] > 0 and q[s, j] > best_value:
                        a = j
                        best_value = q[s, j]
                ih = a // 3 if joint else a
                jf = a % 3 if joint else 0
            uh = HEAT[ih]
            uf = FAN[jf]
        changes += abs(uh - last_uh)
        intervened = False
        applied_h = 0.
        applied_f = 0.
        for second in range(5):
            now = k * 5 + second
            actual_h = uh
            actual_f = uf
            if filt >= 38.5:
                actual_h = 0.
                actual_f = FAN[0]
                intervened = True
            amb = ambient + (2. if kind == 3 and now >= 600 else 0.)
            door = kind == 1 and 600 <= now < 610
            leak = 1.35 if kind == 2 and now >= 600 else 1.
            ta, tm, h, sensor, filt = physical_step(
                ta, tm, h, sensor, filt, actual_h, actual_f, p, amb, door, leak)
            memory += (actual_h - memory) * (1. - np.exp(-1. / 15.))
            applied_h += actual_h
            applied_f += actual_f
            energy += (21. * actual_h + 1.8 * actual_f) / 3600.
            max_t = max(max_t, ta)
            hot_area += max(0., ta - (TARGET + .5)) / 60.
            if first == horizon and abs(ta - TARGET) <= .5:
                first = float(now)
            if now >= 300:
                err_true = ta - TARGET
                sum_abs += abs(err_true)
                sum_sq += err_true ** 2
                count_band += abs(err_true) <= .5
                nsteady += 1
        guard_steps += intervened
        trace[k] = np.array([(k+1)*5., ta, filt, tm, applied_h/5., applied_f/5., memory,
                             1. if intervened else 0.])
        older, previous = previous, start_temp
        last_uh = uh
    metrics = np.array([sum_abs/nsteady, count_band/nsteady*100., hot_area,
                        max_t, energy, first, guard_steps, changes, fallback_steps,
                        np.sqrt(sum_sq/nsteady)])
    return metrics, trace


@njit(cache=True)
def scenario_bank(n, seed, stress=False):
    np.random.seed(seed)
    params = np.zeros((n, 8))
    ambient = np.zeros(n)
    initial = np.zeros(n)
    kind = np.zeros(n, dtype=np.int64)
    noise_seed = np.zeros(n, dtype=np.int64)
    for i in range(n):
        params[i] = sample_params()
        ambient[i] = np.random.uniform(25., 32.)
        initial[i] = ambient[i] if i % 4 == 0 else 37.
        kind[i] = i % 4
        if stress and i % 5 == 0:
            params[i, 0] *= 1.15
            params[i, 1] *= 1.15
        noise_seed[i] = 100000 + seed * 100 + i
    return params, ambient, initial, kind, noise_seed


def evaluate(bank, q=None, visits=None, mode=2, joint=True, controller=2, ctl=None):
    if q is None:
        q = np.zeros((81, 9))
        visits = np.zeros((81, 9), dtype=np.int64)
    if ctl is None:
        ctl = np.zeros(3)
    p, amb, initial, kind, seed = bank
    return np.array([rollout(q, visits, mode, joint, controller, ctl,
                            p[i], amb[i], initial[i], kind[i], seed[i])[0]
                     for i in range(len(amb))])


def score(m):
    # Validation ranking is independent of the varying reward functions.
    failed = np.mean((m[:, 3] > 38.5) | (m[:, 6] > 0))
    quality = float(m[:, 0].mean() + .15 * m[:, 2].mean())
    return (float(failed), quality, float(m[:, 4].mean()))


def summary(m):
    result = {name: float(m[:, i].mean()) for i, name in enumerate(NAMES)}
    result['MAE_sd_across_scenarios_C'] = float(m[:, 0].std())
    result['worst_T_C'] = float(m[:, 3].max())
    result['guard_episode_fraction'] = float(np.mean(m[:, 6] > 0))
    result['true_over_38_5_fraction'] = float(np.mean(m[:, 3] > 38.5))
    return result


def design(episodes):
    OUT.mkdir(parents=True, exist_ok=True)
    val = scenario_bank(40, 440)
    records = []
    # Tune the simple controller instead of deliberately choosing a poor band.
    candidates = []
    for band in [.05, .1, .2, .3, .5]:
        for offset in [-.4, -.2, 0., .2]:
            m = evaluate(val, controller=0, ctl=np.array([band, offset, 0.]))
            candidates.append((score(m), band, offset, summary(m)))
    _, band, offset, stats = min(candidates)
    records.append({'name':'thermostat', 'band':band, 'offset':offset,'validation':stats})
    print('BEST thermostat', band, offset, stats, flush=True)
    candidates = []
    for kp in [.1, .3, .7]:
        for ki in [.0003, .001, .003]:
            for kd in [0., 2., 8.]:
                ctl = np.array([kp, ki, kd])
                m = evaluate(val, controller=1, ctl=ctl)
                candidates.append((score(m), (kp,ki,kd), summary(m)))
    _, gains, stats = min(candidates)
    records.append({'name':'pid', 'gains':gains, 'validation':stats})
    print('BEST PID', gains, stats, flush=True)

    for mode, joint, label in [(0, True, 'T_only_joint'),
                                (1, True, 'T_trend_joint'),
                                (2, True, 'T_trend_memory_joint'),
                                (2, False, 'T_trend_memory_heater_only')]:
        candidates = []
        for whot in [1., 3.]:
            for wenergy in [.02, .1]:
                all_m = []
                for seed in [11, 22, 33]:
                    begin = time.time()
                    q, visits, rewards = train(episodes, mode, joint, whot, wenergy, seed)
                    tag=f'{label}_hot{whot:g}_energy{wenergy:g}_seed{seed}'
                    np.savez(OUT/f'{tag}_SIM_ONLY.npz',q=q,visits=visits,rewards=rewards)
                    m=evaluate(val,q,visits,mode,joint)
                    all_m.append(m)
                    print(tag, 'validation MAE',round(m[:,0].mean(),4),
                          'guard episodes',round(np.mean(m[:,6]>0),3),
                          'seconds',round(time.time()-begin,1),flush=True)
                metrics=np.concatenate(all_m)
                candidates.append((score(metrics),whot,wenergy,summary(metrics)))
        _,whot,wenergy,stats=min(candidates)
        record={'name':label,'mode':mode,'joint':joint,'whot':whot,'wenergy':wenergy,
                'seeds':[11,22,33],'episodes':episodes,'validation':stats}
        records.append(record)
        print('SELECTED',record,flush=True)
    report={'evidence':'ASSUMED SIMULATION ONLY; not fitted to this box; no hatch claims',
            'validation_seed':440,'validation_scenarios':40,'selected':records,
            'action_heat':HEAT.tolist(),'action_fan':FAN.tolist(),
            'state_error_edges':EDGES.tolist(),'target':TARGET,
            'state_counts':{'T_only':9,'T_trend':27,'T_trend_memory':135},
            'trend_edges_delta_T_over_10s':[-.3,-.08,.08,.3],
            'memory_thresholds':[.2,.65],'history_tau_s':15.,
            'alpha_schedule':[.2,.03],'gamma':.99,'epsilon_schedule':[1.,.03],
            'guard_C_SIM_ONLY':38.5}
    (OUT/'selected_on_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


def test():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cfg=json.loads((OUT/'selected_on_validation.json').read_text(encoding='utf-8'))
    bank=scenario_bank(40,909,True)
    records=[]
    rows=[]
    traces={}
    for spec in cfg['selected']:
        name=spec['name']
        if name=='thermostat':
            m=evaluate(bank,controller=0,ctl=np.array([spec['band'],spec['offset'],0.]))
            args=(np.zeros((81,9)),np.zeros((81,9),dtype=np.int64),2,True,0,np.array([spec['band'],spec['offset'],0.]))
        elif name=='pid':
            m=evaluate(bank,controller=1,ctl=np.array(spec['gains']))
            args=(np.zeros((81,9)),np.zeros((81,9),dtype=np.int64),2,True,1,np.array(spec['gains']))
        else:
            all_m=[]
            seed_means=[]
            for seed in spec['seeds']:
                tag=f'{name}_hot{spec["whot"]:g}_energy{spec["wenergy"]:g}_seed{seed}'
                model=np.load(OUT/f'{tag}_SIM_ONLY.npz')
                single=evaluate(bank,model['q'],model['visits'],spec['mode'],spec['joint'])
                all_m.append(single);seed_means.append(float(single[:,0].mean()))
                if seed==spec['seeds'][0]:
                    args=(model['q'],model['visits'],spec['mode'],spec['joint'],2,np.zeros(3))
            m=np.concatenate(all_m)
            spec['test_MAE_by_training_seed']=seed_means
        stats=summary(m)
        records.append({'name':name,'test':stats,'config':spec})
        for j,one in enumerate(m):
            rows.append([name,j]+one.tolist())
        print('TEST',name,stats,flush=True)
        # All examples use the same predeclared scenario and noise seed, not a
        # hand-picked case where a particular policy happens to look best.
        ix=1
        traces[name]=rollout(*args,bank[0][ix],bank[1][ix],bank[2][ix],bank[3][ix],bank[4][ix])[1]
    output={'evidence':cfg['evidence'],'test_seed':909,'test_scenarios':40,'results':records}
    (OUT/'held_out_test.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    with (OUT/'held_out_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['controller','rollout_id']+NAMES);w.writerows(rows)
    fig,axs=plt.subplots(2,1,figsize=(11,7),sharex=True)
    for name in ['thermostat','pid','T_trend_memory_joint']:
        tr=traces[name]
        axs[0].plot(tr[:,0]/60,tr[:,1],label=name,lw=1.4)
        axs[1].plot(tr[:,0]/60,tr[:,4],label=name,lw=1.1)
    axs[0].axhline(TARGET,color='k',ls='--',lw=.8)
    axs[0].axhspan(37.,38.,color='green',alpha=.08)
    axs[0].axvspan(10.,10.+10./60,color='gray',alpha=.3)
    axs[0].set_ylabel('Air temperature (C)');axs[1].set_ylabel('Heater duty')
    axs[1].set_xlabel('Simulated minutes');axs[0].legend(fontsize=8)
    axs[0].set_title('ASSUMED SIMULATION ONLY - fixed held-out door-opening scenario')
    for ax in axs: ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'comparison_SIM_ONLY.png',dpi=160);plt.close(fig)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--episodes',type=int,default=10000)
    ap.add_argument('--test',action='store_true')
    args=ap.parse_args()
    test() if args.test else design(args.episodes)
