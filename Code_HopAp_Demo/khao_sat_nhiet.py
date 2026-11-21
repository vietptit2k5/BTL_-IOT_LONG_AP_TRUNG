#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tự khảo sát đáp ứng bóng/quạt, rồi thử hệ số reward trong mô phỏng từ CSV.

Trên Pi: python3 khao_sat_nhiet.py do
Chỉ xem kế hoạch: python3 khao_sat_nhiet.py do --dry-run
Phân tích lại, không GPIO: python3 khao_sat_nhiet.py phan-tich --log FILE.csv
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sys

import do_nhiet_hop as core


@dataclass(frozen=True)
class Probe:
    name: str
    seconds: float
    lamp: float
    fan: float
    warm: bool = False


class SurveyPolicy:
    """Kích thích có giới hạn; không phải RL khám phá ngẫu nhiên trên hộp thật."""

    def __init__(self, target=37.5, band=.5, seconds=5400,
                 heat_levels=(0, 25, 50, 75, 100), fan_levels=(75, 100),
                 seed=31, dwell=120, repeats=2):
        core.finite_range(seconds, 60, core.MAX_SURVEY_SECONDS, 'Giới hạn thời gian khảo sát')
        core.finite_range(band, .2, 1, 'Dung sai')
        core.finite_range(target, 20, 39 - band, 'Mục tiêu')
        core.finite_range(dwell, 30, 600, 'Thời gian mỗi tổ hợp')
        if not isinstance(repeats, int) or not 1 <= repeats <= 4:
            raise ValueError('Số lần lặp phải từ 1 đến 4.')
        for value in heat_levels:
            core.finite_range(value, 0, 100, 'Mức bóng')
        for value in fan_levels:
            core.finite_range(value, 1, 100, 'Mức quạt đã kiểm tra')
        heat_levels, fan_levels = sorted(set(heat_levels)), sorted(set(fan_levels))
        if len(heat_levels) < 3 or heat_levels[0] != 0 or len(fan_levels) < 2 or fan_levels[-1] != 100:
            raise ValueError('Cần ít nhất ba mức bóng gồm 0% và hai mức quạt gồm 100%.')
        self.target, self.band, self.seconds = target, band, seconds
        self.dwell, self.repeats = dwell, repeats
        self.heat_levels, self.fan_levels = heat_levels, fan_levels
        self.started = self.phase_started = None
        self.index = 0
        self.guard_at = None
        self.guard_count = 0
        self.completed = False
        self.warm_reached = False
        self.initial_temperature = None
        warm_heat = max(h for h in heat_levels if h <= 75)
        self.phases = [Probe('nen_ban_dau', 60, 0, 100),
                       Probe('lam_am_co_gioi_han', 180, warm_heat, 100, True)]
        rng = random.Random(seed)
        previous = None
        for repeat in range(repeats):
            pairs = [(h, f) for h in heat_levels for f in fan_levels]
            rng.shuffle(pairs)
            if pairs[0] == previous:
                pairs[0], pairs[1] = pairs[1], pairs[0]
            for h, f in pairs:
                name = f'thu_{repeat + 1}_bong_{h:g}_quat_{f:g}'
                self.phases.append(Probe(name, dwell, h, f))
            previous = pairs[-1]
        self.phases.append(Probe('ngung_suoi_cuoi', 120, 0, 100))
        self.nominal_seconds = sum(p.seconds for p in self.phases)

    def __call__(self, now, reading):
        temperature = reading.temperature
        if temperature is None:
            raise core.SensorError('Khảo sát cần số đo hợp lệ.')
        if self.started is None:
            self.started = self.phase_started = now
            self.initial_temperature = temperature
        if self.index >= len(self.phases):
            self.completed = True
            return None
        # Hysteresis: dừng sưởi ở target + band, trở lại ở target - band.
        if self.guard_at is not None:
            if temperature > self.target - self.band:
                return core.AutoDecision(f'bao_ve_mem_{self.guard_count}', 0, 100,
                                         'Tạm ngừng kích thích; chỉ tuần hoàn khí.')
            self.phase_started += now - self.guard_at
            self.guard_at = None
        if temperature >= self.target + self.band and self.index < len(self.phases) - 1:
            self.guard_at = now
            self.guard_count += 1
            return core.AutoDecision(f'bao_ve_mem_{self.guard_count}', 0, 100,
                                     'Ngắt sưởi mềm; thời gian chờ vẫn nằm trong giới hạn cả lượt.')
        while self.index < len(self.phases):
            phase = self.phases[self.index]
            warm_done = phase.warm and temperature >= self.target - self.band
            if warm_done:
                self.warm_reached = True
            if warm_done or now - self.phase_started >= phase.seconds:
                self.index += 1
                self.phase_started = now
            else:
                return core.AutoDecision(phase.name, phase.lamp, phase.fan,
                                         'Kích thích khảo sát; % là duty lệnh, chưa đo W/RPM.')
        self.completed = True
        return None

    def metadata(self):
        return {'completed_schedule': self.completed, 'warm_target_reached': self.warm_reached,
                'soft_guard_count': self.guard_count, 'initial_temperature_c': self.initial_temperature,
                'nominal_seconds': self.nominal_seconds, 'wall_time_limit_s': self.seconds,
                'seconds_per_combination': self.dwell, 'repeats': self.repeats,
                'phases': [asdict(p) for p in self.phases]}


def make_parser():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    live = sub.add_parser('do', help='Khảo sát hộp rỗng có giám sát; không phải ấp trứng thật.')
    limit = live.add_mutually_exclusive_group()
    limit.add_argument('--giay', type=float, default=None, help='Giới hạn cả lượt theo giây; không đổi thời gian từng tổ hợp.')
    limit.add_argument('--gioi-han-phut', type=float, default=None, help='Giới hạn cả lượt, mặc định 90 phút, tối đa 120 phút.')
    live.add_argument('--moi-to-hop', type=float, default=120, help='Giây quan sát mỗi tổ hợp; mặc định 120, cho phép 30–600.')
    live.add_argument('--lap', type=int, default=2, help='Số lần thử mỗi tổ hợp, mặc định 2.')
    live.add_argument('--muc-bong', type=float, nargs='+', default=[0, 25, 50, 75, 100])
    live.add_argument('--muc-quat', type=float, nargs='+', default=[75, 100])
    live.add_argument('--thu-tu', type=int, default=31, help='Seed thứ tự các kích thích có giới hạn.')
    live.add_argument('--sensor')
    live.add_argument('--tan-so-quat', type=float, default=100)
    live.add_argument('--khong-oled', action='store_true')
    live.add_argument('--oled-dia-chi', type=core.address_arg)
    live.add_argument('--oled-cao', type=int, choices=(32, 64), default=64)
    live.add_argument('--dry-run', action='store_true')
    for child in (live, sub.add_parser('phan-tich', help='Chỉ phân tích/tune offline, không GPIO.')):
        child.add_argument('--muc-tieu', type=float, default=37.5)
        child.add_argument('--dung-sai', type=float, default=.5)
        child.add_argument('--episodes', type=int, default=250)
        child.add_argument('--chi-do', action='store_true', help='Chỉ phân tích đáp ứng, chưa thử reward/Q-learning.')
        child.add_argument('--out', type=Path, help='Thư mục kết quả mới, từ chối ghi đè thư mục đã có.')
    offline = sub.choices['phan-tich']
    offline.add_argument('--log', action='append', required=True, type=Path, help='Lặp --log để gộp nhiều lượt cùng cấu hình.')
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = make_parser()
    args = parser.parse_args(argv)
    try:
        core.finite_range(args.muc_tieu, 20, 38.8, 'Mục tiêu')
        core.finite_range(args.dung_sai, .2, 1, 'Dung sai')
        if not 10 <= args.episodes <= 5000:
            raise ValueError('--episodes phải từ 10 đến 5000.')
        policy = None
        if args.command == 'do':
            core.finite_range(args.tan_so_quat, 1, 1000, 'Tần số quạt')
            args.giay = (args.giay if args.giay is not None else
                         60 * (args.gioi_han_phut if args.gioi_han_phut is not None else 90))
            policy = SurveyPolicy(args.muc_tieu, args.dung_sai, args.giay,
                                  args.muc_bong, args.muc_quat, args.thu_tu,
                                  dwell=args.moi_to_hop, repeats=args.lap)
    except ValueError as exc:
        parser.error(str(exc))
    if args.command == 'do' and args.dry_run:
        print('KẾ HOẠCH, KHÔNG GPIO, KHÔNG CẢM BIẾN, KHÔNG TẠO SỐ ĐO:')
        for phase in policy.phases:
            print(f'{phase.name}: tối đa {phase.seconds:g}s, bóng {phase.lamp:g}%, quạt {phase.fan:g}%')
        print(f'Lịch danh định tối đa {policy.nominal_seconds / 60:g} phút; giới hạn cả lượt {args.giay / 60:g} phút.')
        print(f'Ngắt mềm {args.muc_tieu + args.dung_sai:g}°C, dừng phần mềm 40°C. Đoạn bị ngắt không được tính là cửa sổ liên tục đủ thời gian.')
        return 0
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    folder = args.out or Path(__file__).resolve().parent / 'ket_qua_khao_sat' / stamp
    try:
        folder.mkdir(parents=True, exist_ok=False)
        live_code = 0
        if args.command == 'do':
            log = folder / 'du_lieu.csv'
            config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
            config['schedule'] = policy.metadata()
            (folder / 'cau_hinh.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
            command = ['giu', '--bong', '0', '--quat', '100', '--giay', str(args.giay),
                       '--csv', str(log), '--ngat-nhiet', '40', '--tan-so-quat', str(args.tan_so_quat),
                       '--oled-cao', str(args.oled_cao)]
            if args.sensor:
                command += ['--sensor', args.sensor]
            if args.khong_oled:
                command.append('--khong-oled')
            if args.oled_dia_chi is not None:
                command += ['--oled-dia-chi', hex(args.oled_dia_chi)]
            print(f'KẾT QUẢ: {folder}\nLịch danh định tối đa {policy.nominal_seconds / 60:g} phút, giới hạn {args.giay / 60:g} phút.\n'
                  'Tự đổi mức, không cần nhập lệnh. Ctrl+C để dừng.', flush=True)
            if args.giay < policy.nominal_seconds:
                print('Giới hạn cả lượt ngắn hơn lịch; kết quả có thể thiếu tổ hợp/thời gian quan sát.', flush=True)
            live_code = core.main(command, control_policy=policy, max_session_seconds=core.MAX_SURVEY_SECONDS)
            config['schedule'] = policy.metadata()
            config['hardware_program_exit_code'] = live_code
            (folder / 'cau_hinh.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
            args.log = [log]
            if not log.is_file():
                print('Chưa có CSV: sửa lỗi cảm biến/khởi tạo ở trên trước khi đo lại.', file=sys.stderr)
                return live_code or 1
        from phan_tich_reward import analyze
        report = analyze(args.log, folder / 'phan_tich', args.muc_tieu, args.dung_sai,
                         episodes=args.episodes, tune=not args.chi_do and live_code == 0,
                         live_metadata=policy.metadata() if policy is not None else None)
        print(f"PHÂN TÍCH: {report['status']}\nXem: {folder / 'phan_tich' / 'KET_QUA.md'}", flush=True)
        return live_code
    except (OSError, ValueError) as exc:
        print(f'Lỗi khảo sát/phân tích: {exc}', file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print('Đã dừng khảo sát/phân tích. CSV đã ghi được vẫn giữ lại.', file=sys.stderr, flush=True)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
