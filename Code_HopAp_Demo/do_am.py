#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đọc và hiển thị độ ẩm DHT11 (GPIO17 / chân 11). Chỉ ĐỌC, không điều khiển bóng/quạt.

    .venv/bin/python do_am.py                 # Terminal, mỗi 3 s
    .venv/bin/python do_am.py --oled          # thêm màn OLED (khi KHÔNG chạy ap_trung/do_nhiet_hop cùng lúc)
    .venv/bin/python do_am.py --ds18b20       # so thêm nhiệt DS18B20 (cũng chỉ khi không có lượt điều khiển)
    bash cai_dich_vu_do_am.sh                 # chạy nền, tự khởi động cùng Pi

Chương trình này là nơi DUY NHẤT mở GPIO17. Mỗi lần đọc nó ghi số mới nhất vào do_am_moi_nhat.json (ghi nguyên
khối). Chương trình điều khiển đọc file đó bằng `ap_trung.py --do-am` (không mở GPIO17, nên không tranh chân), còn
cloud_bridge.py đưa số đo lên app. Độ ẩm chỉ để GIÁM SÁT: không vào state/action/reward của Q-table.
Giá trị hiển thị là trung vị 3 lần đọc tốt gần nhất (DHT11 hay có lần đọc lỗi/nhảy).
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

from dht_reader import OVERLAY_LINE, open_dht11
from kiem_tra_dht11 import CAUSES, classify_error, read_ds18b20

MAC_DINH = Path(__file__).resolve().with_name('do_am_moi_nhat.json')
CHU_KY_S = 3.0
SO_MAU_TRUNG_VI = 3
HET_HAN_S = 30.0  # Số đo cũ hơn thì coi như mất (dùng chung cho bridge/ap_trung).


def median(values):
    s = sorted(values)
    n = len(s)
    return None if n == 0 else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


class DoAm:
    """Gom các lần đọc, lọc trung vị, tạo bản ghi cho file JSON. Tách khỏi phần cứng để kiểm thử."""

    def __init__(self):
        self.rh = deque(maxlen=SO_MAU_TRUNG_VI)
        self.temp = deque(maxlen=SO_MAU_TRUNG_VI)
        self.total = self.ok = 0
        self.last_ok_ts = None
        self.last_error = ''

    def add(self, rh, temp, error, now):
        self.total += 1
        if error is None and rh is not None and math.isfinite(rh) and 0 <= rh <= 100:
            self.ok += 1
            self.rh.append(float(rh))
            if temp is not None and math.isfinite(temp):
                self.temp.append(float(temp))
            self.last_ok_ts = now
            self.last_error = ''
        else:
            self.last_error = error or f'Giá trị không hợp lệ: {rh!r}'

    def record(self, now, ds18b20=None):
        fresh = self.last_ok_ts is not None and now - self.last_ok_ts <= HET_HAN_S
        return {
            'phien_ban': 1, 'ts': int(now * 1000),
            'do_am_pct': round(median(self.rh), 1) if fresh and self.rh else None,
            'nhiet_dht_c': round(median(self.temp), 1) if fresh and self.temp else None,
            'nhiet_ds18b20_c': None if ds18b20 is None else round(ds18b20, 3),
            'ts_doc_ok_cuoi': None if self.last_ok_ts is None else int(self.last_ok_ts * 1000),
            'lan_doc': self.total, 'lan_doc_ok': self.ok,
            'ty_le_ok_pct': round(100 * self.ok / self.total, 1) if self.total else None,
            'loi_cuoi': self.last_error[:160],
        }


def write_atomic(path: Path, record: dict):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)


def read_latest(path: Path = MAC_DINH, now: float | None = None):
    """Cho chương trình khác: (do_am_pct | None, tuổi_giây | None, lỗi). Không bao giờ ném lỗi."""
    now = time.time() if now is None else now
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None, None, 'Chưa chạy do_am.py'
    except (OSError, ValueError):
        return None, None, 'File độ ẩm đang ghi/hỏng'
    ok_ts = data.get('ts_doc_ok_cuoi')
    age = None if not isinstance(ok_ts, (int, float)) else max(0.0, now - ok_ts / 1000)
    rh = data.get('do_am_pct')
    if not isinstance(data.get('ts'), (int, float)) or now - data['ts'] / 1000 > HET_HAN_S:
        return None, age, 'do_am.py không còn cập nhật'
    if rh is None or age is None or age > HET_HAN_S:
        return None, age, data.get('loi_cuoi') or 'DHT11 chưa đọc được'
    return float(rh), age, ''


def format_line(record, error_kind=None):
    rh = record['do_am_pct']
    t_dht = record['nhiet_dht_c']
    t_ds = record['nhiet_ds18b20_c']
    parts = [datetime.now().strftime('%H:%M:%S'),
             f'RH = {rh:.0f} %' if rh is not None else 'RH = -- %',
             f'T(DHT11) = {t_dht:.0f} °C' if t_dht is not None else 'T(DHT11) = --']
    if t_ds is not None:
        parts.append(f'T(DS18B20) = {t_ds:.2f} °C')
    if record['ty_le_ok_pct'] is not None:
        parts.append(f'đọc tốt {record["lan_doc_ok"]}/{record["lan_doc"]}')
    line = ' | '.join(parts)
    if error_kind is not None:
        line += f'\n         lỗi lần này: {record["loi_cuoi"]} → {CAUSES[error_kind][0]}'
    return line


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--file', type=Path, default=MAC_DINH)
    p.add_argument('--chu-ky', type=float, default=CHU_KY_S, help='Giây giữa hai lần đọc (≥ 2; DHT11 chậm)')
    p.add_argument('--oled', action='store_true', help='Hiển thị lên OLED (đừng bật khi chương trình điều khiển đang dùng OLED)')
    p.add_argument('--cach-doc', choices=('auto', 'kernel', 'thu_vien'), default='auto',
                   help='auto: driver kernel nếu đã bật dtoverlay=dht11, không thì thư viện Adafruit')
    p.add_argument('--ds18b20', action='store_true',
                   help='Đọc thêm DS18B20 để so sánh (chỉ khi KHÔNG có chương trình điều khiển đang đọc cảm biến này)')
    args = p.parse_args(argv)
    if args.chu_ky < 2:
        p.error('--chu-ky phải ≥ 2 giây.')
    try:
        device = open_dht11(args.cach_doc)
    except ImportError as exc:
        print(f'KHÔNG TẢI ĐƯỢC THƯ VIỆN DHT: {exc}\n  • ' + '\n  • '.join(CAUSES['library'][1])
              + f'\n  • Hoặc dùng driver kernel: thêm "{OVERLAY_LINE}" vào /boot/firmware/config.txt rồi sudo reboot')
        return 2
    except RuntimeError as exc:
        print(f'LỖI: {exc}')
        return 2

    display = None
    if args.oled:
        from oled_hop_ap import OLEDDisplay, OLEDFrame
        display = OLEDDisplay(enabled=True)
        display.start()

    stop = {'flag': False}
    for number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(number, lambda *_: stop.update(flag=True))

    state = DoAm()
    print(f'Đọc DHT11 ở GPIO17 bằng {"driver kernel" if device.kind == "kernel" else "thư viện Adafruit"} '
          f'mỗi {args.chu_ky:g} s, ghi {args.file.name}. Ctrl+C để dừng.', flush=True)
    try:
        while not stop['flag']:
            started = time.time()
            kind = None
            try:
                state.add(*device.read(), None, started)
            except RuntimeError as exc:
                kind = classify_error(str(exc))
                state.add(None, None, str(exc), started)
            record = state.record(time.time(), read_ds18b20() if args.ds18b20 else None)
            write_atomic(args.file, record)
            print(format_line(record, kind), flush=True)
            if display is not None:
                temp = record['nhiet_ds18b20_c'] if record['nhiet_ds18b20_c'] is not None else record['nhiet_dht_c']
                now_m = time.monotonic()
                display.update(OLEDFrame(temp, now_m if temp is not None else None, None, None, 'do_am', 0,
                                         'RH OK' if record['do_am_pct'] is not None else 'DHT ERR', now_m,
                                         record['do_am_pct'], now_m, True))
            while not stop['flag'] and time.time() - started < args.chu_ky:
                time.sleep(0.2)
    except Exception as exc:  # noqa: BLE001 - lỗi mở chân GPIO17
        kind = classify_error(str(exc))
        print(f'LỖI MỞ DHT11: {exc} → {CAUSES[kind][0]}\n  • ' + '\n  • '.join(CAUSES[kind][1]), flush=True)
        state.add(None, None, str(exc), time.time())
        write_atomic(args.file, state.record(time.time(), None))
        return 1
    finally:
        device.exit()
        if display is not None:
            display.close()
    print('Đã dừng đọc độ ẩm.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
