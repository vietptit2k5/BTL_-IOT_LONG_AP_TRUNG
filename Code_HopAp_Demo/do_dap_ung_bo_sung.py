"""Near-target identification experiment; does not train or deploy an RL policy."""
from __future__ import annotations

import argparse
from collections import deque
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import do_nhiet_hop as core


def slope(points):
    if len(points) < 3 or points[-1][0] - points[0][0] < 10:
        return None
    center = sum(x for x, _ in points) / len(points)
    denominator = sum((x-center)**2 for x, _ in points)
    return 60 * sum((x-center)*y for x, y in points) / denominator


class ResponseSurvey:
    def __init__(self, reverse=False, dwell=300, target=37., heat_levels=(50,25,75,0,100),
                 prepare_seconds=240, post_seconds=90, warm_seconds=600,single_target_full_matrix=False):
        core.finite_range(dwell, 120, 1800, 'Thời gian kích thích')
        core.finite_range(prepare_seconds, 30, 900, 'Thời gian chuẩn bị')
        core.finite_range(post_seconds, 30, 600, 'Thời gian sau tắt')
        core.finite_range(warm_seconds, 60, 1200, 'Thời gian làm ấm')
        self.prepare_seconds,self.post_seconds,self.warm_seconds = prepare_seconds,post_seconds,warm_seconds
        if target not in (33,35,37,37.2,37.5,37.8):
            raise ValueError('Chọn nền 33, 35, 37, 37.2, 37.5 hoặc 37.8°C.')
        if not heat_levels or any(h not in (0,25,50,75,100) for h in heat_levels):
            raise ValueError('Chọn mức bóng trong 0/25/50/75/100%.')
        self.target = float(target)
        self.lower = self.target-1
        self.upper = min(37.9,self.target+1)
        # Adjacent trials share heater duty; reverse the ENTIRE order on run 2.
        self.pairs = [(h, f) for h in dict.fromkeys(heat_levels) for f in (75, 100)]
        if reverse:
            self.pairs.reverse()
        self.dwell = dwell
        self.single_target_full_matrix = single_target_full_matrix
        self.limit = warm_seconds + len(self.pairs)*(prepare_seconds+dwell+post_seconds) + 2
        cap = core.MAX_SINGLE_TEMPERATURE_SECONDS if single_target_full_matrix else core.MAX_SURVEY_SECONDS
        if single_target_full_matrix and (len(self.pairs)!=10 or {h for h,_ in self.pairs}!={0,25,50,75,100}):
            raise ValueError('--mot-moc cần đủ5 mức bóng và hai mức quạt, không dùng tập mức con.')
        if self.limit > cap:
            if single_target_full_matrix:
                raise ValueError('Lịch một mốc vượt7giờ; giảm thời gian hoặc chia đợt, không cắt ngắn ngầm.')
            raise ValueError('Lịch vượt giới hạn 120 phút. Chia thành đợt ít mức bóng hơn bằng --muc-bong; không cắt ngắn ngầm lịch đo.')
        self.started = self.stage_at = self.last_sample_at = None
        self.stage = 'warm'
        self.index = 0
        self.points = deque()
        self.integral = 50.
        self.condition_lamp = 50.
        self.memory = 0.
        self.observed_at = None
        self.previous_lamp = 0.
        self.guard = False
        self.reference_memory = None
        self.completed = False
        self.records = []

    def observe_output(self, now, lamp_pct, fan_pct):
        if self.observed_at is not None:
            self.memory += (self.previous_lamp/100-self.memory)*(1-math.exp(-(now-self.observed_at)/25))
        self.observed_at, self.previous_lamp = now, lamp_pct

    def phase(self, suffix):
        return f'id_{self.index+1:02d}_{suffix}'

    def change_stage(self, stage, now):
        self.stage, self.stage_at = stage, now
        self.points.clear()
        self.last_sample_at = None

    def finish_probe(self, now, reason):
        self.records[-1].update(actual_probe_s=now-self.stage_at, end_reason=reason,
                                full_duration=reason == 'duration')
        self.change_stage('post', now)

    def __call__(self, now, reading):
        t = reading.temperature
        if t is None or not math.isfinite(t):
            raise core.SensorError('Cần DS18B20 hợp lệ.')
        if self.started is None:
            if t > 30:
                raise ValueError('Lượt đo bắt đầu ở nhiệt ≤30°C, hộp rỗng, bố trí giữ nguyên.')
            self.started = self.stage_at = now
        if t >= 38:
            self.guard = True
            if self.stage == 'probe':
                self.finish_probe(now, 'soft_guard_38c')
        if self.guard:
            if t > 37:
                return core.AutoDecision(self.phase('bao_ve_mem'), 0, 100, '38→37°C; thời gian vẫn tính vào giới hạn lượt.')
            self.guard = False
            self.points.clear()
        if self.stage == 'warm':
            if t < self.target-.3:
                if now-self.stage_at >= self.warm_seconds:
                    raise core.StopRun(f'Không đạt {self.target-.3:g}°C trong {self.warm_seconds:g}s làm ấm.')
                return core.AutoDecision('lam_am_co_gioi_han', 75, 100)
            self.change_stage('condition', now)
        if self.stage == 'post':
            if now-self.stage_at < self.post_seconds:
                return core.AutoDecision(self.phase('sau_tat'), 0, 75, f'Quan sát nhiệt dư sau khi tắt sưởi, tối đa {self.post_seconds:g}s.')
            self.index += 1
            if self.index == len(self.pairs):
                self.completed = True
                return None
            self.change_stage('condition', now)
        if self.stage == 'condition':
            if now-self.stage_at >= self.prepare_seconds:
                raise core.StopRun(f'Không đạt điều kiện đầu trong {self.prepare_seconds:g}s; không ép chạy phép thử không tương đương.')
            if reading.at != self.last_sample_at:
                dt = 0 if self.last_sample_at is None else reading.at-self.last_sample_at
                self.last_sample_at = reading.at
                self.points.append((reading.at, t))
                while self.points and reading.at-self.points[0][0] > 30:
                    self.points.popleft()
                rate = slope(list(self.points))
                error = self.target-t
                raw = self.integral+80*error-40*(rate or 0)
                if 0 <= raw <= 100 or (raw > 100 and error < 0) or (raw < 0 and error > 0):
                    self.integral = max(0., min(100., self.integral+.4*error*dt))
                self.condition_lamp = max(0., min(100., 5*round(raw/5)))
                stable = (len(self.points) >= 20 and self.points[-1][0]-self.points[0][0] >= 29
                          and all(abs(v-self.target) <= .125 for _, v in self.points)
                          and self.lower < t < self.upper
                          and rate is not None and abs(rate) <= .12)
                matched_memory = self.reference_memory is None or abs(self.memory-self.reference_memory) <= .1
                if stable and matched_memory:
                    if self.reference_memory is None:
                        self.reference_memory = self.memory
                    self.records.append(dict(trial=self.index+1, lamp=self.pairs[self.index][0],
                        fan=self.pairs[self.index][1], start_temperature_c=t,
                        start_slope_c_per_min=rate, start_heat_memory=self.memory,
                        actual_probe_s=None, end_reason='not_finished', full_duration=False))
                    self.change_stage('probe', now)
            if self.stage == 'condition':
                return core.AutoDecision(self.phase('chuan_bi'), self.condition_lamp, 75,
                    f'Đưa về {self.target:g}±0.125°C; xu hướng ≤0.12°C/phút trong 30s; bộ nhớ sưởi gần lượt đầu.')
        if self.stage == 'probe':
            reason = (f"upper_{self.upper:g}c".replace('.','_') if t >= self.upper else
                      f"lower_{self.lower:g}c".replace('.','_') if t <= self.lower else
                      'duration' if now-self.stage_at >= self.dwell else None)
            if reason:
                self.finish_probe(now, reason)
                return core.AutoDecision(self.phase('sau_tat'), 0, 75, reason)
            h, f = self.pairs[self.index]
            return core.AutoDecision(self.phase('kich_thich'), h, f,
                f'Giữ tổ hợp; dừng sớm nếu nhiệt ngoài ({self.lower:g},{self.upper:g})°C. Không phải RL.')
        raise RuntimeError('Trạng thái khảo sát không hợp lệ.')

    def metadata(self):
        return dict(kind='NEAR_TARGET_RESPONSE_V1', completed=self.completed,
            order=self.pairs, records=self.records, dwell_s=self.dwell,
            prepare_limit_s=self.prepare_seconds, post_s=self.post_seconds, warm_limit_s=self.warm_seconds,
            single_target_full_matrix=self.single_target_full_matrix,
            limit_s=self.limit, initial_target_c=self.target, initial_band_c=.125,
            probe_lower_c=self.lower, probe_upper_c=self.upper,
            initial_slope_limit_c_per_min=.12, heat_memory_tau_s=25,
            memory_tolerance=.1, reference_memory=self.reference_memory,
            soft_guard_c=[38, 37], hard_cutoff_c=38.5,
            evidence='One-probe empty-box identification; history matching is approximate, not equal wall temperatures.')


def analyze(log, profile, exit_code=None):
    with log.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    samples = [r for r in rows if r['event'] == 'MEASUREMENT' and r['temperature_c']
               and float(r['temperature_age_s']) < 3]
    result = []
    for record in profile['records']:
        prefix = f"id_{record['trial']:02d}_"
        commands = [r for r in rows if r['event'] == 'COMMAND' and r['phase'] == prefix+'kich_thich']
        item = dict(record)
        if commands:
            start = float(commands[0]['elapsed_s'])
            points = [(float(r['elapsed_s'])-start, float(r['temperature_c']))
                      for r in samples if r['phase'] == prefix+'kich_thich' and float(r['elapsed_s']) >= start]
            post = [(float(r['elapsed_s']), float(r['temperature_c'])) for r in samples
                    if r['phase'] in (prefix+'sau_tat', prefix+'bao_ve_mem')]
            item['sample_count'] = len(points)
            item['coverage_s'] = points[-1][0]-points[0][0] if len(points)>1 else 0
            item['max_gap_s'] = max((b[0]-a[0] for a,b in zip(points, points[1:])), default=None)
            for a,b in ((0,30),(30,90),(90,180),(180,300),(300,600),(600,900),(900,1200),(1200,1800)):
                item[f'slope_{a}_{b}_c_per_min'] = slope([p for p in points if a <= p[0] <= b])
            tail = [p for p in points if p[0] >= profile['dwell_s']-180]
            item['tail_180s_slope_c_per_min'] = slope(tail)
            item['tail_180s_span_c'] = max(v for _,v in tail)-min(v for _,v in tail) if tail else None
            item['tail_180s_coverage_s'] = tail[-1][0]-tail[0][0] if len(tail)>1 else 0
            if points:
                item.update(first_temperature_c=points[0][1], last_temperature_c=points[-1][1])
                item['peak_after_off_c'] = max((v for _,v in post), default=None)
                item['extra_rise_after_off_c'] = (max(v for _,v in post)-points[-1][1]) if post else None
            item['applied_levels_match'] = all(
                r.get('lamp_command_pct') and r.get('fan_command_pct')
                and float(r['lamp_command_pct']) == record['lamp']
                and float(r['fan_command_pct']) == record['fan']
                for r in samples if r['phase'] == prefix+'kich_thich')
            item['continuous_full_probe'] = bool(record['full_duration'] and len(points)>1
                and item['coverage_s'] >= profile['dwell_s']-5 and item['max_gap_s'] <= 3
                and item['applied_levels_match']
                and not any(r['event']=='ERROR' for r in rows))
        else:
            item.update(sample_count=0, continuous_full_probe=False)
        result.append(item)
    comparisons = []
    for h in (0,25,50,75,100):
        pair = {r['fan']:r for r in result if r['lamp']==h}
        if set(pair) != {75,100}:
            continue
        a,b = pair[75],pair[100]
        accepted = (a['continuous_full_probe'] and b['continuous_full_probe']
            and abs(a['start_temperature_c']-b['start_temperature_c']) <= .125
            and abs(a['start_slope_c_per_min']-b['start_slope_c_per_min']) <= .12
            and abs(a['start_heat_memory']-b['start_heat_memory']) <= .1)
        sa,sb = a.get('slope_30_90_c_per_min'),b.get('slope_30_90_c_per_min')
        comparisons.append(dict(lamp=h, matched_full_pair=accepted,
            fan100_minus_fan75_tail_slope_c_per_min=(b['tail_180s_slope_c_per_min']-a['tail_180s_slope_c_per_min']
                if accepted and a.get('tail_180s_coverage_s',0)>=175 and b.get('tail_180s_coverage_s',0)>=175
                and a.get('tail_180s_slope_c_per_min') is not None and b.get('tail_180s_slope_c_per_min') is not None else None),
            fan100_minus_fan75_slope_c_per_min=sb-sa if accepted and sa is not None and sb is not None else None))
    completed = (profile['completed'] and exit_code == 0 and any(r['event']=='END' for r in rows)
                 and not any(r['event']=='ERROR' for r in rows))
    return dict(status='COMPLETE' if completed else 'INCOMPLETE', exit_code=exit_code,
        source_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        sensor_ids=sorted({r['sensor_id'] for r in samples}), trials=result, comparisons=comparisons,
        full_trial_count=sum(r['continuous_full_probe'] for r in result),
        q_table_changed=False,
        limits='Descriptive single-run results, not proof of optimal RL, significance, spatial uniformity or measured energy.')


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    live = sub.add_parser('do')
    live.add_argument('--dao-thu-tu', action='store_true')
    live.add_argument('--do-dai', action='store_true',help='Mặc định chỉ bóng 50%; kích thích 20 phút, chuẩn bị ≤10 phút, sau tắt 5 phút, làm ấm ≤15 phút.')
    live.add_argument('--mot-moc',action='store_true',help='Tự đo đủ5 mức bóng ×2 mức quạt tại một mốc; mặc định20phút/tổ hợp, cả lượt tối đa khoảng6giờ5phút.')
    live.add_argument('--moi-to-hop', type=float, default=None,help='120–1800 giây. Mặc định 300s; với --do-dai là 1200s.')
    live.add_argument('--chuan-bi', type=float, default=None)
    live.add_argument('--sau-tat', type=float, default=None)
    live.add_argument('--lam-am', type=float, default=None)
    goal = live.add_mutually_exclusive_group()
    goal.add_argument('--nhiet-nen', type=float, choices=(33,35,37,37.2,37.5,37.8), default=None,
                      help='Nhiệt chuẩn bị trước từng tổ hợp; không phải thay setpoint RL.')
    goal.add_argument('--giai-doan',type=int,choices=(1,2,3),
                      help='Đo thực quanh mốc của giai đoạn1/2/3: 37.8/37.5/37.2°C; không chạy Q-table.')
    live.add_argument('--muc-bong', type=float, nargs='+', choices=(0,25,50,75,100),
                      default=None,help='Chọn mức bóng; mặc định toàn bộ, riêng --do-dai mặc định chỉ 50%.')
    live.add_argument('--dht11', action='store_true')
    live.add_argument('--khong-oled', action='store_true')
    live.add_argument('--sensor')
    live.add_argument('--dry-run', action='store_true')
    live.add_argument('--out', type=Path)
    offline = sub.add_parser('phan-tich')
    offline.add_argument('--thu-muc', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.command == 'do':
            long_mode = args.do_dai or args.mot_moc
            dwell = args.moi_to_hop if args.moi_to_hop is not None else (1200 if long_mode else 300)
            levels = args.muc_bong if args.muc_bong is not None else ([50,25,75,0,100] if args.mot_moc else
                                                                       [50] if args.do_dai else [50,25,75,0,100])
            prepare = args.chuan_bi if args.chuan_bi is not None else (600 if long_mode else 240)
            post = args.sau_tat if args.sau_tat is not None else (300 if long_mode else 90)
            warm = args.lam_am if args.lam_am is not None else (900 if long_mode else 600)
            stage_reference = None
            if args.giai_doan is not None:
                from lich_ap_ba_giai_doan import stage_for_day
                stage_reference=stage_for_day({1:1,2:11,3:18}[args.giai_doan])
            target = (stage_reference['target_c'] if stage_reference else
                      args.nhiet_nen if args.nhiet_nen is not None else 37.)
            policy = ResponseSurvey(args.dao_thu_tu,dwell,target,levels,prepare,post,warm,args.mot_moc)
            if args.dry_run:
                print('KHÔNG GPIO, KHÔNG TẠO DỮ LIỆU. Quạt luôn ≥75%.')
                print(f'Nền {policy.target:g}±0.125°C; kích thích trong ({policy.lower:g},{policy.upper:g})°C; điều kiện xu hướng/bộ nhớ sưởi giữ nguyên.')
                for i,(h,f) in enumerate(policy.pairs,1):
                    print(f'{i:02d}: chuẩn bị ≤{prepare:g}s; bóng {h}%/quạt {f}% ≤{policy.dwell:g}s; tắt bóng quan sát {post:g}s.')
                print(f'Làm ấm ≤{warm:g}s. Giới hạn cả lượt {policy.limit/60:.1f} phút + 10s quạt cuối. Không đạt nền thì dừng.')
                return 0
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
            folder = args.out or Path(__file__).resolve().parent/'ket_qua_dap_ung'/stamp
            folder.mkdir(parents=True, exist_ok=False)
            config = dict(profile=policy.metadata(), dht11=args.dht11, hardware_program_exit_code=None)
            config.update(stage_reference=stage_reference,
                          purpose='REAL_HARDWARE_RESPONSE_COLLECTION_NOT_RL_VALIDATION',
                          biological_tolerance_validated=False)
            config_path = folder/'cau_hinh.json'
            config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
            command = ['giu','--bong','0','--quat','100','--giay',str(policy.limit),
                       '--csv',str(folder/'du_lieu.csv'),'--ngat-nhiet','38.5','--tan-so-quat','100']
            if args.dht11:
                command.append('--dht11')
            if args.khong_oled:
                command.append('--khong-oled')
            if args.sensor:
                command += ['--sensor',args.sensor]
            print(f'KẾT QUẢ: {folder}\nĐo hộp rỗng, có người theo dõi; Ctrl+C để dừng. Không sửa Q-table.',flush=True)
            options=dict(control_policy=policy,max_session_seconds=core.MAX_SURVEY_SECONDS)
            if args.mot_moc:
                options.update(max_session_seconds=policy.limit,single_temperature_matrix=True)
            code = core.main(command,**options)
            config.update(profile=policy.metadata(),hardware_program_exit_code=code)
            config_path.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
        else:
            folder = args.thu_muc
            config = json.loads((folder/'cau_hinh.json').read_text(encoding='utf-8'))
            if config['profile']['kind'] != 'NEAR_TARGET_RESPONSE_V1':
                raise ValueError('Không đúng loại phép đo đáp ứng.')
            code = config.get('hardware_program_exit_code')
        log = folder/'du_lieu.csv'
        if not log.exists():
            print('Chưa có CSV; kiểm tra cảm biến/khởi tạo trước.')
            return code or 1
        result = analyze(log,config['profile'],code)
        (folder/'phan_tich.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        lines = ['# Đáp ứng nhiệt bổ sung', '', result['status'], '',
                 f"Không tự cập nhật Q-table. Thời gian yêu cầu mỗi tổ hợp: {config['profile']['dwell_s']:g}s; đoạn rút ngắn không phải cửa sổ đủ thời gian.", '',
                 '|Bóng|Quạt|Lý do kết thúc|Giây kích thích|dT/phút 30–90s|dT/phút 180s cuối lịch|Đủ cửa sổ liên tục|',
                 '|---|---|---|---|---|---|---|']
        for r in result['trials']:
            lines.append(f"|{r['lamp']}|{r['fan']}|{r['end_reason']}|{r['actual_probe_s']}|{r.get('slope_30_90_c_per_min')}|{r.get('tail_180s_slope_c_per_min')}|{r['continuous_full_probe']}|")
        lines += ['', 'Chênh lệch quạt chỉ được xuất khi cặp đủ thời gian và gần nhau về nhiệt, xu hướng, bộ nhớ sưởi ban đầu.',
                  'Một cặp chưa chứng minh khác biệt có ý nghĩa; cần lặp và đổi thứ tự. Xem phan_tich.json, giữ CSV gốc.']
        (folder/'KET_QUA.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print(f"{result['status']}: {folder/'KET_QUA.md'}",flush=True)
        return 0 if result['status']=='COMPLETE' else code or 1
    except (ValueError,OSError,KeyError) as exc:
        print(f'Lỗi: {exc}',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
