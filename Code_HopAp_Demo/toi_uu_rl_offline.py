#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Development experiment from measured CSV. Never opens GPIO or deploys a policy.

python3 toi_uu_rl_offline.py --log FILE.csv --out NEW_FOLDER
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import sys

import phan_tich_reward as legacy
from chinh_sach_nhiet import SoftGuard, ReferenceController, nearest

DT, HORIZON = 5., 120
TRAIN_SEEDS = (11,29,47)
CHECK_SEEDS = (73,101)
VALIDATION_SEED, CHECK_SCENARIO_SEED = 140, 211217
STATE_COUNT = 162   # 9 error x 3 trend x 3 heat-memory x 2 soft-guard states.


def state(temperature, delta, memory, guard, target, band, max_heat):
    return 2*legacy.state_id(temperature,delta,memory,0,target,band,max_heat,1)+int(guard)


def epsilon_at(episode):
    return max(.03,.8*math.exp(-episode/600))


def expected_value(values, allowed, epsilon):
    return (1-epsilon)*max(values[i] for i in allowed)+epsilon*statistics.mean(values[i] for i in allowed)


def greedy(values, allowed, rng):
    best = max(values[i] for i in allowed)
    return rng.choice([i for i in allowed if abs(values[i]-best)<1e-10])


def step_reward(temperature, action, target, band, weights, triggered):
    # No switching penalty: previous action is deliberately absent from the state.
    return (-abs(temperature-target)/band
            -weights['hot']*(max(0.,temperature-target-band)/band)**2
            -weights['duty']*(action[0]+action[1])/2
            -(10. if triggered else 0.))


def train_checkpoints(model, rows, actions, target, band, algorithm, weights, seed, checkpoints):
    if algorithm not in ('q-learning','expected-sarsa'):
        raise ValueError('Thuật toán không hợp lệ.')
    if not checkpoints or any(not isinstance(ep,int) or ep<=0 for ep in checkpoints):
        raise ValueError('Mốc episode phải là các số nguyên dương.')
    rng = random.Random(seed)
    pool = legacy.training_pool(rows,target)
    if not pool:
        raise ValueError('Không có trạng thái khởi đầu gần mục tiêu trong phần train.')
    n, max_heat = len(actions), max(h for h,_ in actions)
    q = [[0.]*n for _ in range(STATE_COUNT)]
    visits = [[0]*n for _ in q]
    safe = nearest(actions,0,max(f for _,f in actions))
    all_actions = list(range(n))
    for episode in range(1,max(checkpoints)+1):
        initial = rng.choice(pool)
        t,d,m = initial['temperature'],initial['previous_delta'],initial['memory_before']
        guard = SoftGuard(target,band)
        guard.update(t)
        epsilon = epsilon_at(episode-1)
        for k in range(HORIZON):
            s = state(t,d,m,guard.active,target,band,max_heat)
            allowed = [safe] if guard.active else all_actions
            selected = rng.choice(allowed) if rng.random()<epsilon else greedy(q[s],allowed,rng)
            heat,fan = actions[selected]
            nt,nd,nm = model.step(t,d,m,heat,fan,rng.gauss(0,model.noise_sd))
            invalid = not math.isfinite(nt) or not model.low<=nt<=model.high
            previous_count = guard.count
            if not invalid:
                guard.update(nt)
            reward = (-100.*(HORIZON-k) if invalid else
                      step_reward(nt,actions[selected],target,band,weights,guard.count>previous_count))
            future = 0.
            if not invalid:
                sn = state(nt,nd,nm,guard.active,target,band,max_heat)
                next_allowed = [safe] if guard.active else all_actions
                future = (max(q[sn][i] for i in next_allowed) if algorithm=='q-learning'
                          else expected_value(q[sn],next_allowed,epsilon))
            visits[s][selected] += 1
            alpha = max(.01,.3/(1+visits[s][selected]/20)**.65)
            q[s][selected] += alpha*(reward+.98*future-q[s][selected])
            if invalid:
                break
            t,d,m = nt,nd,nm
        if episode in checkpoints:
            yield episode,q,visits


def rollout(model, actions, case, target, band, q=None, visits=None, baseline=None, trace=False):
    initial = case['initial']
    t,d,m = initial['temperature'],initial['previous_delta'],initial['memory_before']
    guard = SoftGuard(target,band)
    safe = nearest(actions,0,max(f for _,f in actions))
    controller = ReferenceController(baseline,target,actions) if baseline else None
    total_error = in_band = effort = hot_area = guard_steps = fallback = changes = 0.
    maximum,invalid,steps = t,False,0
    previous = nearest(actions,initial['h'],initial['f'])
    trace_rows = []
    for k in range(HORIZON):
        protected = guard.update(t)
        if protected:
            selected = safe
            guard_steps += 1
        elif controller:
            selected = controller.select(t,d)
        else:
            s = state(t,d,m,False,target,band,max(h for h,_ in actions))
            seen = [i for i,n in enumerate(visits[s]) if n]
            if seen:
                selected = max(seen,key=lambda i:q[s][i])
            else:
                selected = nearest(actions,0 if t>=target else .5,1.)
                fallback += 1
        heat,fan = actions[selected]
        nt,nd,nm = model.step(t,d,m,heat,fan,case['noise'][k])
        if not math.isfinite(nt):
            invalid = True
            break
        steps += 1
        maximum = max(maximum,nt)
        total_error += abs(nt-target)
        in_band += abs(nt-target)<=band
        effort += (heat+fan)/2
        hot_area += max(0.,nt-target-band)*DT/60
        changes += abs(heat-actions[previous][0])+abs(fan-actions[previous][1])
        if trace:
            trace_rows.append(dict(seconds=(k+1)*DT,simulated_temperature_c=nt,
                                   lamp_pct=heat*100,fan_pct=fan*100,soft_guard=int(protected)))
        if not model.low<=nt<=model.high:
            invalid = True
            break
        t,d,m,previous = nt,nd,nm,selected
    metrics = dict(mae_c=(total_error+5.*(HORIZON-steps))/HORIZON,
        observed_mae_c=total_error/max(1,steps),in_band_pct=100*in_band/HORIZON,
        invalid_fraction=float(invalid),guard_rate=guard_steps/HORIZON,
        guard_count=guard.count,fallback_rate=fallback/HORIZON,
        mean_duty_proxy=effort/HORIZON,mean_change=changes/HORIZON,
        hot_area_c_min=hot_area,max_temperature_c=maximum)
    return metrics,trace_rows


def evaluate(model,actions,cases,target,band,**kwargs):
    return legacy.average_metrics([rollout(model,actions,c,target,band,**kwargs)[0] for c in cases])


def aggregate(metrics):
    result = legacy.average_metrics(metrics)
    result['worst_seed_in_band_pct'] = min(m['in_band_pct'] for m in metrics)
    result['eligible'] = (result['invalid_fraction']==0 and result['in_band_pct']>=90
                          and result['worst_seed_in_band_pct']>=80
                          and result['guard_rate']<=.01 and result['fallback_rate']<=.01)
    return result


def rank(m,band):
    # Feasibility precedes performance; tiny hot-area differences cannot trump the band requirement.
    return (not m['eligible'],m['invalid_fraction'],max(0,90-m['in_band_pct']),
            max(0,80-m['worst_seed_in_band_pct']),max(0,m['guard_rate']-.01),
            max(0,m['fallback_rate']-.01),m['mae_c']/band+.02*m['mean_duty_proxy'])


def run(logs,folder,checkpoints=(500,1500,4000),target=37.5,band=.5):
    folder.mkdir(parents=True,exist_ok=False)
    sessions = [legacy.read_log(p) for p in logs]
    model,model_report,issues,actions,train = legacy.identify(sessions,target,band)
    if issues or model is None:
        raise ValueError('Chưa đủ điều kiện mô hình: '+'; '.join(issues))
    protocol = dict(version=2,target_c=target,band_c=band,dt_s=DT,horizon_s=DT*HORIZON,
        checkpoints=list(checkpoints),state_count=STATE_COUNT,actions=actions,
        state_spec='9 error x 3 trend x 3 heater-memory x 2 soft-guard; no previous-action term',
        train_seeds=TRAIN_SEEDS,check_seeds=CHECK_SEEDS,validation_scenarios=32,
        validation_scenario_seed=VALIDATION_SEED,check_scenarios=64,
        check_scenario_seed=CHECK_SCENARIO_SEED,
        criteria='invalid=0; mean in band>=90%; worst seed>=80%; guard steps<=1%; fallback<=1%',
        soft_guard=dict(off_c=target+band,resume_c=target-band,trigger_penalty=10),
        reward='-|T-target|/band - hot*(max(0,T-target-band)/band)^2 - duty*(H+F)/2 - 10*guard_trigger',
        switching_weight=0,algorithms=['q-learning','expected-sarsa'],
        grid=[dict(hot=h,duty=d) for h,d in itertools.product((3.,10.),(0.,.05))],
        evidence='DEVELOPMENT_SIMULATION_ON_ALREADY_REVIEWED_RUN; not independent hardware validation',
        sources=[dict(path=s['path'],sha256=s['sha256']) for s in sessions],deploy_allowed=False)
    legacy.write_json(folder/'giao_thuc.json',protocol)
    validation = legacy.scenarios(model,train,target,VALIDATION_SEED,32)
    baseline_runs = []
    for config in legacy.baseline_candidates():
        metrics = evaluate(model,actions,validation,target,band,baseline=config)
        aggregated = aggregate([metrics])
        baseline_runs.append((rank(aggregated,band),config,metrics))
    _,baseline,baseline_val = min(baseline_runs,key=lambda r:r[0])
    trials,policies,best = [],{},None
    for algorithm in protocol['algorithms']:
        for weights in protocol['grid']:
            by_checkpoint = {ep:[] for ep in checkpoints}
            snapshots = {ep:[] for ep in checkpoints}
            for seed in TRAIN_SEEDS:
                for ep,q,v in train_checkpoints(model,train,actions,target,band,algorithm,weights,seed,checkpoints):
                    met = evaluate(model,actions,validation,target,band,q=q,visits=v)
                    by_checkpoint[ep].append(met)
                    snapshots[ep].append(dict(seed=seed,q=[row[:] for row in q],visits=[row[:] for row in v]))
            for ep in checkpoints:
                metrics = aggregate(by_checkpoint[ep])
                row = dict(algorithm=algorithm,episodes=ep,weights=weights,validation=metrics,
                           validation_by_seed=[dict(seed=s,metrics=m) for s,m in zip(TRAIN_SEEDS,by_checkpoint[ep])])
                trials.append(row)
                key = rank(metrics,band)
                if best is None or key<best[0]:
                    best = key,row,snapshots[ep]
                print(f'{algorithm}, hot={weights["hot"]:g}, duty={weights["duty"]:g}, ep={ep}: '
                      f'trong vùng {metrics["in_band_pct"]:.1f}%, seed thấp nhất {metrics["worst_seed_in_band_pct"]:.1f}%',flush=True)
    _,winner,winning_policies = best
    frozen = dict(algorithm=winner['algorithm'],episodes=winner['episodes'],weights=winner['weights'],
                  selected_using='validation only; frozen before robustness simulations',baseline=baseline)
    legacy.write_json(folder/'lua_chon_da_chot.json',frozen)
    # New Monte Carlo cases/seeds do NOT turn this one measured run into a new hardware test.
    check = legacy.scenarios(model,train,target,CHECK_SCENARIO_SEED,64)
    check_metrics = []
    for policy in winning_policies:
        check_metrics.append(dict(seed=policy['seed'],metrics=evaluate(model,actions,check,target,band,
                                  q=policy['q'],visits=policy['visits'])))
    extra_seed_metrics = []
    for seed in CHECK_SEEDS:
        for _,q,v in train_checkpoints(model,train,actions,target,band,winner['algorithm'],winner['weights'],
                                        seed,[winner['episodes']]):
            extra_seed_metrics.append(dict(seed=seed,metrics=evaluate(model,actions,check,target,band,q=q,visits=v)))
    check_mean = aggregate([p['metrics'] for p in check_metrics+extra_seed_metrics])
    base_check = evaluate(model,actions,check,target,band,baseline=baseline)
    result = dict(status='SIMULATION_CANDIDATE_ONLY' if winner['validation']['eligible'] and check_mean['eligible']
                  else 'NO_STABLE_CANDIDATE',protocol=protocol,model=model_report,selected=winner,
        trials=trials,check_by_seed=check_metrics,additional_training_seeds=extra_seed_metrics,
        check_mean=check_mean,baseline=dict(configuration=baseline,validation=baseline_val,check=base_check),
        better_than_baseline_on_new_simulation_cases=(check_mean['eligible'] and
            check_mean['mae_c']<base_check['mae_c'] and check_mean['in_band_pct']>=base_check['in_band_pct']-.5),
        deploy_allowed=False)
    legacy.write_json(folder/'ket_qua.json',result)
    flattened = [dict(algorithm=r['algorithm'],episodes=r['episodes'],**r['weights'],**r['validation']) for r in trials]
    legacy.write_csv(folder/'duong_hoc_validation.csv',flattened,list(flattened[0]))
    if result['status']=='SIMULATION_CANDIDATE_ONLY':
        legacy.write_json(folder/'chinh_sach_UNG_VIEN_MO_PHONG.json',dict(
            status='SIMULATION_ONLY_NOT_HARDWARE_VALIDATED',deploy_allowed=False,
            model=asdict(model),protocol=protocol,selection=frozen,policies=winning_policies))
    traces = []
    for name,kwargs in [('baseline',dict(baseline=baseline))]+[
        (f'rl_seed_{p["seed"]}',dict(q=p['q'],visits=p['visits'])) for p in winning_policies]:
        _,trace = rollout(model,actions,check[0],target,band,trace=True,**kwargs)
        traces.extend(dict(controller=name,**r) for r in trace)
    legacy.write_csv(folder/'trace_MO_PHONG.csv',traces,list(traces[0]))
    lines = ['# Cải thiện RL offline, phiên bản 2','',f'Trạng thái: **{result["status"]}**.',
        '', 'Đây là phát triển trên lượt đo đã được xem trước, không phải kiểm chứng độc lập trên hộp.',
        'Bảo vệ mềm mô phỏng 38→37°C dùng chung cho RL và đối chứng; khác quy trình mô phỏng cũ (38,5°C).',
        'Không so trực tiếp chỉ số cũ và mới để quy toàn bộ cải thiện cho RL. Duty chưa phải điện năng.',
        '',f'162 state, {len(actions)} action phối hợp bóng/quạt; không phạt đổi action vì đã bỏ action trước khỏi state.',
        f'Chọn trên validation: **{winner["algorithm"]}, {winner["episodes"]} episode**, weights={winner["weights"]}.',
        'Sau khi chốt, kiểm tra thêm các tình huống nhiễu và hai seed huấn luyện mới; không chọn lại theo kết quả đó.',
        '', '| Bộ điều khiển | MAE mô phỏng °C | Trong vùng % | Seed thấp nhất % |', '|---|---:|---:|---:|',
        f'| Đối chứng {baseline} | {base_check["mae_c"]:.3f} | {base_check["in_band_pct"]:.1f} | — |',
        f'| RL, trung bình 5 seed | {check_mean["mae_c"]:.3f} | {check_mean["in_band_pct"]:.1f} | {check_mean["worst_seed_in_band_pct"]:.1f} |',
        '',f'RL hơn đối chứng theo điều kiện đã đặt: **{result["better_than_baseline_on_new_simulation_cases"]}**.',
        f'Ra ngoài miền mô hình: {100*check_mean["invalid_fraction"]:.2f}% tình huống; bảo vệ {100*check_mean["guard_rate"]:.2f}% bước; fallback {100*check_mean["fallback_rate"]:.2f}% bước.',
        'MAE có phạt phần còn lại nếu tình huống ra ngoài miền; không phải số đo sai số trên thiết bị.',
        '', '## Kiểm tra từng seed', '', '| Seed | MAE °C | Trong vùng % |', '|---:|---:|---:|']
    for p in check_metrics+extra_seed_metrics:
        lines.append(f'| {p["seed"]} | {p["metrics"]["mae_c"]:.3f} | {p["metrics"]["in_band_pct"]:.1f} |')
    lines += ['', '## Tiếp theo', '',
        'Chạy kiem_tra_giu_nhiet.py để thu lượt giữ nhiệt độc lập. Bộ này chưa cho chạy RL lên GPIO.',
        'Cần so RL và đối chứng trên phần cứng cùng điều kiện trước khi kết luận nâng hiệu năng máy ấp.',
        'Mô hình vẫn địa phương, một đầu dò, cùng một phiên; chưa đo độ ẩm, W/Wh hoặc độ đều nhiệt.',
        '', 'Thuật toán Expected SARSA: https://www.incompleteideas.net/book/RLbook2020.pdf (Chương 6).']
    (folder/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log',type=Path,action='append',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--moc',type=int,nargs='+',default=[500,1500,4000])
    args = p.parse_args(argv)
    if any(ep<10 or ep>10000 for ep in args.moc) or len(set(args.moc))!=len(args.moc):
        p.error('--moc cần các số khác nhau trong 10–10000.')
    try:
        r = run(args.log,args.out,tuple(sorted(args.moc)))
    except (OSError,ValueError) as exc:
        p.exit(1,f'Lỗi: {exc}\n')
    print(f'KẾT QUẢ: {args.out / "KET_QUA.md"}\n{r["status"]}; deploy_allowed=false')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
