#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ấp 3 giai đoạn: RL tự đổi mốc 37,8 / 37,5 / 37,2 °C theo NGÀY trong trang_thai_me_ap.json.

    python3 me_ap.py bat-dau --ngay 5              # tạo/đặt mẻ (một lần)
    .venv/bin/python ap_trung.py --phut 30          # chạy có giám sát; hộp rỗng, bắt đầu ≤ 30 °C
    python3 me_ap.py dat-ngay 12                    # (cửa sổ khác hoặc từ app) đổi ngày khi đang chạy

Dùng NGUYÊN Q-table Q2 đã thử trên hộp thật (goi_rl_moi_20261120.json, mốc 37,5 °C, vùng ±0,2 °C).
Trạng thái của Q2 là sai lệch so với 37,5 °C, nên với mốc M chương trình đưa vào Q nhiệt độ đã dịch
T − (M − 37,5): cùng chính sách, khác mốc. Kiểm chứng mô phỏng: Code_HopAp_PhanTich/mo_phong_ba_giai_doan.py.

An toàn (độc lập với Q và với ngày): ngắt mềm 38,3 → 37,8 °C (bóng 0 %, quạt 100 %), dừng cứng 38,8 °C
(do_nhiet_hop), mất số đo 3 s thì dừng, KSD301 phần cứng. Không học online. State chưa học: phía trên mốc
thì làm mát (bóng 0 %, quạt 100 %), phía dưới thì làm ấm phục hồi; không bao giờ tự tăng sưởi khi đã nóng.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import do_nhiet_hop as core
from chinh_sach_nhiet import ReferenceController, SoftGuard
import me_ap
from rl_vung_on_dinh import state_id
from thu_rl_du_lieu_moi import ACTIONS, PACKAGE_SHA256, read_package

Q_CENTER = 37.5                 # Mốc mà Q2 đã học.
WARM_HANDOVER_BELOW = 0.5       # Giao cho Q khi T ≥ mốc − 0,5 °C (37,0 °C với mốc 37,5 như lượt đã đo).
RECOVERY_ENTER_BELOW = 0.9      # Dưới mốc − 0,9 °C thì làm ấm phục hồi (36,6 °C với mốc 37,5).
RECOVERY_EXIT_BELOW = 0.5
WARM_LIMIT_S = 900
RECOVERY_TIMEOUT_S = 450
CONTROL_PERIOD_S = 5
MAX_MINUTES = 100               # Lượt thử (dòng lệnh): do_nhiet_hop giới hạn phiên 7200 s (gồm làm ấm 900 s).
MAX_MINUTES_ME = 1440           # Ấp theo mẻ (--theo-me, bridge tự chạy): mỗi phiên ≤ 1 ngày; bridge nối phiên tới ngày 21.
COOL = 1                        # ACTIONS[1] = bóng 0 %, quạt 100 %.
CONTROLLERS = {'rl': 'Q-learning 3 giai đoạn', 'thermostat': 'Thermostat 3 giai đoạn'}
CONFIG_KEYS = {'rl': 'ap-trung', 'thermostat': 'ap-trung-thermostat'}
WARM = (75, 100)
# Chỉnh tay từ app: chỉ các cặp (bóng, quạt) đã khảo sát = 9 hành động của Q-table; bóng bật thì quạt không tắt.
MANUAL_PAIRS = {(round(h * 100), round(f * 100)) for h, f in ACTIONS}
TAY_FILE = Path(__file__).with_name('lenh_tay.json')
NAO_FILE = Path(__file__).with_name('nao_rl.json')  # "RL đang nghĩ gì": bridge đọc và đưa lên app.


def decode_state(state):
    """Ngược của rl_vung_on_dinh.state_id: các thành phần của trạng thái Q2 (để giải thích trên app)."""
    guard, state = state % 2, state // 2
    previous, state = state % 9, state // 9
    stored, state = state % 5, state // 5
    trend, error_bin = state % 3, state // 3
    return {'sai_so': error_bin, 'xu_huong': trend, 'nho_nhiet': stored, 'truoc': previous, 'bao_ve': guard}


def phase_name(info, suffix=''):
    return f'ap_ngay{info["ngay"]:02d}_gd{info["giai_doan"]}{suffix}'


class ApTrungPolicy:
    """Policy cho do_nhiet_hop.main(control_policy=...). now là đồng hồ đơn điệu; lịch dùng giờ thật."""

    def __init__(self, package, minutes=30, lich_path=me_ap.MAC_DINH, wall_clock=time.time,
                 check_start_temperature=True, controller='rl', tay_path=TAY_FILE, nao_path=None,
                 max_minutes=MAX_MINUTES):
        if not 1 <= minutes <= max_minutes:
            raise ValueError(f'--phut phải trong 1–{max_minutes}.')
        if controller not in CONTROLLERS:
            raise ValueError(f'Bộ điều khiển phải là một trong {sorted(CONTROLLERS)}.')
        self.controller = controller
        # Đối chứng: thermostat đã chốt (doi_chung_kiem_tra.json), mốc lấy theo lịch giống RL.
        self.thermostat = None
        if controller == 'thermostat':
            config = json.loads(Path(__file__).with_name('doi_chung_kiem_tra.json').read_text(encoding='utf-8'))
            if config.get('purpose') != 'REFERENCE_CONTROLLER_ONLY' or config['actions'] != ACTIONS:
                raise ValueError('doi_chung_kiem_tra.json không khớp tập hành động đã đo.')
            self.thermostat = ReferenceController(config['configuration'], Q_CENTER, ACTIONS)
        self.package, self.minutes, self.lich_path, self.wall = package, minutes, Path(lich_path), wall_clock
        self.tay_path, self.manual_active = Path(tay_path), False
        self.nao_path = None if nao_path is None else Path(nao_path)  # None: không ghi (mô phỏng, kiểm thử)
        self._nao_mode = self._nao_at = None
        self.created_wall = wall_clock()  # Lệnh tay ghi trước lượt này (lượt cũ) thì bỏ qua.
        self.check_start = check_start_temperature
        self.model = package['model']
        self.guard = SoftGuard(target=(me_ap.NGAT_MEM_C + me_ap.BAT_LAI_C) / 2,
                               band=(me_ap.NGAT_MEM_C - me_ap.BAT_LAI_C) / 2)
        self.info = me_ap.current(me_ap.load(self.lich_path), self.wall())  # Không có lịch thì không chạy.
        self.started = self.hold_started = self.last_control = None
        self.sample_at = self.sample_temperature = None
        self.output_at = None
        self.last_heat, self.memory, self.previous = 0.0, 0.0, COOL
        self.sensor_bound = self.completed = False
        self.decision = None
        self.recovery_started = None
        self.lich_error = None
        self.stats = {'quyet_dinh': 0, 'du_phong_lam_mat': 0, 'phuc_hoi': 0, 'chuyen_giai_doan': 0,
                      'doi_ngay': 0, 'loi_doc_lich': 0}
        self.states = set()
        self.history = [dict(self.info, luc_s=0.0)]
        self.initial_temperature = None

    # ---- giao diện với do_nhiet_hop
    def bind_sensor(self, sensor_id):
        if sensor_id != self.package['sensor_id']:
            raise core.SensorError('Đầu dò khác dữ liệu huấn luyện; dừng.')
        self.sensor_bound = True

    def observe_output(self, now, lamp_pct, fan_pct):
        if not all(math.isfinite(v) for v in (now, lamp_pct, fan_pct)):
            raise ValueError('Lệnh đầu ra không hữu hạn.')
        if self.output_at is not None:
            dt = now - self.output_at
            if dt < 0:
                raise ValueError('Thời gian điều khiển đi lùi.')
            self.memory += (self.last_heat - self.memory) * (-math.expm1(-dt / self.model['tau']))
        self.output_at, self.last_heat = now, lamp_pct / 100
        self.previous = min(range(len(ACTIONS)), key=lambda i: abs(ACTIONS[i][0] - lamp_pct / 100)
                            + abs(ACTIONS[i][1] - fan_pct / 100))

    # ---- lịch
    def refresh_schedule(self, now):
        try:
            info = me_ap.current(me_ap.load(self.lich_path), self.wall())
            self.lich_error = None
        except me_ap.LichError as exc:  # File hỏng/đang thay: giữ mốc cũ, không dừng, ghi nhận.
            if self.lich_error is None:
                self.stats['loi_doc_lich'] += 1
            self.lich_error = str(exc)
            return
        if info['ngay'] != self.info['ngay']:
            self.stats['doi_ngay'] += 1
            if info['giai_doan'] != self.info['giai_doan']:
                self.stats['chuyen_giai_doan'] += 1
            self.history.append(dict(info, luc_s=None if self.started is None else round(now - self.started, 1)))
            self.last_control = None  # Quyết định lại ngay với mốc mới.
        self.info = info

    def demo_clock(self, action, now=None):
        """Mẻ demo rút gọn: chạy lịch khi RL giữ nhiệt, dừng lịch khi lượt kết thúc. Mẻ thật: không đổi gì."""
        try:
            (me_ap.resume if action == 'resume' else me_ap.pause)(self.lich_path, self.wall(), nguon='ap_trung')
            self.stats['lich_' + action] = self.stats.get('lich_' + action, 0) + 1
        except me_ap.LichError as exc:
            self.lich_error = str(exc)
            return
        if action == 'resume' and now is not None:
            self.refresh_schedule(now)

    # ---- vòng điều khiển
    def __call__(self, now, reading):
        t = reading.temperature
        if not self.sensor_bound or self.output_at is None:
            raise core.SensorError('Chưa liên kết cảm biến hoặc lệnh đầu ra.')
        if t is None or not math.isfinite(t) or not math.isfinite(reading.at) or not 0 <= now - reading.at < 3:
            raise core.SensorError('Số đo nhiệt không hợp lệ/quá hạn.')
        if self.started is None:
            if self.check_start and t > 30:
                raise ValueError('Hộp còn trên 30 °C; để nguội rồi chạy lại.')
            self.started, self.initial_temperature = now, t
        if self.last_control is None or now - self.last_control >= CONTROL_PERIOD_S:
            self.refresh_schedule(now)
        target = self.info['muc_tieu_c']
        was_guard = self.guard.active
        self.guard.update(t)

        if self.hold_started is None:  # Làm ấm theo quy tắc, giao cho Q khi gần mốc.
            if now - self.started >= WARM_LIMIT_S:
                raise ValueError(f'Hết {WARM_LIMIT_S}s làm ấm mà chưa tới {target - WARM_HANDOVER_BELOW:.1f} °C; dừng.')
            self._track_trend(reading)
            if self.guard.active or t < target - WARM_HANDOVER_BELOW:
                self._think(now, 'lam_am', nhiet_c=round(t, 3))
                return core.AutoDecision('lam_am_ap', 0 if self.guard.active else WARM[0], WARM[1],
                                         f'Làm ấm tới {target - WARM_HANDOVER_BELOW:.1f} °C; {me_ap.describe(self.info)}')
            self.hold_started = now
            self.last_control = None
            self.demo_clock('resume', now)  # Mẻ demo: lịch chỉ chạy từ lúc RL nhận điều khiển.

        if now - self.hold_started >= self.minutes * 60:
            self.completed = True
            self.demo_clock('pause', now)
            return None
        if self.guard.active:
            self.recovery_started, self.last_control = None, None
            self._think(now, 'bao_ve', nhiet_c=round(t, 3))
            return core.AutoDecision(phase_name(self.info, '_bao_ve'), 0, 100,
                                     f'Ngắt mềm {me_ap.NGAT_MEM_C}→{me_ap.BAT_LAI_C} °C (cố định, không theo ngày).')
        if was_guard:
            self.last_control = None
        manual = self.manual_command()  # Sau bảo vệ, trước RL: bảo vệ luôn thắng lệnh tay.
        if manual is not None:
            lamp, fan, remaining, who = manual
            if not self.manual_active:
                self.stats['chinh_tay'] = self.stats.get('chinh_tay', 0) + 1
            self.manual_active, self.recovery_started, self.last_control = True, None, None
            self._track_trend(reading)
            self._think(now, 'tay', nhiet_c=round(t, 3), bong=lamp, quat=fan, con_lai_s=round(remaining), boi=who)
            return core.AutoDecision(phase_name(self.info, '_tay'), lamp, fan,
                                     f'Chỉnh tay ({who}): bóng {lamp} %, quạt {fan} %, còn {remaining:.0f} s; '
                                     f'{me_ap.describe(self.info)}')
        if self.manual_active:  # Vừa hết hạn hoặc trả về: RL quyết định lại ngay.
            self.manual_active, self.last_control = False, None
        if self.recovery_started is not None or t < target - RECOVERY_ENTER_BELOW:
            decision = self._recover(now, reading, target)
            if decision is not None:
                return decision
        if self.last_control is None or now - self.last_control >= CONTROL_PERIOD_S:
            self.decision = self._q_decision(now, reading, t, target)
        return self.decision

    def manual_command(self):
        """Lệnh tay còn hạn trong lenh_tay.json (bridge ghi từ app): (bóng, quạt, giây còn lại, người) hoặc None."""
        try:
            data = json.loads(self.tay_path.read_text(encoding='utf-8'))
            lamp, fan, until = int(data['bong']), int(data['quat']), float(data['het_han'])
            written = float(data['ghi_luc'])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        remaining = until - self.wall()
        if remaining <= 0 or written < self.created_wall or (lamp, fan) not in MANUAL_PAIRS:
            return None
        return lamp, fan, remaining, str(data.get('by', '?'))[:60]

    def _think(self, now, mode, **extra):
        """Ghi nao_rl.json (nguyên khối). Chế độ không phải quyết định Q/thermostat: tối đa mỗi 5 s một lần."""
        if self.nao_path is None:
            return
        if (mode == self._nao_mode and mode not in ('q', 'thermostat') and self._nao_at is not None
                and now - self._nao_at < CONTROL_PERIOD_S):
            return
        data = {'ts': int(self.wall() * 1000), 'che_do': mode, 'bo_dieu_khien': self.controller,
                'muc_tieu_c': self.info['muc_tieu_c'], 'vung_c': list(self.info['vung_c']), 'ngay': self.info['ngay'],
                'giai_doan': self.info['giai_doan'], **extra}
        try:
            temp = self.nao_path.with_suffix('.tmp')
            temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            os.replace(temp, self.nao_path)
        except OSError:
            return  # Không bao giờ để việc hiển thị làm hỏng vòng điều khiển.
        self._nao_mode, self._nao_at = mode, now

    def _track_trend(self, reading):
        if self.sample_at is None or reading.at - self.sample_at >= CONTROL_PERIOD_S:
            self.sample_at, self.sample_temperature = reading.at, reading.temperature

    def _thermostat_decision(self, now, reading, t, target):
        d = self._delta(reading, t)
        self.thermostat.target = target
        action = self.thermostat.select(t, d)
        heat, fan = ACTIONS[action]
        self.last_control, self.sample_at, self.sample_temperature = now, reading.at, t
        self.stats['quyet_dinh'] += 1
        self._think(now, 'thermostat', nhiet_c=round(t, 3), dT5=round(d, 4), chon=action)
        return core.AutoDecision(phase_name(self.info), heat * 100, fan * 100,
                                 f'Thermostat ±0,1 °C quanh mốc {target:.1f} °C; dT5={d:+.3f}; {me_ap.describe(self.info)}')

    def _delta(self, reading, t):
        if self.sample_at is None or reading.at <= self.sample_at:
            return 0.0
        return (t - self.sample_temperature) * CONTROL_PERIOD_S / (reading.at - self.sample_at)

    def _q_decision(self, now, reading, t, target):
        if self.thermostat is not None:
            return self._thermostat_decision(now, reading, t, target)
        shifted = t - (target - Q_CENTER)
        if not self.model['low'] <= shifted <= self.model['high']:
            raise ValueError(f'Nhiệt đã dịch {shifted:.2f} °C ngoài miền mô hình; dừng, không ngoại suy.')
        d = self._delta(reading, t)
        state = state_id(shifted, d, self.memory, self.previous, False)
        seen = [i for i, n in enumerate(self.package['policy']['visits'][state]) if n > 0]
        info = self.info
        if seen:
            action = max(seen, key=lambda i: self.package['policy']['q'][state][i])
            note = f'Q2 dịch mốc {target:.1f} °C; state={state}; dT5={d:+.3f}; {me_ap.describe(info)}'
        else:
            action = COOL if shifted >= Q_CENTER else None
            if action is None:  # Lạnh và chưa học: làm ấm phục hồi thay vì đoán.
                return self._recover(now, reading, target, force=True)
            self.stats['du_phong_lam_mat'] += 1
            note = f'State {state} chưa học, đang trên mốc: làm mát an toàn; {me_ap.describe(info)}'
        heat, fan = ACTIONS[action]
        self.last_control, self.sample_at, self.sample_temperature = now, reading.at, t
        self.stats['quyet_dinh'] += 1
        self.states.add(state)
        q_row, visits = self.package['policy']['q'][state], self.package['policy']['visits'][state]
        self._think(now, 'q', nhiet_c=round(t, 3), nhiet_dich_c=round(shifted, 3), dT5=round(d, 4), state=state,
                    thanh_phan=decode_state(state), chon=action, ly_do='q_max' if seen else 'chua_hoc_lam_mat',
                    q=[round(float(q_row[i]), 4) if visits[i] > 0 else None for i in range(len(ACTIONS))],
                    so_lan=[int(v) for v in visits])
        return core.AutoDecision(phase_name(info), heat * 100, fan * 100, note)

    def _recover(self, now, reading, target, force=False):
        if self.recovery_started is None:
            self.recovery_started = now
            self.stats['phuc_hoi'] += 1
        if now - self.recovery_started >= RECOVERY_TIMEOUT_S:
            raise ValueError(f'Làm ấm phục hồi quá {RECOVERY_TIMEOUT_S}s; dừng.')
        if reading.temperature >= target - RECOVERY_EXIT_BELOW and not force:
            self.recovery_started, self.last_control = None, None
            return None
        if force and reading.temperature >= target - RECOVERY_EXIT_BELOW:
            self.recovery_started = None
        self._track_trend(reading)
        self.last_control = None if not force else now
        self._think(now, 'phuc_hoi', nhiet_c=round(reading.temperature, 3))
        return core.AutoDecision(phase_name(self.info, '_phuc_hoi'), WARM[0], WARM[1],
                                 f'Làm ấm phục hồi tới {target - RECOVERY_EXIT_BELOW:.1f} °C; {me_ap.describe(self.info)}')

    def metadata(self):
        return {
            'bo_dieu_khien': CONTROLLERS[self.controller], 'controller': self.controller, 'completed': self.completed,
            'initial_temperature_c': self.initial_temperature,
            'warm_elapsed_s': None if self.hold_started is None else self.hold_started - self.started,
            'requested_minutes': self.minutes, 'q_updates': 0, 'package_sha256': PACKAGE_SHA256,
            'q_center_c': Q_CENTER, 'stages': [dict(s, vung_c=list(s['vung_c']),
                                                    do_am_khuyen_nghi=list(s['do_am_khuyen_nghi']))
                                               for s in me_ap.STAGES],
            'soft_guard_c': [me_ap.NGAT_MEM_C, me_ap.BAT_LAI_C], 'hard_cutoff_c': me_ap.DUNG_CUNG_C,
            'soft_guard_count': self.guard.count, 'control_period_s': CONTROL_PERIOD_S,
            'lich': self.history, 'lich_loi_cuoi': self.lich_error, 'thong_ke': self.stats,
            'states': sorted(self.states),
        }


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--phut', type=int, default=30,
                        help=f'Thời gian điều khiển sau làm ấm (1–{MAX_MINUTES}; với --theo-me tới {MAX_MINUTES_ME}).')
    parser.add_argument('--theo-me', action='store_true',
                        help='Một phiên của mẻ ấp do bridge tự chạy: không đòi hộp ≤ 30 °C lúc bắt đầu (phiên nối tiếp '
                             'khi hộp đang ấm), phiên dài tới 1 ngày. Mọi bảo vệ nhiệt/cảm biến giữ nguyên.')
    parser.add_argument('--bo-dieu-khien', choices=sorted(CONTROLLERS), default='rl',
                        help='rl = Q2 dịch mốc (mặc định); thermostat = đối chứng, cùng lịch/bảo vệ/CSV.')
    parser.add_argument('--dht11', action='store_true', help='Tự đọc DHT11 ở GPIO17 (khi do_am.py KHÔNG chạy).')
    parser.add_argument('--do-am', action='store_true',
                        help='Lấy độ ẩm từ do_am_moi_nhat.json của do_am.py (dịch vụ hop-ap-do-am); không mở GPIO17.')
    parser.add_argument('--khong-oled', action='store_true')
    parser.add_argument('--lich', type=Path, default=me_ap.MAC_DINH)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    data = read_package(Path(__file__).with_name('goi_rl_moi_20261120.json'))
    try:
        policy = ApTrungPolicy(data, args.phut, args.lich, controller=args.bo_dieu_khien, nao_path=NAO_FILE,
                               check_start_temperature=not args.theo_me,
                               max_minutes=MAX_MINUTES_ME if args.theo_me else MAX_MINUTES)
    except me_ap.LichError as exc:
        print(f'LỖI: {exc}', file=sys.stderr)
        return 1
    print(f'{CONTROLLERS[args.bo_dieu_khien]}. {me_ap.describe(policy.info)}', flush=True)
    if args.dry_run:
        print(f'Q2 dịch mốc theo ngày; làm ấm ≤{WARM_LIMIT_S}s, điều khiển {args.phut} phút; ngắt mềm '
              f'{me_ap.NGAT_MEM_C}→{me_ap.BAT_LAI_C} °C, dừng cứng {me_ap.DUNG_CUNG_C} °C. Không GPIO trong dry-run.')
        return 0
    folder = args.out or Path(__file__).resolve().parent / 'ket_qua_ap_trung' / \
        (datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + f'_{args.bo_dieu_khien}')
    folder.mkdir(parents=True, exist_ok=False)
    config = {'bo_dieu_khien': CONFIG_KEYS[args.bo_dieu_khien], 'profile': policy.metadata(),
              'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'dht11': args.dht11,
              'do_am_tu_file': args.do_am}
    (folder / 'cau_hinh.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'KẾT QUẢ: {folder}\nChỉnh ngày khi đang chạy: python3 me_ap.py dat-ngay N (hoặc từ app).', flush=True)
    command = ['giu', '--bong', '0', '--quat', '100', '--giay', str(WARM_LIMIT_S + args.phut * 60 + 5),
               '--csv', str(folder / 'du_lieu.csv'), '--sensor', data['sensor_id'],
               '--ngat-nhiet', str(me_ap.DUNG_CUNG_C), '--tan-so-quat', '100']
    if args.dht11 and args.do_am:
        print('LỖI: chọn một trong --dht11 hoặc --do-am.', file=sys.stderr)
        return 2
    if args.dht11:
        command.append('--dht11')
    if args.do_am:
        command += ['--do-am-file', str(Path(__file__).with_name('do_am_moi_nhat.json'))]
    if args.khong_oled:
        command.append('--khong-oled')
    code = core.main(command, control_policy=policy, incubation=args.theo_me,
                     max_session_seconds=core.MAX_INCUBATION_SECONDS if args.theo_me else core.MAX_SURVEY_SECONDS)
    policy.demo_clock('pause')  # Kết thúc theo bất kỳ cách nào (hết giờ, dừng khẩn cấp, lỗi): đứng lịch demo.
    config.update(profile=policy.metadata(), hardware_program_exit_code=code)
    (folder / 'cau_hinh.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    return code if code else 0 if policy.completed else 1


if __name__ == '__main__':
    raise SystemExit(main())
