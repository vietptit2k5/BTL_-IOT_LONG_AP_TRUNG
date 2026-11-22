#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thử nhiễu: ép bóng/quạt trong 1–2 phút rồi đo bộ điều khiển (RL hoặc thermostat) kéo nhiệt về vùng nhanh cỡ nào.

Luồng (bridge điều phối, ap_trung thực hiện qua lenh_tay.json như chỉnh tay):
    1. Chỉ bắt đầu khi lượt ap_trung đang GIỮ NHIỆT và nhiệt đang TRONG VÙNG.
    2. Pha nhiễu: "lanh" = bóng 0 %, quạt 100 %; "nong" = bóng 100 %, quạt 75 %. Bảo vệ 38,3 / 38,8 °C vẫn thắng.
    3. Hết nhiễu, bộ điều khiển lấy lại quyền. Đo từ lúc hết nhiễu:
         ve_vung_s  : tới lần đầu nhiệt vào lại vùng mục tiêu;
         on_dinh_s  : tới lúc bắt đầu một đoạn ở yên trong vùng liên tục ON_DINH_S giây;
         lech_max_c : độ lệch lớn nhất khỏi mốc trong cả phép thử.
    4. Quá HET_GIO_S giây sau nhiễu mà chưa ổn định: CHUA_VE_VUNG. Lượt kết thúc giữa chừng: HUY.

Mọi hàm làm việc trên một dict thường để bridge lưu bền và gửi thẳng lên Firebase.
"""
from __future__ import annotations

KIEU = {'lanh': (0, 100), 'nong': (100, 75)}
KIEU_TEN = {'lanh': 'làm lạnh (bóng 0 %, quạt 100 %)', 'nong': 'làm nóng (bóng 100 %, quạt 75 %)'}
THOI_HAN = (60, 120)
ON_DINH_S = 60
HET_GIO_S = 600
ACTIVE = ('DANG_NHIEU', 'DANG_PHUC_HOI')


def new_test(kieu, seconds, now, by, target, band, controller, session):
    return {
        'id': str(int(now * 1000)), 'kieu': kieu, 'thoi_han_s': seconds, 'by': str(by)[:100],
        'bat_dau_ts': int(now * 1000), 'het_han_ts': int((now + seconds) * 1000),
        'muc_tieu_c': target, 'vung_c': list(band), 'bo_dieu_khien': controller, 'phien': session,
        'trang_thai': 'DANG_NHIEU', 'ra_vung': False, 'bao_ve': False,
        'lech_max_c': 0.0, 'nhiet_min_c': None, 'nhiet_max_c': None, 'nhiet_c': None,
        've_vung_s': None, 'on_dinh_s': None, 'last_t': None, 'chuoi_tu': None, 'ly_do': None,
    }


def feed(test, t, temp, in_band, cls):
    """Một số đo (t = giờ thật, giây). Trả True nếu phép thử còn đang chạy hoặc vừa xong ở điểm này."""
    if test['trang_thai'] not in ACTIVE:
        return False
    if t < test['bat_dau_ts'] / 1000 or (test['last_t'] is not None and t <= test['last_t']):
        return False  # trước phép thử, hoặc điểm đã xử lý (bridge gửi lại sau khi mất mạng)
    test['last_t'] = t
    test['nhiet_c'] = round(temp, 3)
    test['nhiet_min_c'] = round(temp if test['nhiet_min_c'] is None else min(test['nhiet_min_c'], temp), 3)
    test['nhiet_max_c'] = round(temp if test['nhiet_max_c'] is None else max(test['nhiet_max_c'], temp), 3)
    test['lech_max_c'] = round(max(test['lech_max_c'], abs(temp - test['muc_tieu_c'])), 3)
    if cls == 'bao_ve':
        test['bao_ve'] = True
    end = test['het_han_ts'] / 1000
    if t <= end:
        test['ra_vung'] = test['ra_vung'] or not in_band
        return True
    test['trang_thai'] = 'DANG_PHUC_HOI'
    if in_band:
        if test['ve_vung_s'] is None:
            test['ve_vung_s'] = round(t - end, 1)
        if test['chuoi_tu'] is None:
            test['chuoi_tu'] = t
        if t - test['chuoi_tu'] >= ON_DINH_S:
            test['on_dinh_s'] = round(test['chuoi_tu'] - end, 1)
            test['trang_thai'] = 'XONG'
    else:
        test['chuoi_tu'] = None
        test['ra_vung'] = True
        if t - end > HET_GIO_S:
            test['trang_thai'] = 'CHUA_VE_VUNG'
    return True


def cancel(test, reason):
    if test['trang_thai'] in ACTIVE:
        test['trang_thai'], test['ly_do'] = 'HUY', str(reason)[:200]
    return test


def fmt_s(seconds):
    if seconds is None:
        return '--'
    s = int(round(seconds))
    return f'{s // 60}:{s % 60:02d}'


def summary_text(test):
    head = f'Thử nhiễu {KIEU_TEN.get(test["kieu"], test["kieu"])} {test["thoi_han_s"] // 60} phút ({test["bo_dieu_khien"]})'
    lech = f'lệch tối đa {test["lech_max_c"]:.2f} °C'.replace('.', ',')
    if test['trang_thai'] == 'XONG':
        if not test['ra_vung']:
            return f'{head}: nhiệt KHÔNG ra khỏi vùng; {lech}.'
        return f'{head}: về vùng sau {fmt_s(test["ve_vung_s"])}, ổn định sau {fmt_s(test["on_dinh_s"])}; {lech}.'
    if test['trang_thai'] == 'CHUA_VE_VUNG':
        return f'{head}: chưa ổn định lại sau {HET_GIO_S // 60} phút; {lech}.'
    if test['trang_thai'] == 'HUY':
        return f'{head}: đã hủy ({test.get("ly_do") or "?"}).'
    return f'{head}: đang chạy.'
