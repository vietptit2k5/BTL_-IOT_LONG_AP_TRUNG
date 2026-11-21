#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lịch mẻ ấp 21 ngày, 3 giai đoạn, lưu bền trong trang_thai_me_ap.json. KHÔNG mở GPIO.

    python3 me_ap.py xem                          # ngày, giai đoạn, mốc nhiệt hiện tại
    python3 me_ap.py bat-dau                      # bắt đầu mẻ mới từ ngày 1 (thời gian thật)
    python3 me_ap.py bat-dau --ngay 9 --giay-moi-ngay 120   # demo: 1 ngày = 2 phút
    python3 me_ap.py dat-ngay 12                  # chỉnh sang ngày 12; sau đó ngày vẫn tự tăng

"Chỉnh ngày" dời thời điểm bắt đầu mẻ: bat_dau = bây giờ − (N−1) × giây_mỗi_ngày. Chương trình
điều khiển (ap_trung.py) đọc lại file mỗi chu kỳ 5 s nên đổi mốc ngay trong lúc chạy.
Mốc nhiệt theo Bản tin Khuyến nông Việt Nam số 04/2026 (xem TAI_LIEU_NHIET_DO_BA_GIAI_DOAN.md);
vùng ±0,2 °C là thiết kế kỹ thuật của demo, không phải dung sai sinh học do nguồn quy định.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time

SO_NGAY = 21
GIAY_MOI_NGAY_THAT = 86400
GIAY_MOI_NGAY_TOI_THIEU = 30           # Demo rút gọn nhanh nhất: 1 ngày = 30 s.
STAGES = (
    {'giai_doan': 1, 'ngay': (1, 10), 'muc_tieu_c': 37.8, 'vung_c': (37.6, 38.0), 'do_am_khuyen_nghi': (60, 60)},
    {'giai_doan': 2, 'ngay': (11, 17), 'muc_tieu_c': 37.5, 'vung_c': (37.3, 37.7), 'do_am_khuyen_nghi': (55, 55)},
    {'giai_doan': 3, 'ngay': (18, 21), 'muc_tieu_c': 37.2, 'vung_c': (37.0, 37.4), 'do_am_khuyen_nghi': (65, 70)},
)
# Bảo vệ CỐ ĐỊNH, không đổi theo giai đoạn: đổi ngày không bao giờ nới bảo vệ.
NGAT_MEM_C, BAT_LAI_C, DUNG_CUNG_C = 38.3, 37.8, 38.8
MAC_DINH = Path(__file__).resolve().with_name('trang_thai_me_ap.json')


class LichError(ValueError):
    pass


def stage_for_day(ngay: int) -> dict:
    if isinstance(ngay, bool) or not isinstance(ngay, int) or not 1 <= ngay <= SO_NGAY:
        raise LichError(f'Ngày ấp phải là số nguyên 1–{SO_NGAY}.')
    return next(dict(s) for s in STAGES if s['ngay'][0] <= ngay <= s['ngay'][1])


def stage_by_id(giai_doan: int) -> dict:
    return next(dict(s) for s in STAGES if s['giai_doan'] == giai_doan)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec='seconds')


def _parse(text: str) -> float:
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise LichError('Thời điểm trong file lịch thiếu múi giờ.')
    return value.timestamp()


def validate(state: dict) -> dict:
    if not isinstance(state, dict) or state.get('phien_ban') != 1:
        raise LichError('File lịch sai định dạng.')
    spd = state.get('giay_moi_ngay')
    if isinstance(spd, bool) or not isinstance(spd, (int, float)) or not math.isfinite(spd) \
            or not GIAY_MOI_NGAY_TOI_THIEU <= spd <= GIAY_MOI_NGAY_THAT:
        raise LichError(f'giay_moi_ngay phải trong {GIAY_MOI_NGAY_TOI_THIEU}–{GIAY_MOI_NGAY_THAT}.')
    _parse(state['bat_dau_utc'])
    return state


def load(path: Path = MAC_DINH) -> dict:
    try:
        return validate(json.loads(Path(path).read_text(encoding='utf-8')))
    except FileNotFoundError as exc:
        raise LichError(f'Chưa có mẻ ấp ({Path(path).name}); chạy: python3 me_ap.py bat-dau') from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise LichError(f'Không đọc được file lịch: {exc}') from exc


def save(state: dict, path: Path = MAC_DINH) -> dict:
    validate(state)
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)  # Ghi nguyên khối: chương trình điều khiển không bao giờ đọc file dở.
    return state


def is_paused(state: dict) -> bool:
    return bool(state.get('tam_dung_utc'))


def _clock(state: dict, now: float) -> float:
    """Đồng hồ của lịch: đứng yên tại lúc tạm dừng (chỉ dùng cho mẻ demo rút gọn)."""
    return _parse(state['tam_dung_utc']) if is_paused(state) else now


def current(state: dict, now: float | None = None) -> dict:
    """Ngày/giai đoạn/mốc tại thời điểm now (giây epoch). Sau ngày 21 giữ giai đoạn 3 và báo het_lich."""
    now = time.time() if now is None else now
    spd = state['giay_moi_ngay']
    elapsed = _clock(state, now) - _parse(state['bat_dau_utc'])
    raw_day = int(max(0.0, elapsed) // spd) + 1
    ngay = min(raw_day, SO_NGAY)
    stage = stage_for_day(ngay)
    return {
        'ngay': ngay, 'giai_doan': stage['giai_doan'], 'muc_tieu_c': stage['muc_tieu_c'],
        'vung_c': list(stage['vung_c']), 'do_am_khuyen_nghi': list(stage['do_am_khuyen_nghi']),
        'het_lich': raw_day > SO_NGAY, 'giay_moi_ngay': spd, 'rut_gon': spd < GIAY_MOI_NGAY_THAT,
        'bat_dau_utc': state['bat_dau_utc'],
        'giay_den_ngay_sau': None if raw_day > SO_NGAY else round(spd - max(0.0, elapsed) % spd, 1),
        'cap_nhat_utc': state.get('cap_nhat_utc'), 'nguon': state.get('nguon'),
        'tam_dung': is_paused(state),
    }


def start_batch(path: Path = MAC_DINH, now: float | None = None, ngay: int = 1,
                giay_moi_ngay: float = GIAY_MOI_NGAY_THAT, nguon: str = 'dong_lenh', paused: bool | None = None) -> dict:
    """Tạo mẻ. Mẻ demo rút gọn mặc định TẠM DỪNG: lịch chỉ chạy khi ap_trung đang giữ nhiệt bằng RL,
    để thời gian làm ấm (~5 phút) không "ăn" mất nhiều ngày demo. Mẻ thời gian thật luôn chạy."""
    stage_for_day(ngay)
    now = time.time() if now is None else now
    paused = giay_moi_ngay < GIAY_MOI_NGAY_THAT if paused is None else paused
    state = {'phien_ban': 1, 'giay_moi_ngay': giay_moi_ngay,
             'bat_dau_utc': _iso(now - (ngay - 1) * giay_moi_ngay - 1),
             'cap_nhat_utc': _iso(now), 'nguon': nguon}
    if paused:
        state['tam_dung_utc'] = _iso(now)
    return save(state, path)


def set_day(ngay: int, path: Path = MAC_DINH, now: float | None = None, nguon: str = 'dong_lenh') -> dict:
    """Chỉnh ngày hiện tại thành `ngay`, giữ nguyên tốc độ lịch và trạng thái tạm dừng."""
    stage_for_day(ngay)
    state = load(path)
    now = time.time() if now is None else now
    # Lùi thêm 1 s để không rơi đúng biên ngày do làm tròn.
    state.update(bat_dau_utc=_iso(_clock(state, now) - (ngay - 1) * state['giay_moi_ngay'] - 1),
                 cap_nhat_utc=_iso(now), nguon=nguon)
    return save(state, path)


def pause(path: Path = MAC_DINH, now: float | None = None, nguon: str = 'ap_trung') -> dict:
    """Đứng lịch (chỉ mẻ demo). Gọi khi lượt kết thúc/dừng. Không làm gì nếu đã dừng hoặc là mẻ thật."""
    state = load(path)
    if is_paused(state) or state['giay_moi_ngay'] >= GIAY_MOI_NGAY_THAT:
        return state
    now = time.time() if now is None else now
    state.update(tam_dung_utc=_iso(now), cap_nhat_utc=_iso(now), nguon=nguon)
    return save(state, path)


def resume(path: Path = MAC_DINH, now: float | None = None, nguon: str = 'ap_trung') -> dict:
    """Chạy tiếp lịch từ đúng chỗ đã dừng (dời bat_dau thêm đúng thời gian đã dừng)."""
    state = load(path)
    if not is_paused(state):
        return state
    now = time.time() if now is None else now
    paused_for = max(0.0, now - _parse(state['tam_dung_utc']))
    state['bat_dau_utc'] = _iso(_parse(state['bat_dau_utc']) + paused_for)
    state.pop('tam_dung_utc')
    state.update(cap_nhat_utc=_iso(now), nguon=nguon)
    return save(state, path)


def describe(info: dict) -> str:
    lo, hi = info['vung_c']
    rh = info['do_am_khuyen_nghi']
    rh_text = f'{rh[0]}%' if rh[0] == rh[1] else f'{rh[0]}–{rh[1]}%'
    speed = '' if not info['rut_gon'] else f' (DEMO RÚT GỌN: 1 ngày = {info["giay_moi_ngay"]:g} s' + \
        (', lịch tạm dừng tới khi RL giữ nhiệt)' if info.get('tam_dung') else ')')
    tail = ' — ĐÃ HẾT 21 NGÀY, giữ mốc giai đoạn 3' if info['het_lich'] else ''
    return (f'Ngày {info["ngay"]}/{SO_NGAY} · Giai đoạn {info["giai_doan"]} · mốc {info["muc_tieu_c"]:.1f} °C '
            f'(vùng {lo:.1f}–{hi:.1f} °C) · ẩm độ khuyến nghị {rh_text}{speed}{tail}')


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', type=Path, default=MAC_DINH)
    sub = parser.add_subparsers(dest='lenh', required=True)
    sub.add_parser('xem')
    p = sub.add_parser('bat-dau')
    p.add_argument('--ngay', type=int, default=1)
    p.add_argument('--giay-moi-ngay', type=float, default=GIAY_MOI_NGAY_THAT,
                   help=f'Mặc định {GIAY_MOI_NGAY_THAT} (thật). Demo: ví dụ 120.')
    p = sub.add_parser('dat-ngay')
    p.add_argument('ngay', type=int)
    args = parser.parse_args(argv)
    try:
        if args.lenh == 'bat-dau':
            start_batch(args.file, ngay=args.ngay, giay_moi_ngay=args.giay_moi_ngay)
        elif args.lenh == 'dat-ngay':
            set_day(args.ngay, args.file)
        print(describe(current(load(args.file))))
    except LichError as exc:
        print(f'LỖI: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
