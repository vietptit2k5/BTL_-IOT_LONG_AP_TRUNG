#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chẩn đoán DHT11 (chỉ ĐỌC, không điều khiển bóng/quạt). Chạy trên Pi:

    .venv/bin/python kiem_tra_dht11.py              # 10 lần đọc, mỗi 3 s
    .venv/bin/python kiem_tra_dht11.py --lan 20

In từng lần đọc, phân loại lỗi kèm nguyên nhân hay gặp và cách sửa, rồi kết luận. Nếu có DS18B20 thì so nhiệt
độ hai cảm biến (DHT11 sai số nhiệt khoảng ±2 °C theo hãng) để phát hiện cảm biến đặt sai chỗ.
Dây đang lắp (README.md): VCC → hàng 3,3 V breadboard (lỗ d10) · GND → hàng GND (lỗ d18) · DATA → chân 11 (GPIO17).
"""
from __future__ import annotations

import argparse
from collections import Counter
import glob
import math
import sys
import time

CAUSES = {
    'not_found': ('Không có tín hiệu trả về từ cảm biến',
                  ['DATA chưa cắm đúng GPIO17 / chân vật lý 11 (đếm lại chân, đừng theo màu dây)',
                   'VCC/GND nhầm hàng: VCC ở hàng 3,3 V (d10), GND ở hàng GND (d18); KHÔNG lấy từ chân 2/4 (5 V); '
                   'đo bằng đồng hồ khoảng 3,3 V giữa VCC và GND của module',
                   'Chưa cấp 3,3 V hoặc GND, hoặc dây Dupont lỏng: đo 3,3 V giữa VCC và GND bằng đồng hồ',
                   'Cảm biến rời 4 chân cần điện trở 10 kΩ giữa DATA và 3,3 V (module 3 chân thường có sẵn)',
                   'Thứ tự chân trên module khác tài liệu: đọc chữ in trên bo (+, OUT/S, −)',
                   'Cảm biến hỏng: thử một con khác']),
    'checksum': ('Có tín hiệu nhưng dữ liệu sai (nhiễu)',
                 ['Dây quá dài hoặc đi sát dây 12 V của bóng/quạt: rút ngắn, tách xa',
                  'Mối nối lỏng: hàn hoặc cắm lại chắc',
                  'Thiếu/yếu điện trở kéo lên: thêm 10 kΩ DATA–3,3 V nếu là cảm biến rời']),
    'timing': ('Đọc lỡ nhịp (DHT11 trên Pi hay bị, thường tự hết ở lần sau)',
               ['Nếu chỉ thỉnh thoảng: bình thường, chương trình đã tự đọc lại mỗi 3 s',
                'Nếu gần như lần nào cũng bị: giảm tải CPU (đóng chương trình khác), kiểm tra dây như mục "nhiễu"']),
    'busy': ('GPIO17 đang bị chương trình khác giữ',
             ['Đang chạy song song do_nhiet_hop/ap_trung với --dht11: dừng chương trình đó rồi thử lại',
              'Một tiến trình DHT cũ bị treo: khởi động lại Pi (sudo reboot)']),
    'library': ('Thiếu thư viện hoặc chạy sai Python',
                ['Chạy bằng .venv/bin/python (không phải python3 hệ thống)',
                 'Cài: python3 -m venv --system-site-packages .venv && .venv/bin/python -m pip install adafruit-circuitpython-dht',
                 'Nếu báo thiếu libgpiod: sudo apt install -y libgpiod2']),
    'range': ('Giá trị ngoài miền hợp lệ', ['Cảm biến lỗi hoặc đọc nhầm: thử lại, thay cảm biến nếu lặp lại']),
    'other': ('Lỗi khác', ['Ghi lại nguyên văn thông báo lỗi để tra cứu']),
}


def classify_error(message: str) -> str:
    m = message.lower()
    if 'not found' in m or 'check wiring' in m:
        return 'not_found'
    if 'checksum' in m:
        return 'checksum'
    if 'full buffer' in m or 'timed out' in m or 'timeout' in m:
        return 'timing'
    if 'busy' in m or 'unable to set line' in m or 'lock' in m or 'in use' in m:
        return 'busy'
    if 'no module' in m or 'libgpiod' in m or 'import' in m:
        return 'library'
    return 'other'


def read_ds18b20(root='/sys/bus/w1/devices'):
    for path in glob.glob(f'{root}/28-*/w1_slave'):
        try:
            lines = open(path, encoding='ascii').read().splitlines()
            if lines and lines[0].strip().endswith('YES') and 't=' in lines[-1]:
                return int(lines[-1].split('t=')[1]) / 1000
        except (OSError, ValueError):
            continue
    return None


def summarize(results, ds_temp=None):
    """results: [(rh, temp, error_kind_or_None, message)]. Trả (kết luận, dòng gợi ý)."""
    ok = [r for r in results if r[2] is None]
    kinds = Counter(r[2] for r in results if r[2] is not None)
    lines = []
    ratio = len(ok) / len(results) if results else 0
    if ratio >= 0.5:
        verdict = 'DAT'
        rh = [r[0] for r in ok]
        lines.append(f'Đọc được {len(ok)}/{len(results)} lần; RH {min(rh):.0f}–{max(rh):.0f} %.')
        if ds_temp is not None:
            t = sum(r[1] for r in ok if r[1] is not None) / max(1, sum(r[1] is not None for r in ok))
            diff = t - ds_temp
            lines.append(f'Nhiệt DHT11 {t:.1f} °C so với DS18B20 {ds_temp:.2f} °C (lệch {diff:+.1f} °C).')
            if abs(diff) > 3:
                lines.append('Lệch > 3 °C: DHT11 có thể đặt sát bóng/thành nóng hoặc ở ngoài hộp; đặt gần đầu dò DS18B20.')
    else:
        verdict = 'KHONG_DAT'
        lines.append(f'Chỉ đọc được {len(ok)}/{len(results)} lần.')
    for kind, count in kinds.most_common():
        title, fixes = CAUSES[kind]
        lines.append(f'- {title}: {count} lần')
        if verdict == 'KHONG_DAT' or kind != 'timing':
            lines.extend(f'    • {fix}' for fix in fixes)
    return verdict, lines


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--lan', type=int, default=10, help='Số lần đọc (mặc định 10, mỗi 3 s)')
    p.add_argument('--cach-doc', choices=('auto', 'kernel', 'thu_vien'), default='auto')
    args = p.parse_args(argv)
    from dht_reader import OVERLAY_LINE, find_kernel_dht11, open_dht11
    kernel = find_kernel_dht11()
    print('Driver kernel dht11:', f'ĐÃ BẬT ({kernel})' if kernel else f'chưa bật (dòng cần thêm: {OVERLAY_LINE})')
    try:
        device = open_dht11(args.cach_doc)
    except ImportError as exc:
        print(f'KHÔNG TẢI ĐƯỢC THƯ VIỆN: {exc}')
        for fix in CAUSES['library'][1]:
            print(f'  • {fix}')
        print(f'  • Hoặc bật driver kernel: thêm "{OVERLAY_LINE}" vào /boot/firmware/config.txt rồi sudo reboot')
        print(f'Python đang dùng: {sys.executable}')
        return 2
    except RuntimeError as exc:
        print(f'LỖI: {exc}')
        return 2
    print(f'Đọc DHT11 ở GPIO17 (chân 11) bằng {"driver kernel" if device.kind == "kernel" else "thư viện Adafruit"}. '
          'Ctrl+C để dừng.\n')
    results = []
    try:
        for i in range(1, args.lan + 1):
            try:
                rh, temp = device.read()
                if rh is None or not math.isfinite(rh) or not 0 <= rh <= 100:
                    raise RuntimeError(f'Giá trị RH không hợp lệ: {rh!r}')
                results.append((float(rh), None if temp is None else float(temp), None, ''))
                print(f'[{i:2d}] OK   RH = {rh:.0f} %   T = {temp} °C')
            except RuntimeError as exc:
                kind = 'range' if 'không hợp lệ' in str(exc) else classify_error(str(exc))
                results.append((None, None, kind, str(exc)))
                print(f'[{i:2d}] LỖI  {exc}   → {CAUSES[kind][0]}')
            time.sleep(3)
    except KeyboardInterrupt:
        print('\nĐã dừng.')
    except Exception as exc:  # noqa: BLE001 - lỗi khởi tạo chân GPIO
        kind = classify_error(str(exc))
        results.append((None, None, kind, str(exc)))
        print(f'LỖI KHỞI TẠO: {exc}   → {CAUSES[kind][0]}')
    finally:
        device.exit()
    verdict, lines = summarize(results, read_ds18b20())
    if verdict != 'DAT' and device.kind == 'thu_vien':
        lines.append(f'Gợi ý mạnh: thư viện Adafruit hay đọc hỏng trên Raspberry Pi OS mới dù dây đúng. Bật driver '
                     f'kernel: echo "{OVERLAY_LINE}" | sudo tee -a /boot/firmware/config.txt && sudo reboot, '
                     'rồi chạy lại chương trình này.')
    print(f'\nKẾT LUẬN: {"ĐẠT" if verdict == "DAT" else "CHƯA ĐẠT"}')
    print('\n'.join(lines))
    return 0 if verdict == 'DAT' else 1


if __name__ == '__main__':
    raise SystemExit(main())
