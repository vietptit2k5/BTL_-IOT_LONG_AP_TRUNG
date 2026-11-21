#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phân tích CSV khảo sát; thử reward/Q-learning OFFLINE, không có GPIO.

Không suy hệ số reward duy nhất từ tốc độ nhiệt. Mục tiêu/dung sai là yêu cầu
thiết kế; dữ liệu dùng nhận dạng mô hình và so sánh ứng viên bằng tiêu chí cố định.
Chỉ dùng thư viện chuẩn Python; không cần TensorFlow/numpy/numba.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import csv
from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics


DT = 5.0
SEEDS = (11, 29)
HORIZON = 120
MODEL_MARGIN = .25


def finite(value, name):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f'{name}: giá trị không hữu hạn.')
    return number


def slope(points):
    if len(points) < 3 or points[-1][0] - points[0][0] < 10:
        return None
    mt = statistics.mean(t for t, _ in points)
    my = statistics.mean(t for _, t in points)
    den = sum((t - mt) ** 2 for t, _ in points)
    return 60 * sum((t - mt) * (v - my) for t, v in points) / den


def read_log(path):
    path = Path(path)
    measurements, commands, issues, warnings = [], [(0., 0., 0.)], [], []
    sensors, frequencies = set(), set()
    ended, previous_t = False, -math.inf
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'event', 'phase', 'elapsed_s', 'sensor_id', 'temperature_c',
                    'temperature_age_s', 'gpio_control', 'lamp_command_pct', 'fan_command_pct',
                    'lamp_requested_pct', 'fan_requested_pct', 'fan_pwm_hz'}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f'{path.name}: không phải CSV của do_nhiet_hop.py.')
        for row in reader:
            t = finite(row['elapsed_s'], 'elapsed_s')
            if t < previous_t or t < 0:
                raise ValueError(f'{path.name}: thời gian không tăng theo thứ tự.')
            previous_t = t
            if row['event'] == 'ERROR':
                issues.append('Lượt có lỗi/ngắt; không tự dùng để chọn reward.')
            if row['event'] == 'END':
                ended = True
            if row['gpio_control'] != '1':
                continue
            h, f = finite(row['lamp_command_pct'], 'bóng') / 100, finite(row['fan_command_pct'], 'quạt') / 100
            if not 0 <= h <= 1 or not 0 <= f <= 1:
                raise ValueError(f'{path.name}: duty nằm ngoài 0–100%.')
            if (h, f) != commands[-1][1:]:
                commands.append((t, h, f))
            if row['fan_pwm_hz']:
                frequencies.add(finite(row['fan_pwm_hz'], 'fan_pwm_hz'))
            if row['sensor_id']:
                sensors.add(row['sensor_id'])
            if row['event'] != 'MEASUREMENT' or not row['temperature_c']:
                continue
            age = finite(row['temperature_age_s'], 'tuổi số đo')
            temperature = finite(row['temperature_c'], 'nhiệt độ')
            if not 0 <= age < 3 or not -55 <= temperature <= 125 or temperature == 85:
                issues.append('Có số đo quá hạn hoặc ngoài miền hợp lệ.')
                continue
            measurements.append(dict(t=t - age, temperature=temperature, phase=row['phase'],
                                     h=h, f=f, rh=finite(row['lamp_requested_pct'], 'bóng yêu cầu') / 100,
                                     rf=finite(row['fan_requested_pct'], 'quạt yêu cầu') / 100))
    if not ended:
        issues.append('Thiếu END; file có thể chưa ghi xong.')
    measurements.sort(key=lambda row: row['t'])
    unique = []
    for row in measurements:
        if not unique or row['t'] > unique[-1]['t']:
            unique.append(row)
    if any(b['t'] - a['t'] > 3 for a, b in zip(unique, unique[1:])):
        issues.append('Có khoảng mất mẫu trên 3 giây.')
    config = path.parent / 'cau_hinh.json'
    planned_phases = {}
    if config.is_file():
        try:
            manifest = json.loads(config.read_text(encoding='utf-8'))
            for phase in manifest.get('schedule', {}).get('phases', []):
                if phase.get('name', '').startswith('thu_'):
                    planned_phases[phase['name']] = dict(seconds=finite(phase['seconds'], 'thời gian dự kiến'),
                                                        h=finite(phase['lamp'], 'bóng dự kiến') / 100,
                                                        f=finite(phase['fan'], 'quạt dự kiến') / 100)
            if not manifest.get('schedule', {}).get('completed_schedule', False):
                warnings.append('Lịch khảo sát chưa chạy hết; chỉ đánh giá phần thực sự đã đo, kiểm tra độ phủ action.')
            if manifest.get('hardware_program_exit_code', 0) != 0:
                issues.append('Chương trình phần cứng kết thúc với mã lỗi/ngắt; chưa tự dùng để chọn reward.')
        except (OSError, ValueError, KeyError, TypeError):
            issues.append('Không đọc được cấu hình lượt đo; vẫn lưu đáp ứng, chưa chọn reward.')
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                samples=unique, commands=commands, issues=sorted(set(issues)),
                warnings=warnings, sensors=sorted(sensors), frequencies=sorted(frequencies),
                planned_phases=planned_phases)


def summarize_phases(sessions):
    summaries = []
    for session in sessions:
        blocks, block, previous = [], [], None
        for row in session['samples']:
            key = row['phase'], row['rh'], row['rf']
            if key != previous and block:
                blocks.append(block)
                block = []
            block.append(row)
            previous = key
        if block:
            blocks.append(block)
        for number, block in enumerate(blocks, 1):
            # Bỏ đoạn khởi động quạt và 5 giây đầu khi mô tả dốc của bước.
            begin = block[0]['t']
            steady = [r for r in block if r['t'] >= begin + 5 and abs(r['h'] - r['rh']) < .001
                      and abs(r['f'] - r['rf']) < .001]
            points = [(r['t'], r['temperature']) for r in steady]
            rate = slope(points)
            duration = block[-1]['t'] - begin
            max_gap = max((b['t'] - a['t'] for a, b in zip(block, block[1:])), default=0.)
            stable_span = points[-1][0] - points[0][0] if len(points) > 1 else 0.
            planned = session.get('planned_phases', {}).get(block[0]['phase'])
            expected = planned['seconds'] if planned else None
            complete = None if expected is None else duration >= expected - 3 and stable_span >= expected - 8 and max_gap <= 3
            tail = [(t, value) for t, value in points if t >= block[-1]['t'] - 30]
            tail_rate = slope(tail)
            # Chỉ báo thực nghiệm, không tự đồng nhất với thời gian xác lập thật.
            near_flat = (stable_span >= 60 and tail_rate is not None and abs(tail_rate) <= .1
                         and len(tail) >= 20 and statistics.pstdev(v for _, v in tail) <= .1)
            summaries.append(dict(log=Path(session['path']).name, block=number, phase=block[0]['phase'],
                                  lamp_requested_pct=100 * block[0]['rh'], fan_requested_pct=100 * block[0]['rf'],
                                  duration_s=duration, planned_duration_s=expected,
                                  stable_span_s=stable_span, max_sample_gap_s=max_gap, continuous_window_complete=complete,
                                  last_30s_slope_c_per_min=tail_rate, near_flat_hint=near_flat, samples=len(block),
                                  start_c=block[0]['temperature'], end_c=block[-1]['temperature'],
                                  delta_c=block[-1]['temperature'] - block[0]['temperature'],
                                  slope_c_per_min=rate,
                                  trend='chưa đủ mẫu' if rate is None else ('tăng' if rate > .03 else 'giảm' if rate < -.03 else 'độ dốc nhỏ')))
    return summaries


def interpolate(samples, times, when):
    i = bisect_right(times, when) - 1
    if i < 0:
        raise ValueError('Ngoài miền thời gian dữ liệu.')
    if i == len(samples) - 1 or abs(times[i] - when) < 1e-8:
        return samples[i]['temperature']
    if times[i + 1] - times[i] > 3:
        raise ValueError('Không nội suy qua khoảng mất số đo.')
    fraction = (when - times[i]) / (times[i + 1] - times[i])
    return samples[i]['temperature'] + fraction * (samples[i + 1]['temperature'] - samples[i]['temperature'])


def mean_input(commands, start, end):
    times = [row[0] for row in commands]
    index = max(0, bisect_right(times, start) - 1)
    current, hsum, fsum = start, 0., 0.
    while current < end - 1e-9:
        boundary = min(end, times[index + 1] if index + 1 < len(times) else end)
        hsum += commands[index][1] * (boundary - current)
        fsum += commands[index][2] * (boundary - current)
        current = boundary
        if current < end - 1e-9:
            index += 1
    return hsum / (end - start), fsum / (end - start)


def transitions(session, tau):
    samples = session['samples']
    if len(samples) < 2:
        return []
    times = [r['t'] for r in samples]
    t, memory, previous_delta = times[0], 0., 0.
    result = []
    while t + DT <= times[-1] + 1e-8:
        temperature = interpolate(samples, times, t)
        next_temp = interpolate(samples, times, t + DT)
        h, f = mean_input(session['commands'], t, t + DT)
        next_memory = h if tau == 0 else memory + (h - memory) * (1 - math.exp(-DT / tau))
        result.append(dict(t=t, temperature=temperature, next_temperature=next_temp,
                           delta=next_temp - temperature, previous_delta=previous_delta,
                           memory_before=memory, memory=next_memory, h=h, f=f))
        memory, previous_delta, t = next_memory, next_temp - temperature, t + DT
    return result


def least_squares_qr(rows, values):
    """QR cải biên có tái trực giao, chuẩn hóa cột; báo thiếu hạng thay vì bù giả."""
    n, p = len(rows), len(rows[0])
    if n < p + 2:
        raise ValueError('Quá ít hàng cho mô hình.')
    means = [0.] + [statistics.mean(row[j] for row in rows) for j in range(1, p)]
    scales = [1.] + [math.sqrt(sum((row[j] - means[j]) ** 2 for row in rows) / n) for j in range(1, p)]
    if min(scales) < 1e-10:
        raise ValueError('Kích thích chưa đủ: có cột đặc trưng không thay đổi.')
    columns = [[(row[j] - means[j]) / scales[j] for row in rows] for j in range(p)]
    q, r = [], [[0.] * p for _ in range(p)]
    for j in range(p):
        vector = columns[j][:]
        for _ in range(2):
            for i in range(j):
                projection = sum(a * b for a, b in zip(q[i], vector))
                r[i][j] += projection
                vector = [a - projection * b for a, b in zip(vector, q[i])]
        length = math.sqrt(sum(value * value for value in vector))
        if length < 1e-7 * math.sqrt(n):
            raise ValueError('Đặc trưng phụ thuộc nhau; chưa nhận dạng được mô hình.')
        r[j][j] = length
        q.append([value / length for value in vector])
    ratio = max(r[i][i] for i in range(p)) / min(r[i][i] for i in range(p))
    if ratio > 1e4:
        raise ValueError('Mô hình gần thiếu hạng; cần kích thích đa dạng hơn.')
    rhs = [sum(a * b for a, b in zip(column, values)) for column in q]
    beta = [0.] * p
    for i in reversed(range(p)):
        beta[i] = (rhs[i] - sum(r[i][j] * beta[j] for j in range(i + 1, p))) / r[i][i]
    coefficients = [beta[j] / scales[j] for j in range(p)]
    coefficients[0] -= sum(coefficients[j] * means[j] for j in range(1, p))
    return coefficients, ratio


def features(temperature, previous_delta, memory, fan, center, fan_center):
    fc = fan - fan_center
    return [1., temperature - center, previous_delta, memory, fc, memory * fc]


@dataclass
class ThermalModel:
    coefficients: list
    center: float
    fan_center: float
    tau: float
    low: float
    high: float
    noise_sd: float

    def step(self, temperature, previous_delta, memory, heat, fan, noise=0.):
        next_memory = heat if self.tau == 0 else memory + (heat - memory) * (1 - math.exp(-DT / self.tau))
        x = features(temperature, previous_delta, next_memory, fan, self.center, self.fan_center)
        delta = sum(a * b for a, b in zip(self.coefficients, x)) + noise
        return temperature + delta, delta, next_memory


def model_metrics(model, blocks):
    errors, free, persistence = [], [], []
    for rows in blocks:
        for row in rows:
            predicted, _, _ = model.step(row['temperature'], row['previous_delta'], row['memory_before'], row['h'], row['f'])
            errors.append(predicted - row['next_temperature'])
        for start in range(0, len(rows) - 5, 6):
            chunk = rows[start:start + 6]
            initial = chunk[0]
            temperature, delta, memory = initial['temperature'], initial['previous_delta'], initial['memory_before']
            for row in chunk:
                temperature, delta, memory = model.step(temperature, delta, memory, row['h'], row['f'])
                free.append(temperature - row['next_temperature'])
                persistence.append(initial['temperature'] - row['next_temperature'])
    def rmse(values):
        return math.sqrt(statistics.mean(v * v for v in values)) if values else None
    return dict(one_step_rmse_c=rmse(errors), rollout_30s_rmse_c=rmse(free), persistence_30s_rmse_c=rmse(persistence))


def identify(sessions, target, band):
    issues = [issue for session in sessions for issue in session['issues']]
    all_samples = [row for session in sessions for row in session['samples']]
    if not all_samples:
        return None, {}, ['Không có số đo có điều khiển GPIO.'], [], []
    temperatures = [r['temperature'] for r in all_samples]
    low, high = min(temperatures), max(temperatures)
    counts = Counter((round(r['rh'], 4), round(r['rf'], 4)) for r in all_samples
                     if abs(r['h'] - r['rh']) < .001 and abs(r['f'] - r['rf']) < .001 and r['rf'] > 0)
    requirements = {}
    for session in sessions:
        for phase in session.get('planned_phases', {}).values():
            pair = round(phase['h'], 4), round(phase['f'], 4)
            requirements[pair] = max(requirements.get(pair, 0), phase['seconds'])
    blocks_summary = summarize_phases(sessions)
    complete_pairs, support = set(), []
    for pair, required in sorted(requirements.items()):
        blocks = [row for row in blocks_summary if row['phase'].startswith('thu_') and
                  abs(row['lamp_requested_pct'] / 100 - pair[0]) < .001 and
                  abs(row['fan_requested_pct'] / 100 - pair[1]) < .001]
        qualified = any(row['duration_s'] >= required - 3 and row['stable_span_s'] >= required - 8
                        and row['max_sample_gap_s'] <= 3 for row in blocks)
        if qualified:
            complete_pairs.add(pair)
        support.append(dict(lamp_pct=100 * pair[0], fan_pct=100 * pair[1], required_continuous_s=required,
                            longest_observed_s=max((row['duration_s'] for row in blocks), default=0), qualified=qualified))
    actions = sorted(pair for pair, n in counts.items() if n >= 15 and
                     (pair not in requirements or pair in complete_pairs))
    if len({h for h, _ in actions}) < 3 or len({f for _, f in actions}) < 2:
        issues.append('Cần ít nhất ba mức bóng và hai mức quạt, mỗi tổ hợp được đo đủ lâu.')
    if not any(h == 0 for h, _ in actions) or not any(f == 1 for _, f in actions):
        issues.append('Cần đo cả tắt bóng và quạt 100% để có hành động dự phòng trong mô phỏng.')
    if high - low < 1:
        issues.append('Nhiệt chỉ thay đổi dưới 1°C; chưa đủ nhận dạng.')
    if target - band < low - MODEL_MARGIN or target + band > high + MODEL_MARGIN:
        issues.append(f'Vùng mục tiêu {target - band:g}–{target + band:g}°C chưa được khảo sát; không ngoại suy xa.')
    if len({sensor for s in sessions for sensor in s['sensors']}) != 1:
        issues.append('Chỉ gộp lượt của cùng một mã cảm biến tại cùng vị trí.')
    if len({frequency for s in sessions for frequency in s['frequencies']}) != 1:
        issues.append('Không gộp các tần số PWM quạt khác nhau vào một mô hình.')
    report = dict(observed_temperature_range_c=[low, high], actions=[list(a) for a in actions],
                  action_observation_support=support,
                  model_domain_margin_c=MODEL_MARGIN, candidates=[])
    candidates = []
    for tau in (0., 10., 25.):
        blocks = [transitions(session, tau) for session in sessions]
        train_blocks, val_blocks, test_blocks = [], [], []
        for rows in blocks:
            n = len(rows)
            a, b = int(.6 * n), int(.8 * n)
            train_blocks.append(rows[:a])
            val_blocks.append(rows[a + 2:b])  # khoảng cách 10 giây giữa các phần
            test_blocks.append(rows[b + 2:])
        train = list(itertools.chain.from_iterable(train_blocks))
        if len(train) < 40 or sum(map(len, val_blocks)) < 8 or sum(map(len, test_blocks)) < 8:
            report['candidates'].append(dict(tau_s=tau, error='Cần thêm dữ liệu: train >=40, validation/test >=8 bước 5 giây.'))
            continue
        center = statistics.mean(row['temperature'] for row in train)
        fan_center = statistics.mean(sorted({f for _, f in actions})) if actions else .75
        x = [features(r['temperature'], r['previous_delta'], r['memory'], r['f'], center, fan_center) for r in train]
        try:
            coefficients, ratio = least_squares_qr(x, [r['delta'] for r in train])
            # Ma trận tự hồi quy của T và dT cần ổn định trong mô hình địa phương.
            bt, bv = coefficients[1:3]
            trace, determinant = 1 + bt + bv, bv
            discriminant = trace * trace - 4 * determinant
            radius = (max(abs((trace + math.sqrt(discriminant)) / 2), abs((trace - math.sqrt(discriminant)) / 2))
                      if discriminant >= 0 else math.sqrt(determinant))
            if radius >= 1.02 or bt >= 0:
                raise ValueError('Hệ số tự hồi quy chưa ổn định/phản ánh mất nhiệt; cần thêm đoạn nguội.')
            if any(coefficients[3] + coefficients[5] * (f - fan_center) <= 0 for _, f in actions):
                raise ValueError('Chưa nhận dạng được tác dụng sưởi dương ở các mức quạt.')
            residuals = [sum(a * b for a, b in zip(coefficients, row)) - actual['delta'] for row, actual in zip(x, train)]
            sigma = max(.005, math.sqrt(statistics.mean(v * v for v in residuals)))
            model = ThermalModel(coefficients, center, fan_center, tau, low - MODEL_MARGIN, high + MODEL_MARGIN, sigma)
            val = model_metrics(model, val_blocks)
            if val['rollout_30s_rmse_c'] is None:
                raise ValueError('Phần validation mỗi lượt quá ngắn để kiểm tra dự báo 30 giây.')
            spec = dict(tau_s=tau, coefficients=coefficients, qr_diagonal_ratio=ratio,
                        validation=val, train_steps=len(train), validation_steps=sum(map(len, val_blocks)),
                        test_steps=sum(map(len, test_blocks)))
            report['candidates'].append(spec)
            candidates.append((val['rollout_30s_rmse_c'], model, spec, train))
        except (ValueError, ArithmeticError) as exc:
            report['candidates'].append(dict(tau_s=tau, error=str(exc)))
    if not candidates:
        issues.append('Chưa có mô hình hợp lệ; báo cáo dốc nhiệt vẫn được lưu.')
        return None, report, sorted(set(issues)), actions, []
    _, model, spec, train = min(candidates, key=lambda candidate: candidate[0])
    # Chỉ đọc tập test sau khi chọn tau bằng validation; không chọn lại theo test.
    test_blocks = []
    for session in sessions:
        rows = transitions(session, model.tau)
        test_blocks.append(rows[int(.8 * len(rows)) + 2:])
    test = model_metrics(model, test_blocks)
    report['selected'] = dict(**spec, test=test, model=asdict(model))
    for name, metrics in (('validation', spec['validation']), ('test', test)):
        if metrics['rollout_30s_rmse_c'] is None or metrics['rollout_30s_rmse_c'] > min(.35, .6 * band):
            issues.append(f'Sai số dự báo 30 giây trên {name} còn cao so với dung sai.')
        if (metrics['persistence_30s_rmse_c'] is None or
                metrics['rollout_30s_rmse_c'] >= .95 * metrics['persistence_30s_rmse_c']):
            issues.append(f'Mô hình chưa hơn dự báo giữ nguyên nhiệt độ trên {name}.')
    return model, report, sorted(set(issues)), actions, train


def nearest_action(actions, heat, fan):
    return min(range(len(actions)), key=lambda i: abs(actions[i][0] - heat) + abs(actions[i][1] - fan))


def state_id(temperature, delta, memory, last_action, target, band, max_heat, action_count):
    error_bin = bisect_right((-4., -2., -1., -.3, .3, 1., 2., 4.), (temperature - target) / band)
    threshold = max(.03, band * .1)
    trend_bin = 0 if delta < -threshold else 2 if delta > threshold else 1
    memory_bin = 0 if memory < max_heat / 3 else 2 if memory > 2 * max_heat / 3 else 1
    return ((error_bin * 3 + trend_bin) * 3 + memory_bin) * action_count + last_action


def reward_value(temperature, action, previous, target, band, weights):
    error = abs(temperature - target) / band
    hot = (max(0., temperature - target - band) / band) ** 2
    duty_proxy = (action[0] + action[1]) / 2
    change = abs(action[0] - previous[0]) + abs(action[1] - previous[1])
    return -error - weights['hot'] * hot - weights['duty'] * duty_proxy - weights['switch'] * change


def training_pool(rows, target):
    return [row for row in rows if abs(row['temperature'] - target) <= 1.5]


def train_q(model, rows, actions, target, band, weights, seed, episodes):
    rng = random.Random(seed)
    pool = training_pool(rows, target)
    if not pool:
        raise ValueError('Phần train chưa có dữ liệu gần mục tiêu; không tự huấn luyện bằng ngoại suy.')
    count, max_heat = len(actions), max(h for h, _ in actions)
    q = [[0.] * count for _ in range(81 * count)]
    visits = [[0] * count for _ in q]
    for episode in range(episodes):
        initial = rng.choice(pool)
        temperature, delta, memory = initial['temperature'], initial['previous_delta'], initial['memory_before']
        previous = nearest_action(actions, initial['h'], initial['f'])
        epsilon = max(.05, 1 - .95 * episode / max(1, .8 * episodes))
        alpha = .15 - .12 * episode / max(1, episodes - 1)
        for k in range(HORIZON):
            s = state_id(temperature, delta, memory, previous, target, band, max_heat, count)
            if rng.random() < epsilon:
                selected = rng.randrange(count)
            else:
                best = max(q[s])
                selected = rng.choice([i for i, value in enumerate(q[s]) if abs(value - best) < 1e-10])
            applied = selected
            guarded = temperature >= min(39., target + band + .5)
            if guarded:
                applied = nearest_action(actions, 0, max(f for _, f in actions))
            heat, fan = actions[applied]
            next_t, next_delta, next_memory = model.step(temperature, delta, memory, heat, fan, rng.gauss(0, model.noise_sd))
            invalid = not math.isfinite(next_t) or not model.low <= next_t <= model.high
            reward = (-100. * (HORIZON - k) if invalid else
                      reward_value(next_t, actions[applied], actions[previous], target, band, weights) - (20 if guarded else 0))
            future = 0.
            if not invalid:
                sn = state_id(next_t, next_delta, next_memory, applied, target, band, max_heat, count)
                future = .98 * max(q[sn])
            q[s][selected] += alpha * (reward + future - q[s][selected])
            visits[s][selected] += 1
            if invalid:
                break
            temperature, delta, memory, previous = next_t, next_delta, next_memory, applied
    return q, visits


def scenarios(model, rows, target, seed, number):
    rng = random.Random(seed)
    pool = training_pool(rows, target)
    if not pool:
        raise ValueError('Không có trạng thái khởi đầu gần mục tiêu trong phần train.')
    return [dict(initial=rng.choice(pool), noise=[rng.gauss(0, model.noise_sd) for _ in range(HORIZON)])
            for _ in range(number)]


def rollout(model, actions, case, target, band, q=None, visits=None, baseline=None, trace=False):
    initial = case['initial']
    temperature, delta, memory = initial['temperature'], initial['previous_delta'], initial['memory_before']
    previous = nearest_action(actions, initial['h'], initial['f'])
    integral = 0.
    heater_on = temperature < target
    maximum = temperature
    sums = dict(abs_error=0., in_band=0., hot_area=0., duty=0., changes=0., guard=0., fallback=0.)
    failed, samples = 0, []
    max_heat, fan_low, fan_high = max(h for h, _ in actions), min(f for _, f in actions), max(f for _, f in actions)
    for k in range(HORIZON):
        if baseline is not None:
            mode = baseline['fan_mode']
            fan = fan_low if mode == 'low' else fan_high if mode == 'high' else (
                fan_high if temperature > target + .2 or delta > .05 else fan_low)
            if baseline['kind'] == 'thermostat':
                if temperature < target - baseline['band']:
                    heater_on = True
                elif temperature > target + baseline['band']:
                    heater_on = False
                heat = max_heat if heater_on else 0.
            else:
                error = target - temperature
                proposal = integral + baseline['ki'] * error * DT
                raw = baseline['kp'] * error + proposal - baseline['kd'] * delta / DT
                if not ((raw > max_heat and error > 0) or (raw < 0 and error < 0)):
                    integral = proposal
                heat = min(max_heat, max(0., baseline['kp'] * error + integral - baseline['kd'] * delta / DT))
            selected = nearest_action(actions, heat, fan)
        else:
            s = state_id(temperature, delta, memory, previous, target, band, max_heat, len(actions))
            seen = [i for i, n in enumerate(visits[s]) if n > 0]
            if seen:
                selected = max(seen, key=lambda i: q[s][i])
            else:
                # Fallback được đếm, không trình bày là chính sách đã học.
                selected = nearest_action(actions, 0 if temperature >= target else max_heat / 2, fan_high)
                sums['fallback'] += 1
        applied = selected
        guarded = temperature >= min(39., target + band + .5)
        if guarded:
            applied = nearest_action(actions, 0, fan_high)
            sums['guard'] += 1
        heat, fan = actions[applied]
        next_t, next_delta, next_memory = model.step(temperature, delta, memory, heat, fan, case['noise'][k])
        if not math.isfinite(next_t):
            failed = 1
            sums['abs_error'] += 10 * band * (HORIZON - k)
            break
        maximum = max(maximum, next_t)
        sums['abs_error'] += abs(next_t - target)
        sums['in_band'] += abs(next_t - target) <= band
        sums['hot_area'] += max(0., next_t - target - band) * DT / 60
        sums['duty'] += (heat + fan) / 2
        sums['changes'] += abs(heat - actions[previous][0]) + abs(fan - actions[previous][1])
        if trace:
            samples.append(dict(seconds=(k + 1) * DT, simulated_temperature_c=next_t,
                                lamp_pct=100 * heat, fan_pct=100 * fan, guard=int(guarded)))
        if not model.low <= next_t <= model.high:
            failed = 1
            # Không đi tiếp ở miền chưa đo và không thưởng cho việc kết thúc sớm.
            sums['abs_error'] += 10 * band * (HORIZON - k - 1)
            break
        temperature, delta, memory, previous = next_t, next_delta, next_memory, applied
    metrics = dict(mae_c=sums['abs_error'] / HORIZON, in_band_pct=100 * sums['in_band'] / HORIZON,
                   hot_area_c_min=sums['hot_area'], mean_duty_proxy=sums['duty'] / HORIZON,
                   mean_change=sums['changes'] / HORIZON, guard_rate=sums['guard'] / HORIZON,
                   fallback_rate=sums['fallback'] / HORIZON, unsupported_fraction=float(failed),
                   max_temperature_c=maximum)
    return metrics, samples


def average_metrics(metrics):
    result = {key: statistics.mean(row[key] for row in metrics) for key in metrics[0]}
    result['max_temperature_c'] = max(row['max_temperature_c'] for row in metrics)
    return result


def evaluate(model, actions, cases, target, band, **kwargs):
    return average_metrics([rollout(model, actions, case, target, band, **kwargs)[0] for case in cases])


def score(metrics, band):
    """Tiêu chí ngoài reward, cố định cho mọi bộ điều khiển trước khi thử hệ số."""
    return (metrics['unsupported_fraction'], metrics['guard_rate'], metrics['hot_area_c_min'],
            max(0., 80 - metrics['in_band_pct']),
            metrics['mae_c'] / band + .02 * metrics['mean_duty_proxy'] + .005 * metrics['mean_change'])


def baseline_candidates():
    for fan in ('low', 'high', 'trend'):
        for width in (.1, .3, .5):
            yield dict(kind='thermostat', band=width, fan_mode=fan)
        for kp, ki, kd in itertools.product((.3, .8), (0., .002), (0., 1.)):
            yield dict(kind='pid', kp=kp, ki=ki, kd=kd, fan_mode=fan)


def tune_reward(model, rows, actions, target, band, episodes):
    validation = scenarios(model, rows, target, 140, 16)
    test = scenarios(model, rows, target, 905, 32)
    baseline_runs = []
    for baseline in baseline_candidates():
        metrics = evaluate(model, actions, validation, target, band, baseline=baseline)
        baseline_runs.append((score(metrics, band), baseline, metrics))
    _, baseline, baseline_val = min(baseline_runs, key=lambda row: row[0])
    baseline_test = evaluate(model, actions, test, target, band, baseline=baseline)
    trials = []
    best = None
    for hot, duty, switch in itertools.product((1., 3., 10.), (0., .05, .2), (0., .03)):
        weights = dict(hot=hot, duty=duty, switch=switch)
        policies, evaluations = [], []
        for seed in SEEDS:
            q, visits = train_q(model, rows, actions, target, band, weights, seed, episodes)
            evaluations.append(evaluate(model, actions, validation, target, band, q=q, visits=visits))
            policies.append(dict(seed=seed, q=q, visits=visits))
        metrics = average_metrics(evaluations)
        trial = dict(weights=weights, validation=metrics)
        trials.append(trial)
        key = score(metrics, band)
        if best is None or key < best[0]:
            best = key, trial, policies
        print(f"Thử reward hot={hot:g}, duty={duty:g}, switch={switch:g}: "
              f"MAE mô phỏng {metrics['mae_c']:.3f}°C, trong vùng {metrics['in_band_pct']:.1f}%", flush=True)
    _, winner, policies = best
    test_by_seed = [dict(seed=p['seed'], metrics=evaluate(model, actions, test, target, band, q=p['q'], visits=p['visits']))
                    for p in policies]
    test_mean = average_metrics([row['metrics'] for row in test_by_seed])
    eligible = (winner['validation']['unsupported_fraction'] == 0 and winner['validation']['guard_rate'] == 0
                and winner['validation']['in_band_pct'] >= 80 and winner['validation']['fallback_rate'] <= .05)
    passed_test = (test_mean['unsupported_fraction'] == 0 and test_mean['guard_rate'] == 0
                   and test_mean['in_band_pct'] >= 80 and test_mean['fallback_rate'] <= .05)
    trace_rows = []
    for name, kwargs in (('baseline', dict(baseline=baseline)),
                         (f"q_seed_{policies[0]['seed']}", dict(q=policies[0]['q'], visits=policies[0]['visits']))):
        _, trace = rollout(model, actions, test[0], target, band, trace=True, **kwargs)
        trace_rows += [dict(controller=name, **row) for row in trace]
    result = dict(trials=trials, selected=winner, test_by_seed=test_by_seed, test_mean=test_mean,
                  baseline=dict(configuration=baseline, validation=baseline_val, test=baseline_test),
                  validation_eligible=eligible, passed_simulation_test=passed_test,
                  better_than_baseline_on_simulation_test=score(test_mean, band) < score(baseline_test, band),
                  train_seeds=list(SEEDS), validation_seed=140, test_seed=905,
                  episodes_per_seed=episodes, simulation_horizon_s=DT * HORIZON,
                  deploy_allowed=False)
    return result, policies, trace_rows


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def write_csv(path, rows, fields):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: '' if row.get(key) is None else row.get(key, '') for key in fields})


def analyze(paths, folder, target=37.5, band=.5, episodes=250, tune=True, live_metadata=None):
    if not math.isfinite(target) or not math.isfinite(band) or not 20 <= target <= 38.8 or not .2 <= band <= 1:
        raise ValueError('Mục tiêu/dung sai không hợp lệ.')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    sessions = [read_log(path) for path in paths]
    if not sessions:
        raise ValueError('Cần ít nhất một CSV.')
    summaries = summarize_phases(sessions)
    fields = ['log', 'block', 'phase', 'lamp_requested_pct', 'fan_requested_pct', 'duration_s',
              'planned_duration_s', 'stable_span_s', 'max_sample_gap_s', 'continuous_window_complete',
              'last_30s_slope_c_per_min', 'near_flat_hint',
              'samples', 'start_c', 'end_c', 'delta_c', 'slope_c_per_min', 'trend']
    write_csv(folder / 'dap_ung_tung_buoc.csv', summaries, fields)
    model, model_report, reasons, actions, rows = identify(sessions, target, band)
    warnings = [warning for session in sessions for warning in session['warnings']]
    for support in model_report.get('action_observation_support', []):
        if not support['qualified']:
            warnings.append(f"Tổ hợp bóng {support['lamp_pct']:g}%/quạt {support['fan_pct']:g}% chưa có cửa sổ "
                            f"{support['required_continuous_s']:g}s liên tục; không đưa tổ hợp đó vào Q-table ứng viên.")
    if live_metadata is not None and not live_metadata['completed_schedule']:
        warnings.append('Lượt tự động chưa hoàn tất toàn bộ lịch; chỉ dùng phần có dữ liệu thực và đủ kiểm định.')
    reasons = sorted(set(reasons))
    report = dict(status='RESPONSE_ONLY', target_c=target, tolerance_c=band,
                  evidence='CSV_INPUT_AND_FITTED_SIMULATION_ONLY; no hardware RL validation or hatch claim',
                  sources=[{key: session[key] for key in ('path', 'sha256', 'issues', 'warnings')} for session in sessions],
                  response_blocks=len(summaries), model=model_report, needs_more_data=reasons,
                  warnings=sorted(set(warnings)),
                  reward_formula='-|T-target|/band - w_hot*(max(0,T-target-band)/band)^2 '
                                 '- w_duty*(u_heat+u_fan)/2 - w_switch*(|du_heat|+|du_fan|)',
                  effort_is_duty_proxy_not_measured_energy=True, deploy_allowed=False)
    if reasons:
        report['status'] = 'NEEDS_MORE_MEASUREMENTS'
    if tune and not reasons and model is not None:
        result, policies, trace = tune_reward(model, rows, actions, target, band, episodes)
        report['reward_search'] = result
        report['status'] = ('SIMULATION_CANDIDATE_ONLY' if result['validation_eligible'] and result['passed_simulation_test']
                            else 'NO_VALIDATED_REWARD_CANDIDATE')
        flat = [dict(**trial['weights'], **trial['validation']) for trial in result['trials']]
        write_csv(folder / 'thu_he_so_reward.csv', flat, list(flat[0]))
        write_csv(folder / 'so_sanh_MO_PHONG.csv', trace, ['controller', 'seconds', 'simulated_temperature_c', 'lamp_pct', 'fan_pct', 'guard'])
        if report['status'] == 'SIMULATION_CANDIDATE_ONLY':
            artifact = dict(evidence='SIMULATION_CANDIDATE_NOT_HARDWARE_VALIDATED', deploy_allowed=False,
                            model=asdict(model), target_c=target, tolerance_c=band, control_seconds=DT,
                            actions=[list(a) for a in actions], state_count=81 * len(actions),
                            state_spec='9 error bins x 3 delta bins x 3 heater-memory bins x last-action',
                            error_edges_in_tolerance_units=[-4, -2, -1, -.3, .3, 1, 2, 4],
                            trend_threshold_c_per_step=max(.03, band * .1),
                            reward_weights=result['selected']['weights'], seeds=list(SEEDS), tables=policies)
            write_json(folder / 'qtable_UNG_VIEN_MO_PHONG.json', artifact)
            write_json(folder / 'reward_de_xuat_MO_PHONG.json', {key: value for key, value in artifact.items() if key != 'tables'})
    write_json(folder / 'phan_tich.json', report)
    lines = ['# Kết quả khảo sát nhiệt', '', f"Trạng thái: **{report['status']}**.", '',
             'Dốc nhiệt bên dưới được tính từ CSV đầu vào. Dữ liệu mô phỏng được ghi riêng; không coi là phép đo trên hộp.', '',
             f'Mục tiêu {target:g}°C, dung sai ±{band:g}°C. Có {len(sessions)} lượt và {len(summaries)} đoạn đáp ứng.', '',
             '| Đoạn | Bóng % | Quạt % | Quan sát / yêu cầu (s) | Đủ liên tục | ΔT °C | Dốc °C/phút |',
             '|---|---:|---:|---:|---|---:|---:|']
    for row in summaries:
        rate = 'chưa đủ mẫu' if row['slope_c_per_min'] is None else f"{row['slope_c_per_min']:+.3f}"
        expected = '—' if row['planned_duration_s'] is None else f"{row['planned_duration_s']:g}"
        complete = '—' if row['continuous_window_complete'] is None else 'có' if row['continuous_window_complete'] else 'chưa'
        lines.append(f"| {row['phase']} | {row['lamp_requested_pct']:g} | {row['fan_requested_pct']:g} | "
                     f"{row['duration_s']:.1f} / {expected} | {complete} | {row['delta_c']:+.3f} | {rate} |")
    if reasons:
        lines += ['', 'Chưa chọn reward/Q-table vì:', ''] + [f'- {reason}' for reason in reasons]
    if warnings:
        lines += ['', 'Ghi chú lượt đo:', ''] + [f'- {warning}' for warning in sorted(set(warnings))]
    if 'reward_search' in report:
        result = report['reward_search']
        lines += ['', '## So sánh CHỈ TRONG MÔ PHỎNG', '',
                  '| Bộ điều khiển | MAE °C | Trong vùng % | Ngoài miền mô hình % |', '|---|---:|---:|---:|']
        for name, metrics in (('Đối chứng đã chỉnh trên validation', result['baseline']['test']),
                              ('Q-learning, trung bình hai seed', result['test_mean'])):
            lines.append(f"| {name} | {metrics['mae_c']:.3f} | {metrics['in_band_pct']:.1f} | {100 * metrics['unsupported_fraction']:.1f} |")
        lines += ['', f"Hệ số ứng viên chọn bằng validation: `{result['selected']['weights']}`.",
                  f"Q-learning hơn đối chứng theo tiêu chí đã định trên test mô phỏng: **{result['better_than_baseline_on_simulation_test']}**.",
                  'Không chọn lại hệ số theo test; không tự triển khai Q-table lên GPIO.']
    lines += ['', '## Giới hạn', '',
              '- Tốc độ tăng/giảm nhiệt không xác định duy nhất mức quan trọng của sai số, quá nhiệt và tiết kiệm. Mục tiêu và dung sai là yêu cầu thiết kế.',
              '- Hệ số chọn bằng tiêu chí chung: tránh ngoài miền/ngắt bảo vệ, hạn chế vượt nhiệt, đạt vùng mục tiêu rồi cân nhắc MAE và duty. Không so tổng reward có thang điểm khác nhau.',
              '- Duty là đại lượng thay thế mức điều khiển; chưa đo W/Wh/RPM. Một đầu dò không chứng minh độ đều nhiệt hoặc hiệu quả ấp nở.',
              '- Mô hình địa phương giả định điều kiện phòng/bố trí giống lúc đo; nhiễu mô phỏng lấy từ sai số khớp, không phải khoảng tin cậy vật lý.',
              '- Cần thêm lượt đo độc lập và so điều khiển thực trên cùng hộp trước khi nói RL nâng hiệu năng.', '']
    (folder / 'KET_QUA.md').write_text('\n'.join(lines), encoding='utf-8')
    return report
