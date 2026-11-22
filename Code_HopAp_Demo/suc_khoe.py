#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sức khỏe thiết bị (quản lý thiết bị từ xa): bridge đọc mỗi 30 s rồi gửi lên hop_ap_01/suc_khoe.

Chỉ ĐỌC, không điều khiển gì. Mỗi số đọc lỗi thì để None, không làm hỏng chu kỳ của bridge.
    cpu_c            nhiệt CPU Pi (/sys/class/thermal/thermal_zone0/temp); > 80 °C Pi tự giảm xung
    nguon            cờ của `vcgencmd get_throttled`: sụt áp HIỆN TẠI / ĐÃ TỪNG từ lúc khởi động (adapter Pi yếu)
    wifi_dbm         cường độ Wi-Fi (/proc/net/wireless); ≥ −60 mạnh, ≤ −80 yếu
    ram_dung_pct     % RAM đã dùng (/proc/meminfo); the_nho_trong_gb / the_nho_dung_pct: thẻ nhớ
    uptime_s         thời gian Pi chạy liên tục; tai_1phut: tải CPU trung bình 1 phút
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess


def _read(path):
    try:
        return Path(path).read_text(encoding='utf-8')
    except OSError:
        return None


def cpu_temperature(sys_root='/sys'):
    text = _read(Path(sys_root) / 'class' / 'thermal' / 'thermal_zone0' / 'temp')
    try:
        return round(int(text.strip()) / 1000, 1)
    except (AttributeError, ValueError):
        return None


def uptime_seconds(proc_root='/proc'):
    text = _read(Path(proc_root) / 'uptime')
    try:
        return int(float(text.split()[0]))
    except (AttributeError, ValueError, IndexError):
        return None


def memory_used_pct(proc_root='/proc'):
    text = _read(Path(proc_root) / 'meminfo')
    if not text:
        return None
    values = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ('MemTotal:', 'MemAvailable:'):
            values[parts[0]] = int(parts[1])
    total, free = values.get('MemTotal:'), values.get('MemAvailable:')
    if not total or free is None:
        return None
    return round(100 * (1 - free / total), 1)


def wifi_dbm(proc_root='/proc'):
    """Mức tín hiệu (dBm) của card Wi-Fi đầu tiên trong /proc/net/wireless."""
    text = _read(Path(proc_root) / 'net' / 'wireless')
    if not text:
        return None
    for line in text.splitlines()[2:]:
        if ':' not in line:
            continue
        fields = line.split(':', 1)[1].split()
        try:
            level = float(fields[2].rstrip('.'))
        except (IndexError, ValueError):
            continue
        return int(level - 256) if level > 0 else int(level)  # vài driver báo dạng không dấu
    return None


THROTTLE_BITS = {'yeu_hien_tai': 0, 'giam_xung_hien_tai': 2, 'tung_yeu': 16, 'tung_giam_xung': 18}


def power_flags(run=subprocess.run):
    """Đọc `vcgencmd get_throttled`. Không có lệnh (không phải Pi) thì None."""
    try:
        result = run(['vcgencmd', 'get_throttled'], capture_output=True, text=True, timeout=3)
        code = int(result.stdout.strip().split('=')[1], 16)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None
    return dict({k: bool(code >> bit & 1) for k, bit in THROTTLE_BITS.items()}, ma=hex(code))


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))  # UDP: không gửi gói nào, chỉ để hệ điều hành chọn card mạng
            return s.getsockname()[0]
    except OSError:
        return None


def collect(base, sys_root='/sys', proc_root='/proc', run=subprocess.run):
    data = {'cpu_c': cpu_temperature(sys_root), 'uptime_s': uptime_seconds(proc_root),
            'ram_dung_pct': memory_used_pct(proc_root), 'wifi_dbm': wifi_dbm(proc_root),
            'nguon': power_flags(run), 'ip': local_ip(), 'may': socket.gethostname()}
    try:
        disk = shutil.disk_usage(base)
        data['the_nho_trong_gb'] = round(disk.free / 1e9, 1)
        data['the_nho_dung_pct'] = round(100 * disk.used / disk.total, 1)
    except OSError:
        data['the_nho_trong_gb'] = data['the_nho_dung_pct'] = None
    try:
        data['tai_1phut'] = round(os.getloadavg()[0], 2)
    except (AttributeError, OSError):  # Windows không có getloadavg
        data['tai_1phut'] = None
    return data
