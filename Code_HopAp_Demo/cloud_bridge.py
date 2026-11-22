#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cầu nối đám mây (IoT Level-2) cho hộp ấp: đọc CSV cục bộ, đẩy lên Firebase Realtime Database.

Tiến trình RIÊNG, không import và không thay đổi vòng điều khiển. Pi vẫn tự đo, tự quyết định
(Q-table) và tự bảo vệ; đám mây chỉ lưu trữ, hiển thị, cảnh báo và nhận lệnh DỪNG.

    python3 cloud_bridge.py kiem-tra                      # thử đăng nhập + quyền ghi
    python3 cloud_bridge.py chay                          # theo dõi CSV mới nhất, chạy song song lượt đo
    python3 cloud_bridge.py phat-lai ../Du_lieu_giu_nhiet/20261120_pilot_01/du_lieu.csv --toc-do 10
    python3 cloud_bridge.py tai-len ../Du_lieu_giu_nhiet/*/du_lieu.csv   # đưa lượt cũ lên lịch sử
    Thêm --ghi-file THU_MUC để ghi JSON cục bộ thay vì Firebase (thử khi chưa có mạng/tài khoản).

Lệnh DỪNG từ app chỉ gửi SIGTERM tới đúng tiến trình đang ghi CSV; do_nhiet_hop.py bắt SIGTERM,
tắt bóng rồi tắt quạt. Không có lệnh bật bóng hay đổi nhiệt độ đặt từ đám mây.
"""

from __future__ import annotations

import argparse
import copy
import csv
from collections import deque
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import sys
import threading
import time

import me_ap
import suc_khoe
import thu_nhieu as tn

VERSION = '1.7'
DEVICE = 'hop_ap_01'
CSV_FIELDS = (
    'timestamp_utc', 'elapsed_s', 'event', 'phase', 'sensor_id',
    'temperature_c', 'temperature_age_s', 'gpio_control', 'lamp_requested_pct',
    'fan_requested_pct', 'lamp_command_pct', 'fan_command_pct', 'fan_pwm_hz',
    'cutoff_c', 'trend_c_per_min', 'note',
    'humidity_pct', 'humidity_age_s', 'humidity_error',
)  # Phải trùng do_nhiet_hop.CSV_FIELDS (có test kiểm tra).
LEGACY_FIELDS = CSV_FIELDS[:16]  # Định dạng trước khi thêm DHT11 (các lượt 17/11).
VALID_HEADERS = (CSV_FIELDS, LEGACY_FIELDS)

TARGET_C, LOWER_C, UPPER_C = 37.5, 37.3, 37.7
SAMPLE_EVERY_S = 5            # Một mẫu lên đám mây mỗi 5 s thời gian đo (bằng chu kỳ điều khiển).
OUT_OF_BAND_S = 60            # Ngoài vùng liên tục bao lâu thì cảnh báo.
SETTLED_S = 60                # Trở lại vùng bao lâu thì báo "đã ổn định".
DROP_WINDOW_S = 30
DROP_ALERT_C = 0.5            # Tụt >= 0,5 °C trong 30 s khi bóng vẫn đang sưởi -> nghi mở nắp.
COOLDOWN_S = 300              # Mỗi loại cảnh báo tối đa 1 lần / 5 phút (theo thời gian đo).
SENSOR_STALE_S = 3.0
CSV_SILENT_S = 20             # CSV không ghi thêm quá lâu khi chưa END -> chương trình Pi có thể đã dừng.
STOP_MAX_AGE_S = 600          # Bỏ qua lệnh dừng cũ hơn 10 phút (ví dụ khi bridge khởi động lại).
HOLD = ('giu_nhiet', 'phuc_hoi', 'bao_ve')

PHASE_LABELS = {
    'cho': 'Chờ cảm biến', 'lam_am': 'Làm ấm', 'giu_nhiet': 'Giữ nhiệt', 'phuc_hoi': 'Phục hồi nhiệt',
    'bao_ve': 'Bảo vệ quá nhiệt', 'quat_cuoi': 'Quạt làm nguội cuối', 'tay': 'Chỉnh tay', 'khac': 'Khác',
}
CONTROLLER_LABELS = {'doi-chung': 'Thermostat', 'thu-rl': 'Q-learning v1', 'co-dinh': 'Mức cố định',
                     'ap-trung': 'Q-learning 3 giai đoạn', 'ap-trung-thermostat': 'Thermostat 3 giai đoạn'}
ALERT_LEVEL = {
    'NGOAI_VUNG': 'canh_bao', 'ON_DINH': 'thong_tin', 'NGHI_MO_NAP': 'canh_bao', 'BAO_VE': 'canh_bao',
    'LOI_CAM_BIEN': 'nguy_hiem', 'LOI': 'nguy_hiem', 'KET_THUC': 'thong_tin', 'PI_KHONG_GHI': 'nguy_hiem',
    'DUNG_TU_XA': 'canh_bao',
}
ALERT_LEVEL.update(TIEP_TUC_ME='thong_tin', TAM_DUNG_ME='nguy_hiem', HET_ME='thong_tin')
ALERT_LEVEL.update(CHUYEN_GIAI_DOAN='thong_tin', DOI_NGAY='thong_tin', TAO_ME='thong_tin', KET_THUC_ME='thong_tin',
                   BAT_DAU_LUOT='canh_bao', DUNG_BAT_THUONG='nguy_hiem', CHINH_TAY='canh_bao', TRA_VE_RL='thong_tin',
                   THU_NHIEU='thong_tin', KET_QUA_THU_NHIEU='thong_tin')
NO_COOLDOWN = {'ON_DINH', 'KET_THUC', 'DUNG_TU_XA', 'CHUYEN_GIAI_DOAN', 'DOI_NGAY', 'TAO_ME', 'KET_THUC_ME',
               'BAT_DAU_LUOT', 'DUNG_BAT_THUONG', 'CHINH_TAY', 'TRA_VE_RL', 'THU_NHIEU', 'KET_QUA_THU_NHIEU',
               'TIEP_TUC_ME', 'TAM_DUNG_ME', 'HET_ME'}
MAX_SEGMENT_MINUTES = 1440    # Một phiên của mẻ ≤ 1 ngày (ap_trung MAX_MINUTES_ME).
ME_RETRY_WINDOW_S = 600       # Phiên chết trong vòng 10 phút sau khi chạy = một lần lỗi liên tiếp.
ME_MAX_FAILS = 3              # Lỗi liên tiếp 3 lần thì tạm dừng mẻ (tránh bật/tắt liên tục khi cảm biến hỏng).
ME_LAUNCH_GAP_S = 30          # Chờ tối thiểu giữa hai lần khởi động phiên.
HEALTH_EVERY_S = 30          # Gửi sức khỏe thiết bị mỗi 30 s.
NAO_FRESH_S = 30              # nao_rl.json cũ hơn thì không gửi (lượt đã dừng).
MANUAL_LAMP = (0, 25, 50, 75, 100)
MANUAL_FAN = (75, 100)
MANUAL_SECONDS = (60, 120, 300)
STAGE_RE = re.compile(r'^ap_ngay(\d{1,2})_gd([123])')


def log(message):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {message}', flush=True)


def now_ms():
    return int(time.time() * 1000)


def classify(phase):
    phase = phase or ''
    if phase == 'cho_cam_bien':
        return 'cho'
    if phase.endswith('_tay'):
        return 'tay'  # Chỉnh tay từ app: không tính vào chỉ số của RL/thermostat (không thuộc HOLD).
    if 'bao_ve' in phase:
        return 'bao_ve'
    if 'phuc_hoi' in phase:
        return 'phuc_hoi'
    if phase.startswith('lam_am'):
        return 'lam_am'
    if phase.startswith(('kiem_tra', 'giu_co_dinh', 'ap_ngay')):
        return 'giu_nhiet'
    if phase == 'giu_quat_cuoi':
        return 'quat_cuoi'
    return 'khac'


def stage_of(phase):
    """Ngày/giai đoạn/mốc từ tên pha của ap_trung.py (ví dụ ap_ngay12_gd2); None nếu không phải lượt 3 giai đoạn."""
    match = STAGE_RE.match(phase or '')
    if not match:
        return None
    try:
        stage = me_ap.stage_for_day(int(match[1]))
    except me_ap.LichError:
        return None
    return {'ngay': int(match[1]), 'giai_doan': stage['giai_doan'], 'muc_tieu_c': stage['muc_tieu_c'],
            'vung_c': list(stage['vung_c'])}


def num(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def parse_ts(text):
    try:
        return datetime.fromisoformat(text).timestamp()
    except (TypeError, ValueError):
        return None


def safe_key(text):
    return re.sub(r'[.#$\[\]/\s]+', '_', str(text)).strip('_')[:120] or 'khong_ten'


# --------------------------------------------------------------------------- lưu trữ đám mây

class CloudError(RuntimeError):
    pass


class FirebaseStore:
    """REST API của Realtime Database, đăng nhập bằng Firebase Auth (email/mật khẩu của Pi)."""

    def __init__(self, config, session=None, timeout=8):
        import requests  # Chỉ cần khi dùng Firebase thật.
        self.requests = requests
        self.http = session or requests.Session()
        self.config = config
        self.base = config['databaseURL'].rstrip('/')
        self.timeout = timeout
        self.token = None
        self.refresh_token = None
        self.expires_at = 0.0

    def _auth_post(self, url, payload):
        try:
            response = self.http.post(url, json=payload, timeout=self.timeout)
        except self.requests.RequestException as exc:
            raise CloudError(f'Không kết nối được dịch vụ đăng nhập: {type(exc).__name__}') from exc
        if not response.ok:
            try:
                reason = response.json().get('error', {}).get('message', '')
            except ValueError:
                reason = response.text[:80]
            raise CloudError(f'Đăng nhập thất bại ({response.status_code}): {reason}')
        return response.json()

    def login(self):
        key = self.config['apiKey']
        if self.refresh_token:
            try:
                data = self._auth_post(f'https://securetoken.googleapis.com/v1/token?key={key}',
                                       {'grant_type': 'refresh_token', 'refresh_token': self.refresh_token})
                self.token, self.refresh_token = data['id_token'], data['refresh_token']
                self.expires_at = time.time() + int(data.get('expires_in', 3600))
                return
            except CloudError:
                self.refresh_token = None
        data = self._auth_post(
            f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={key}',
            {'email': self.config['pi_email'], 'password': self.config['pi_password'], 'returnSecureToken': True})
        self.token, self.refresh_token = data['idToken'], data['refreshToken']
        self.expires_at = time.time() + int(data.get('expiresIn', 3600))
        self.uid = data.get('localId')

    def _request(self, method, path, data=None, retry=True):
        if self.token is None or time.time() > self.expires_at - 300:
            self.login()
        url = f'{self.base}/{path.strip("/")}.json'
        try:
            response = self.http.request(method, url, params={'auth': self.token},
                                         data=None if data is None else json.dumps(data, ensure_ascii=False).encode('utf-8'),
                                         timeout=self.timeout)
        except self.requests.RequestException as exc:
            raise CloudError(f'Mất kết nối Firebase: {type(exc).__name__}') from exc
        if response.status_code == 401 and retry:
            self.token = None
            return self._request(method, path, data, retry=False)
        if not response.ok:
            raise CloudError(f'Firebase từ chối {method} /{path} ({response.status_code}): {response.text[:120]}')
        return response.json()

    def get(self, path):
        return self._request('GET', path)

    def put(self, path, data):
        return self._request('PUT', path, data)

    def patch(self, path, data):
        return self._request('PATCH', path, data)


class FileStore:
    """Cùng giao diện với FirebaseStore nhưng ghi một cây JSON cục bộ (để thử và kiểm thử)."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'firebase_gia_lap.json'
        self.lock = threading.Lock()
        self.fail_next = 0  # Kiểm thử: số lần gọi tiếp theo sẽ giả lập mất mạng.
        self.calls = []

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError, ValueError):
            return {}

    def _save(self, tree):
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(temp, self.path)

    def _check(self, method, path):
        self.calls.append((method, path))
        if self.fail_next > 0:
            self.fail_next -= 1
            raise CloudError('Giả lập mất mạng')

    @staticmethod
    def _parts(path):
        return [part for part in path.strip('/').split('/') if part]

    def _set(self, tree, parts, value):
        node = tree
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        if value is None:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = copy.deepcopy(value)

    def get(self, path):
        with self.lock:
            self._check('GET', path)
            node = self._load()
            for part in self._parts(path):
                if not isinstance(node, dict) or part not in node:
                    return None
                node = node[part]
            return copy.deepcopy(node)

    def put(self, path, data):
        with self.lock:
            self._check('PUT', path)
            tree = self._load()
            self._set(tree, self._parts(path), data)
            self._save(tree)
            return data

    def patch(self, path, data):
        with self.lock:
            self._check('PATCH', path)
            tree = self._load()
            base = self._parts(path)
            for key, value in data.items():
                self._set(tree, base + self._parts(key), value)
            self._save(tree)
            return data


def load_config(path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f'Không thấy {path}. Tạo file theo HUONG_DAN_CLOUD.md hoặc dùng --ghi-file.')
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    missing = [k for k in ('apiKey', 'databaseURL', 'pi_email', 'pi_password') if not config.get(k)]
    if missing:
        raise SystemExit(f'{path.name} thiếu: {", ".join(missing)}')
    if os.name == 'posix' and path.stat().st_mode & 0o077:
        log(f'CẢNH BÁO: {path.name} đang cho người khác đọc; chạy: chmod 600 {path}')
    return config


def default_config_path():
    here = Path(__file__).resolve().parent
    for candidate in (here / 'firebase_bi_mat.json', here.parent / 'firebase_bi_mat.json'):
        if candidate.exists():
            return candidate
    return here / 'firebase_bi_mat.json'


def make_store(args):
    if args.ghi_file:
        log(f'Chế độ --ghi-file: ghi JSON cục bộ vào {Path(args.ghi_file).resolve()}')
        return FileStore(args.ghi_file)
    return FirebaseStore(load_config(args.cau_hinh or default_config_path()))


# --------------------------------------------------------------------------- đọc CSV đang được ghi

class CsvTail:
    """Đọc dần các dòng HOÀN CHỈNH mới được ghi; giữ vị trí byte để đọc tiếp/gửi bù."""

    def __init__(self, path, offset=0):
        self.path = Path(path)
        self.offset = offset

    def read_new(self):
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            chunk = stream.read()
        end = chunk.rfind(b'\n')
        if end < 0:
            return [], self.offset
        text = chunk[:end + 1].decode('utf-8', errors='replace')
        if self.offset == 0:
            text = text.lstrip('﻿')
        rows = list(csv.reader(io.StringIO(text)))
        return rows, self.offset + end + 1


def is_control_csv(path):
    try:
        with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
            return tuple(next(csv.reader(stream), ())) in VALID_HEADERS
    except (OSError, UnicodeDecodeError):
        return False


def newest_csv(base):
    base = Path(base)
    candidates = []
    for pattern in ('ket_qua_*/*/du_lieu.csv', 'logs/*.csv', 'ket_qua_*/*/*.csv', '*/*/du_lieu.csv'):
        candidates.extend(base.glob(pattern))
    candidates = [p for p in candidates if '.cloud_bridge' not in p.parts]  # Bỏ CSV phát lại.
    candidates = sorted({p.resolve() for p in candidates}, key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[:20]:
        if is_control_csv(path):
            return path
    return None


def session_id_for(path):
    path = Path(path)
    return safe_key(path.parent.name if path.name == 'du_lieu.csv' else path.stem)


def read_run_config(csv_path):
    path = Path(csv_path).parent / 'cau_hinh.json'
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}


def describe_controller(config, override=None):
    if override:
        return override
    if config.get('bo_dieu_khien'):
        return CONTROLLER_LABELS.get(config['bo_dieu_khien'], config['bo_dieu_khien'])
    profile = config.get('profile') or {}
    if isinstance(profile, dict) and 'lower_c' in profile:
        return 'Q-learning v2'
    return 'Không rõ'


def band_for(config):
    profile = config.get('profile') if isinstance(config.get('profile'), dict) else {}
    target = num(profile.get('target_c')) or TARGET_C
    lower, upper = num(profile.get('lower_c')), num(profile.get('upper_c'))
    if lower is None or upper is None or not lower < target < upper:
        lower, upper = target - (TARGET_C - LOWER_C), target + (UPPER_C - TARGET_C)
    return target, lower, upper


# --------------------------------------------------------------------------- xử lý dòng -> mẫu, sự kiện, cảnh báo

class Engine:
    """Biến dòng CSV thành mẫu/sự kiện/cảnh báo. Trạng thái là dict để lưu và khôi phục khi gửi lỗi."""

    def __init__(self, session_id, lower=LOWER_C, upper=UPPER_C, alerts=True, state=None):
        self.session_id = session_id
        self.lower, self.upper = lower, upper
        self.alerts_enabled = alerts
        self.s = state or {
            'header_ok': None, 'last_bucket': None, 'last_alert': {}, 'out_since': None, 'out_alerted': False,
            'in_since': None, 'window': [], 'hold_started': False, 'last_cls': None, 'ended': False,
            'latest': None, 'sensor_bad': False, 'stage': None, 'transition': False,
        }

    def snapshot(self):
        return copy.deepcopy(self.s)

    def restore(self, state):
        self.s = state

    def _alert(self, out, kind, t, message, temp=None):
        # t = elapsed_s (đồng hồ đơn điệu của chương trình Pi) cho mọi khoảng thời gian/giới hạn lặp;
        # thời điểm hiển thị lấy từ timestamp_utc của đúng dòng đó.
        if not self.alerts_enabled or t is None:
            return
        last = self.s['last_alert'].get(kind)
        if kind not in NO_COOLDOWN and last is not None and t - last < COOLDOWN_S:
            return
        self.s['last_alert'][kind] = t
        ts_ms = self._row_ts_ms
        out['alerts'][f'{ts_ms}_{kind}'] = {
            'ts': ts_ms, 'loai': kind, 'muc': ALERT_LEVEL.get(kind, 'canh_bao'), 'noi_dung': message,
            'phien': self.session_id, 'nhiet_c': None if temp is None else round(temp, 3),
        }

    def feed(self, rows):
        out = {'samples': {}, 'events': {}, 'alerts': {}, 'diem': []}
        for values in rows:
            if not values:
                continue
            if self.s['header_ok'] is None:
                if tuple(values) not in VALID_HEADERS:
                    raise ValueError('CSV không đúng định dạng của do_nhiet_hop.py')
                self.s['header_ok'] = len(values)
                continue
            if len(values) != self.s['header_ok']:
                continue
            values = list(values) + [''] * (len(CSV_FIELDS) - len(values))
            self._row(dict(zip(CSV_FIELDS, values)), out)
        return out

    def _row(self, row, out):
        t = parse_ts(row['timestamp_utc'])
        elapsed = num(row['elapsed_s'])
        if t is None or elapsed is None:
            return
        self._row_ts_ms = int(t * 1000)
        event, cls = row['event'], classify(row['phase'])
        temp, age = num(row['temperature_c']), num(row['temperature_age_s'])
        lamp, fan = num(row['lamp_command_pct']), num(row['fan_command_pct'])
        rh = num(row['humidity_pct'])
        if event != 'MEASUREMENT':
            out['events'][f'{int(round(elapsed * 1000)):09d}'] = {
                't': round(elapsed, 3), 'su_kien': event, 'giai_doan': cls, 'pha': row['phase'],
                'ghi_chu': row['note'][:200], 'bong': lamp, 'quat': fan}
        if event == 'ERROR':
            self.s['loi'] = True
            self._alert(out, 'LOI', elapsed, f'Chương trình trên Pi báo lỗi: {row["note"][:120]}', temp)
        if event == 'END':
            self.s['ended'] = True
            self._alert(out, 'KET_THUC', elapsed, 'Lượt chạy đã kết thúc; Pi đã gửi lệnh tắt bóng và quạt.', temp)
        if event == 'MEASUREMENT':
            self.s['dem_do'] = self.s.get('dem_do', 0) + 1
        if event == 'MEASUREMENT' and (temp is None or (age is not None and age > SENSOR_STALE_S)):
            self.s['dem_loi_do'] = self.s.get('dem_loi_do', 0) + 1
            if not self.s['sensor_bad']:
                self.s['sensor_bad'] = True
                self._alert(out, 'LOI_CAM_BIEN', elapsed, 'Mất số đo DS18B20; Pi sẽ tự dừng nếu quá 3 s.', temp)
        elif event == 'MEASUREMENT':
            self.s['sensor_bad'] = False
        if temp is None:
            return
        stage = stage_of(row['phase'])
        lo, hi = (stage['vung_c'] if stage else (self.lower, self.upper))
        if stage:
            self._stage_change(out, elapsed, stage, temp)
        in_band = lo <= temp <= hi
        self.s['latest'] = {
            'ts': int(t * 1000), 'elapsed_s': round(elapsed, 1), 'nhiet_c': round(temp, 3),
            'do_am_pct': rh, 'bong_pct': lamp, 'quat_pct': fan, 'giai_doan': cls,
            'giai_doan_ten': PHASE_LABELS[cls], 'pha': row['phase'], 'trong_vung': in_band,
            'xu_huong_c_phut': num(row['trend_c_per_min']), 'su_kien': event, 'vung_c': [lo, hi],
            'muc_tieu_c': stage['muc_tieu_c'] if stage else None,
            'ngay_ap': stage['ngay'] if stage else None, 'giai_doan_ap': stage['giai_doan'] if stage else None,
        }
        if event != 'MEASUREMENT':
            return
        out.setdefault('diem', []).append((t, temp, in_band, cls))
        bucket = int(elapsed // SAMPLE_EVERY_S)
        if bucket != self.s['last_bucket']:
            self.s['last_bucket'] = bucket
            out['samples'][f'{bucket * SAMPLE_EVERY_S:06d}'] = {
                't': round(elapsed, 1), 'T': round(temp, 3), 'RH': rh, 'L': lamp, 'F': fan, 'g': cls,
                **({'n': stage['ngay'], 'k': stage['giai_doan']} if stage else {})}
        if cls == 'giu_nhiet':
            self.s['hold_started'] = True
        self._guard_alert(out, elapsed, cls, temp)
        self._band_alert(out, elapsed, cls, temp, in_band, lo, hi)
        self._drop_alert(out, elapsed, cls, temp, lamp)
        self.s['last_cls'] = cls

    def _guard_alert(self, out, t, cls, temp):
        if cls == 'bao_ve' and self.s['last_cls'] != 'bao_ve':
            self._alert(out, 'BAO_VE', t, f'Bảo vệ quá nhiệt kích hoạt ở {temp:.2f} °C: tắt bóng, quạt 100%.', temp)

    def _stage_change(self, out, t, stage, temp):
        previous = self.s.get('stage')
        self.s['stage'] = stage
        if previous is None or previous['giai_doan'] == stage['giai_doan']:
            return
        lo, hi = stage['vung_c']
        self._alert(out, 'CHUYEN_GIAI_DOAN', t, f'Chuyển sang giai đoạn {stage["giai_doan"]} (ngày {stage["ngay"]}): '
                    f'mốc {stage["muc_tieu_c"]:.1f} °C, vùng {lo:.1f}–{hi:.1f} °C.', temp)
        # Đang chuyển mốc: chưa tính "ngoài vùng" cho tới khi nhiệt vào vùng mới.
        self.s.update(transition=True, out_since=None, in_since=None, out_alerted=False)

    def _band_alert(self, out, t, cls, temp, in_band, lo=None, hi=None):
        lo, hi = (self.lower, self.upper) if lo is None else (lo, hi)
        if not (self.s['hold_started'] and cls in HOLD):
            self.s['out_since'] = self.s['in_since'] = None
            return
        if self.s.get('transition'):
            if not in_band:
                return
            self.s['transition'] = False
        if not in_band:
            self.s['in_since'] = None
            self.s['out_since'] = self.s['out_since'] or t
            if not self.s['out_alerted'] and t - self.s['out_since'] >= OUT_OF_BAND_S:
                before = len(out['alerts'])
                side = 'thấp' if temp < lo else 'cao'
                self._alert(out, 'NGOAI_VUNG', t, f'Nhiệt {side} ngoài vùng {lo:.1f}–{hi:.1f} °C '
                            f'quá {OUT_OF_BAND_S} s (hiện {temp:.2f} °C).', temp)
                self.s['out_alerted'] = len(out['alerts']) > before
        else:
            self.s['out_since'] = None
            if self.s['out_alerted']:
                self.s['in_since'] = self.s['in_since'] or t
                if t - self.s['in_since'] >= SETTLED_S:
                    self._alert(out, 'ON_DINH', t, f'Đã ổn định lại trong vùng {SETTLED_S} s (hiện {temp:.2f} °C).', temp)
                    self.s['out_alerted'], self.s['in_since'] = False, None

    def _drop_alert(self, out, t, cls, temp, lamp):
        window = self.s['window']
        if cls not in ('giu_nhiet', 'phuc_hoi') or not lamp:
            window.clear()  # Chỉ xét khi bóng đang sưởi; nguội do tắt bóng là hoạt động bình thường.
            return
        window.append([t, temp])
        while window and t - window[0][0] > DROP_WINDOW_S:
            window.pop(0)
        if t - window[0][0] >= DROP_WINDOW_S - 5:
            peak = max(value for _, value in window)
            if peak - temp >= DROP_ALERT_C:
                self._alert(out, 'NGHI_MO_NAP', t, f'Đang sưởi nhưng nhiệt tụt {peak - temp:.2f} °C trong '
                            f'{DROP_WINDOW_S} s: kiểm tra nắp hộp/luồng gió.', temp)


# --------------------------------------------------------------------------- tóm tắt một lượt (thống nhất cho mọi bộ điều khiển)

def summarize_csv(path, lower=LOWER_C, upper=UPPER_C, target=TARGET_C):
    with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    hold, started, ended, errors, guards = [], False, False, 0, 0
    first_elapsed = warm_start = hold_start = None
    last_cls = None
    for row in rows:
        cls, elapsed, temp = classify(row.get('phase')), num(row.get('elapsed_s')), num(row.get('temperature_c'))
        if row.get('event') == 'END':
            ended = True
        if row.get('event') == 'ERROR':
            errors += 1
        if elapsed is None:
            continue
        first_elapsed = elapsed if first_elapsed is None else first_elapsed
        if cls == 'lam_am' and warm_start is None:
            warm_start = elapsed
        if cls == 'giu_nhiet' and not started:
            started, hold_start = True, elapsed
        if started and cls == 'bao_ve' and last_cls != 'bao_ve':
            guards += 1
        last_cls = cls
        if started and cls in HOLD and row.get('event') == 'MEASUREMENT' and temp is not None:
            stage = stage_of(row.get('phase'))
            hold.append((elapsed, temp, row.get('lamp_command_pct'), row.get('fan_command_pct'),
                         stage['muc_tieu_c'] if stage else target,
                         *(stage['vung_c'] if stage else (lower, upper)), stage['giai_doan'] if stage else None))
    if not hold:
        return {'trang_thai': 'CHUA_CO_GIU_NHIET', 'ket_thuc': ended, 'so_loi': errors}
    temps = [h[1] for h in hold]
    mean = sum(temps) / len(temps)
    changes = sum(1 for a, b in zip(hold, hold[1:]) if (a[2], a[3]) != (b[2], b[3]))
    duration = hold[-1][0] - hold[0][0]
    per_stage = {}
    for gd in sorted({h[7] for h in hold if h[7] is not None}):
        rows_gd = [h for h in hold if h[7] == gd]
        per_stage[str(gd)] = {
            'muc_tieu_c': rows_gd[0][4], 'vung_c': [rows_gd[0][5], rows_gd[0][6]], 'so_mau': len(rows_gd),
            'mae_c': round(sum(abs(h[1] - h[4]) for h in rows_gd) / len(rows_gd), 4),
            'trong_vung_pct': round(100 * sum(h[5] <= h[1] <= h[6] for h in rows_gd) / len(rows_gd), 2)}
    staged = bool(per_stage)
    return {
        'trang_thai': 'HOAN_TAT' if ended and duration >= 590 and not errors else 'CHUA_DU',
        'ket_thuc': ended, 'so_loi': errors, 'so_mau_giu': len(hold),
        'thoi_gian_giu_s': round(duration, 1),
        'lam_am_s': None if warm_start is None else round(hold_start - warm_start, 1),
        'mae_c': round(sum(abs(h[1] - h[4]) for h in hold) / len(hold), 4),
        'trong_vung_pct': round(100 * sum(h[5] <= h[1] <= h[6] for h in hold) / len(hold), 2),
        'do_lech_chuan_c': round(math.sqrt(sum((v - mean) ** 2 for v in temps) / len(temps)), 4),
        'nhiet_tb_c': round(mean, 3), 'nhiet_min_c': round(min(temps), 3), 'nhiet_max_c': round(max(temps), 3),
        'so_lan_doi_muc': changes, 'so_lan_bao_ve': guards,
        'vung_c': [lower, upper], 'muc_tieu_c': target,
        **({'theo_giai_doan': per_stage, 'nhieu_giai_doan': True} if staged else {}),
        'ghi_chu': ('MAE/% trong vùng tính theo mốc của giai đoạn tại từng mẫu. ' if staged else '') + 'Bridge tính thống nhất theo mẫu 1 s trong giai đoạn giữ nhiệt (gồm bảo vệ/phục hồi); '
                   'có thể lệch nhẹ so với báo cáo gốc tính theo trọng số thời gian.',
    }


def original_result(csv_path):
    folder = Path(csv_path).parent
    for path in (folder / 'ket_qua.json', folder / 'phan_tich' / 'ket_qua.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        keep = ('status', 'controller', 'mae_c', 'in_band_pct', 'band_c', 'lower_c', 'upper_c', 'min_c', 'max_c',
                'pair_changes', 'soft_guard_count', 'covered_s')
        return {k: data[k] for k in keep if k in data and not isinstance(data[k], (dict, list))}
    return None


# --------------------------------------------------------------------------- lệnh DỪNG

def find_writer_pids(csv_path, proc_root='/proc', readlink=os.readlink, listdir=os.listdir, read_cmdline=None):
    """Trả các PID python đang mở đúng file CSV (tức chương trình điều khiển đang ghi nó)."""
    target = os.path.realpath(csv_path)
    me = os.getpid()
    if read_cmdline is None:
        def read_cmdline(pid):
            with open(os.path.join(proc_root, pid, 'cmdline'), 'rb') as stream:
                return stream.read().replace(b'\0', b' ').decode('utf-8', 'replace')
    pids = []
    try:
        entries = listdir(proc_root)
    except OSError:
        return pids
    for pid in entries:
        if not pid.isdigit() or int(pid) == me:
            continue
        fd_dir = os.path.join(proc_root, pid, 'fd')
        try:
            fds = listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                if readlink(os.path.join(fd_dir, fd)) == target:
                    if 'python' in read_cmdline(pid):
                        pids.append(int(pid))
                    break
            except OSError:
                continue
    return pids


# --------------------------------------------------------------------------- bắt đầu lượt từ app (có rào an toàn)

CONTROL_SCRIPTS = ('ap_trung.py', 'thu_rl_du_lieu_moi.py', 'kiem_tra_giu_nhiet.py', 'do_nhiet_hop.py',
                   'khao_sat_nhiet.py', 'do_dap_ung_bo_sung.py', 'thu_mach.py', 'thu_mach_12v.py')
DEMO_SPEEDS = (86400, 300, 120, 60)       # Thời gian thật, 1 ngày = 5 / 2 / 1 phút.
RUN_MINUTES = (10, 20, 30, 45, 60)        # Lượt từ xa ngắn hơn giới hạn 100 phút của ap_trung.
START_MAX_C = 30.0                        # Giống ap_trung.py: hộp phải nguội trước khi làm ấm.
APP_SESSION = 'hopap_app'


def running_controllers(proc_root='/proc', listdir=os.listdir, read_cmdline=None):
    """Các (pid, lệnh) của chương trình điều khiển đang chạy (giữ GPIO18/23). Rỗng nếu không có /proc."""
    if read_cmdline is None:
        def read_cmdline(pid):
            with open(os.path.join(proc_root, pid, 'cmdline'), 'rb') as stream:
                return stream.read().replace(b'\0', b' ').decode('utf-8', 'replace')
    found = []
    try:
        entries = listdir(proc_root)
    except OSError:
        return found
    for pid in entries:
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            cmd = read_cmdline(pid)
        except OSError:
            continue
        if 'python' in cmd and any(name in cmd for name in CONTROL_SCRIPTS):
            found.append((int(pid), cmd.strip()[:160]))
    return found


def read_box_temperature(root='/sys/bus/w1/devices'):
    from kiem_tra_dht11 import read_ds18b20
    return read_ds18b20(root)


def launch_run(base, controller, minutes, use_humidity_file, batch=False):
    """Chạy ap_trung.py tách khỏi bridge (tmux nếu có, không thì setsid), ghi log. Trả mô tả cách chạy.
    batch=True: một phiên của mẻ ấp (--theo-me)."""
    import subprocess
    base = Path(base)
    python = base / '.venv' / 'bin' / 'python'
    python = str(python) if python.exists() else 'python3'
    log_dir = base / '.cloud_bridge'
    log_dir.mkdir(exist_ok=True)
    log = log_dir / f'luot_app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    args = [python, 'ap_trung.py', '--bo-dieu-khien', controller, '--phut', str(minutes)]
    if batch:
        args.append('--theo-me')
    if use_humidity_file:
        args.append('--do-am')
    shell = f'cd {base} && ' + ' '.join(args) + f' 2>&1 | tee -a {log}'
    env = dict(os.environ, TERM=os.environ.get('TERM', 'xterm'))
    if shutil.which('tmux'):
        subprocess.run(['tmux', 'kill-session', '-t', APP_SESSION], capture_output=True, env=env)
        subprocess.run(['tmux', 'new-session', '-d', '-s', APP_SESSION, shell], check=True, env=env)
        return f'tmux:{APP_SESSION}'
    subprocess.Popen(['bash', '-c', shell], cwd=base, start_new_session=True, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f'log:{log.name}'


def stop_is_fresh(command, handled_ts, now=None):
    if not isinstance(command, dict) or command.get('value') is not True:
        return False
    ts = command.get('ts')
    if not isinstance(ts, (int, float)) or ts <= (handled_ts or 0):
        return False
    now = now_ms() if now is None else now
    return now - ts <= STOP_MAX_AGE_S * 1000


# --------------------------------------------------------------------------- vòng chạy

class Bridge:
    def __init__(self, store, base, csv_path=None, state_path=None, period=5.0, source='truc_tiep', clock=time.time,
                 lich_path=None, do_am_path=None, tay_path=None, nao_path=None, notifier=None, thu_log_path=None):
        self.store, self.base, self.fixed_csv = store, Path(base), Path(csv_path) if csv_path else None
        self.lich_path = Path(lich_path) if lich_path else me_ap.MAC_DINH
        self.lich_sig, self.lich_put_at = None, 0.0
        self.do_am_path = Path(do_am_path) if do_am_path else Path(__file__).resolve().with_name('do_am_moi_nhat.json')
        self.tay_path = Path(tay_path) if tay_path else Path(__file__).resolve().with_name('lenh_tay.json')
        self.nao_path = Path(nao_path) if nao_path else Path(__file__).resolve().with_name('nao_rl.json')
        self.thu_log_path = Path(thu_log_path) if thu_log_path else Path(__file__).resolve().with_name('ket_qua_thu_nhieu.jsonl')
        self.notifier = notifier  # TelegramNotifier hoặc None
        self.nao_ts = None
        self.health_at, self.started_at, self.cloud_ok_at = None, clock(), None
        self.health_reader = suc_khoe.collect  # thay được khi kiểm thử
        self.do_am_sig, self.do_am_put_at = None, 0.0
        # Phụ thuộc phần cứng, thay được khi kiểm thử.
        self.running_probe = running_controllers
        self.box_temperature = read_box_temperature
        self.launcher = launch_run
        self.state_path = Path(state_path) if state_path else Path(base) / '.cloud_bridge' / 'trang_thai.json'
        self.period, self.source, self.clock = period, source, clock
        self.state = self._load_state()
        self.engine = self.tail = None
        self.online = None
        self.last_growth = clock()
        self.finished_at = None
        self.silent_alerted = False

    # ---- trạng thái lưu bền
    def _load_state(self):
        try:
            return json.loads(self.state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {'stop_handled_ts': 0}

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.state, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.state_path)

    def _path(self, *parts):
        return '/'.join((DEVICE,) + parts)

    # ---- chọn phiên
    def _select_csv(self):
        path = self.fixed_csv or newest_csv(self.base)
        if path is None:
            return None
        path = Path(path).resolve()
        if self.tail is None or self.tail.path != path:
            self._open_session(path)
        return path

    def _open_session(self, path):
        sid = session_id_for(path)
        config = read_run_config(path)
        target, lower, upper = band_for(config)
        saved = self.state.get('phien') or {}
        if saved.get('csv') == str(path):
            offset, engine_state = saved.get('offset', 0), saved.get('engine')
        else:
            offset, engine_state = 0, None
        self.tail = CsvTail(path, offset)
        self.engine = Engine(sid, lower, upper, alerts=True, state=engine_state)
        self.meta = {'bo_dieu_khien': describe_controller(config), 'file': path.name, 'thu_muc': path.parent.name,
                     'muc_tieu_c': target, 'vung_c': [lower, upper], 'nguon': self.source,
                     'bat_dau_ts': None}
        self.state['phien'] = {'csv': str(path), 'offset': offset, 'engine': self.engine.snapshot(), 'id': sid}
        self.last_growth, self.finished_at, self.silent_alerted = self.clock(), None, False
        log(f'Theo dõi phiên {sid} ({self.meta["bo_dieu_khien"]}) từ {path}')

    # ---- một chu kỳ
    def cycle(self):
        path = self._select_csv()
        if path is not None:
            self._push_rows()
        self._handle_stop()
        if self.source == 'truc_tiep':  # Phát lại trên laptop không được ghi đè lịch của Pi.
            self._handle_day_command()
            self._handle_batch_command()
            self._handle_run_command()
            self._handle_manual_command()
            self._handle_disturbance_command()
            self._supervise_batch()
            self._publish_brain()
            self._publish_health()
            self._publish_schedule()
            self._publish_humidity()
        try:
            self.store.put(self._path('trang_thai', 'bridge'), {
                'ts': now_ms(), 'phien_ban': VERSION, 'may': socket.gethostname(),
                'phien': self.engine.session_id if self.engine else None})
            self._set_online(True)
            self.cloud_ok_at = now_ms()
        except CloudError as exc:
            self._set_online(False, exc)

    def _post_alerts(self, alerts):
        self.store.patch(self._path('alerts'), alerts)
        if self.notifier is not None and self.source == 'truc_tiep':
            for key, alert in alerts.items():
                self.notifier.offer(key, alert)

    def _set_online(self, ok, exc=None):
        if ok and self.online is not True:
            log('Đã kết nối đám mây.')
        if not ok and self.online is not False:
            log(f'Chưa gửi được lên đám mây (sẽ gửi bù): {exc}')
        self.online = ok

    def _push_rows(self):
        rows, new_offset = self.tail.read_new()
        before = self.engine.snapshot()
        try:
            out = self.engine.feed(rows)
        except ValueError as exc:
            log(f'Bỏ qua {self.tail.path}: {exc}')
            self.fixed_csv = None
            return
        now = self.clock()
        if rows:
            self.last_growth, self.silent_alerted = now, False
        elif (not self.engine.s['ended'] and not self.silent_alerted and self.engine.s['latest']
              and now - self.last_growth > CSV_SILENT_S and self.source == 'truc_tiep'):
            out['alerts'][f'{int(now * 1000)}_PI_KHONG_GHI'] = {
                'ts': int(now * 1000), 'loai': 'PI_KHONG_GHI', 'muc': ALERT_LEVEL['PI_KHONG_GHI'],
                'noi_dung': f'CSV không cập nhật quá {CSV_SILENT_S} s mà chưa kết thúc: kiểm tra chương trình trên Pi.',
                'phien': self.engine.session_id, 'nhiet_c': None}
            self.silent_alerted = True
        if (not rows and not self.engine.s['ended'] and self.engine.s['latest'] and self.source == 'truc_tiep'
                and now - self.last_growth > CSV_SILENT_S and not self.running()):
            # CSV đứng mà không còn chương trình điều khiển nào: lượt đã chết không kịp ghi END (bị kill,
            # mất điện...). Đóng lượt để app không kẹt "Đang chạy", và nhắc kiểm tra tải bằng mắt.
            self.engine.s['ended'] = True
            self.engine.s['bat_thuong'] = True
            out['alerts'][f'{int(now * 1000)}_DUNG_BAT_THUONG'] = {
                'ts': int(now * 1000), 'loai': 'DUNG_BAT_THUONG', 'muc': ALERT_LEVEL['DUNG_BAT_THUONG'],
                'noi_dung': 'Chương trình điều khiển đã dừng mà không ghi kết thúc (bị tắt đột ngột?). '
                            'Kiểm tra tận nơi bóng và quạt đã tắt; nếu bóng còn sáng hãy rút adapter 12 V.',
                'phien': self.engine.session_id, 'nhiet_c': None}
        test = self._track_disturbance(out)
        sid = self.engine.session_id
        session_patch = {}
        if self.engine.s['latest'] and not self.state.get('meta_sent_' + sid):
            latest = self.engine.s['latest']
            if self.meta['bat_dau_ts'] is None:
                self.meta['bat_dau_ts'] = latest['ts'] - int(latest['elapsed_s'] * 1000)
            session_patch['meta'] = self.meta
        session_patch.update({f'samples/{k}': v for k, v in out['samples'].items()})
        session_patch.update({f'events/{k}': v for k, v in out['events'].items()})
        try:
            if session_patch:
                self.store.patch(self._path('sessions', sid), session_patch)
            if out['alerts']:
                self._post_alerts(out['alerts'])
                for alert in out['alerts'].values():
                    log(f'CẢNH BÁO {alert["loai"]}: {alert["noi_dung"]}')
            latest = self.engine.s['latest']
            if latest:
                live = dict(vung_c=self.meta['vung_c'], muc_tieu_c=self.meta['muc_tieu_c'])
                live.update({k: v for k, v in latest.items() if v is not None})
                live = dict(live, phien=sid, bo_dieu_khien=self.meta['bo_dieu_khien'],
                            trang_thai='KET_THUC' if self.engine.s['ended'] else 'DANG_CHAY',
                            nguon=self.source, bridge_ts=now_ms())
                self.store.put(self._path('live'), live)
            if test is not None:
                self.store.put(self._path('thu_nhieu', test['id']), test)
        except CloudError as exc:
            self.engine.restore(before)  # Không tiến vị trí đọc: lần sau gửi lại đúng các dòng này (khóa cố định).
            self._set_online(False, exc)
            return
        if 'meta' in session_patch:
            self.state['meta_sent_' + sid] = True
        if test is not None and test['trang_thai'] not in tn.ACTIVE and not test.get('da_bao'):
            test['da_bao'] = True  # chỉ đánh dấu khi cảnh báo kết quả đã lên Firebase
            self._log_disturbance(test)
        self.tail.offset = new_offset
        self.state['phien'] = {'csv': str(self.tail.path), 'offset': new_offset,
                               'engine': self.engine.snapshot(), 'id': sid}
        self._save_state()
        if self.engine.s['ended']:
            self._finish_session()

    def _finish_session(self):
        sid = self.engine.session_id
        if self.state.get('summary_done_' + sid):
            return
        self.finished_at = self.finished_at or self.clock()
        original = original_result(self.tail.path)
        if original is None and self.clock() - self.finished_at < 60:
            return  # Chờ chương trình điều khiển ghi ket_qua.json (tối đa 60 s).
        summary = summarize_csv(self.tail.path, *self.meta['vung_c'], self.meta['muc_tieu_c'])
        summary['bo_dieu_khien'] = self.meta['bo_dieu_khien']
        summary['ket_qua_goc'] = original
        try:
            self.store.put(self._path('sessions', sid, 'summary'), summary)
        except CloudError as exc:
            self._set_online(False, exc)
            return
        self.state['summary_done_' + sid] = True
        self._save_state()
        log(f'Đã gửi tóm tắt phiên {sid}: MAE {summary.get("mae_c")} °C, trong vùng {summary.get("trong_vung_pct")} %')

    def _handle_stop(self):
        try:
            command = self.store.get(self._path('commands', 'stop'))
        except CloudError:
            return
        handled = self.state.get('stop_handled_ts', 0)
        if not stop_is_fresh(command, handled):
            if isinstance(command, dict) and command.get('value') is True and command.get('ts', 0) > handled:
                self.state['stop_handled_ts'] = command['ts']  # Lệnh quá cũ: ghi nhận đã bỏ qua, không thực hiện.
                self._save_state()
                self._reset_stop(command, 'BO_QUA_LENH_CU')
            return
        result = self.execute_stop(command)
        if self.state.get('me_chay'):  # Dừng khẩn cấp = tạm dừng mẻ; app có nút "Chạy tiếp".
            self.state['me_chay'] = False
            self.state['me_ly_do'] = f'Dừng khẩn cấp từ {str(command.get("by", "?"))[:60]}'
            self.lich_sig = None
        self.state['stop_handled_ts'] = command['ts']
        self._save_state()
        self._reset_stop(command, result)
        t = self.clock()
        alert = {'ts': int(t * 1000), 'loai': 'DUNG_TU_XA', 'muc': ALERT_LEVEL['DUNG_TU_XA'],
                 'noi_dung': f'Lệnh dừng từ {command.get("by", "?")}: {result}.',
                 'phien': self.engine.session_id if self.engine else None, 'nhiet_c': None}
        try:
            self._post_alerts({f'{alert["ts"]}_DUNG_TU_XA': alert})
        except CloudError:
            pass
        log(f'LỆNH DỪNG từ {command.get("by", "?")}: {result}')

    def execute_stop(self, command):
        if self.tail is None or self.engine.s['ended']:
            return 'KHONG_CO_LUOT_DANG_CHAY'
        if self.source != 'truc_tiep' or not os.path.isdir('/proc'):
            return 'MO_PHONG_KHONG_GUI_TIN_HIEU'
        pids = find_writer_pids(self.tail.path)
        if not pids:
            return 'KHONG_TIM_THAY_TIEN_TRINH'
        for pid in pids:
            os.kill(pid, signal.SIGTERM)
        return f'DA_GUI_SIGTERM_PID_{"_".join(map(str, pids))}'

    def _pi_email(self):
        return self.store.config.get('pi_email', 'pi') if hasattr(self.store, 'config') else 'pi'

    def _publish_schedule(self):
        try:
            data = dict(me_ap.current(me_ap.load(self.lich_path)), co_me=True,
                        chay=bool(self.state.get('me_chay')), ly_do_dung=self.state.get('me_ly_do'))
        except me_ap.LichError as exc:
            data = {'co_me': False, 'loi': str(exc), 'chay': False}
        sig = json.dumps({k: v for k, v in data.items() if k != 'giay_den_ngay_sau'}, sort_keys=True)
        now = self.clock()
        if sig == self.lich_sig and now - self.lich_put_at < 30:
            return
        try:
            self.store.put(self._path('lich'), dict(data, bridge_ts=now_ms()))
            self.lich_sig, self.lich_put_at = sig, now
        except CloudError:
            pass

    # ---- lệnh tạo/kết thúc mẻ và bắt đầu lượt (cùng khuôn: mới, chưa xử lý, ≤ 10 phút, mỗi lệnh một lần)
    def _take_command(self, name):
        try:
            command = self.store.get(self._path('commands', name))
        except CloudError:
            return None
        if not isinstance(command, dict) or command.get('da_xu_ly') is True:
            return None
        ts = command.get('ts')
        if not isinstance(ts, (int, float)) or ts <= self.state.get(f'{name}_handled_ts', 0):
            return None
        self.state[f'{name}_handled_ts'] = ts
        self._save_state()
        if now_ms() - ts > STOP_MAX_AGE_S * 1000:
            self._reply(name, command, 'BO_QUA_LENH_CU')
            return None
        return command

    def _reply(self, name, command, result, alert_kind=None, alert_text=None):
        reply = dict(command, by=self._pi_email(), yeu_cau_boi=str(command.get('by', '?'))[:100],
                     da_xu_ly=True, ket_qua=result[:200], xu_ly_ts=now_ms())
        try:
            self.store.put(self._path('commands', name), reply)
        except CloudError:
            pass
        if alert_kind:
            alert = {'ts': now_ms(), 'loai': alert_kind, 'muc': ALERT_LEVEL.get(alert_kind, 'thong_tin'),
                     'noi_dung': alert_text, 'phien': self.engine.session_id if self.engine else None, 'nhiet_c': None}
            try:
                self._post_alerts({f'{alert["ts"]}_{alert_kind}': alert})
            except CloudError:
                pass
        log(f'LỆNH {name} từ {reply["yeu_cau_boi"]}: {result}')

    def _handle_batch_command(self):
        """Mẻ ấp từ app: tạo = chạy RL ngay; tiếp tục sau khi tạm dừng; kết thúc = dừng và lưu lịch."""
        command = self._take_command('me_ap')
        if command is None:
            return
        who = str(command.get('by', '?'))[:100]
        action = command.get('hanh_dong')
        busy = self.running()
        if action == 'tao':
            day, speed = command.get('ngay'), command.get('giay_moi_ngay')
            if isinstance(day, bool) or not isinstance(day, (int, float)) or day != int(day) or not 1 <= day <= 21 \
                    or speed not in DEMO_SPEEDS:
                return self._reply('me_ap', command, 'KHONG_HOP_LE')
            if self.state.get('me_chay') or busy:
                return self._reply('me_ap', command, 'TU_CHOI: đang có mẻ chạy, kết thúc mẻ trước')
            if self.source != 'truc_tiep' or not os.path.isdir('/proc'):
                return self._reply('me_ap', command, 'TU_CHOI: chỉ chạy được trên Raspberry Pi')
            if self.box_temperature() is None:
                return self._reply('me_ap', command, 'TU_CHOI: không đọc được DS18B20, kiểm tra dây cảm biến')
            self._archive_batch()
            me_ap.start_batch(self.lich_path, ngay=int(day), giay_moi_ngay=speed, nguon=f'app:{who}')
            self.state.update(me_chay=True, me_ly_do=None, me_loi=0, me_khoi_dong_ts=0)
            self._save_state()
            self.lich_sig = None
            info = me_ap.current(me_ap.load(self.lich_path))
            return self._reply('me_ap', command, 'DA_TAO', 'TAO_ME',
                               f'{who} tạo mẻ mới: {me_ap.describe(info)}. Hệ thống bắt đầu làm ấm bằng RL.')
        if action == 'tiep_tuc':
            try:
                info = me_ap.current(me_ap.load(self.lich_path))
            except me_ap.LichError:
                return self._reply('me_ap', command, 'KHONG_CO_ME')
            if info['het_lich']:
                return self._reply('me_ap', command, 'TU_CHOI: mẻ đã hết 21 ngày, hãy kết thúc mẻ')
            if self.state.get('me_chay'):
                return self._reply('me_ap', command, 'TU_CHOI: mẻ đang chạy')
            self.state.update(me_chay=True, me_ly_do=None, me_loi=0, me_khoi_dong_ts=0)
            self._save_state()
            self.lich_sig = None
            return self._reply('me_ap', command, 'DA_TIEP_TUC', 'TIEP_TUC_ME', f'{who} cho mẻ ấp chạy tiếp.')
        if action == 'ket_thuc':
            if not self.lich_path.exists():
                return self._reply('me_ap', command, 'KHONG_CO_ME')
            self.state.update(me_chay=False, me_ly_do='Đã kết thúc mẻ')
            if busy:
                self.execute_stop(command)
                self.state['me_cho_ket_thuc'] = True  # lưu lịch khi chương trình điều khiển đã thoát
                self._save_state()
                return self._reply('me_ap', command, 'DANG_KET_THUC', 'KET_THUC_ME',
                                   f'{who} kết thúc mẻ ấp: tắt bóng và quạt, lưu lịch.')
            self._archive_batch()
            self._save_state()
            return self._reply('me_ap', command, 'DA_KET_THUC', 'KET_THUC_ME', f'{who} kết thúc mẻ ấp.')
        return self._reply('me_ap', command, 'KHONG_HOP_LE')

    def _archive_batch(self):
        if self.lich_path.exists():  # Lưu lại, không xóa.
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            os.replace(self.lich_path, self.lich_path.with_name(f'trang_thai_me_ap.ket_thuc_{stamp}.json'))
        self.state['me_cho_ket_thuc'] = False
        self.lich_sig = None

    def _pause_batch(self, reason, kind='TAM_DUNG_ME', text=None):
        self.state.update(me_chay=False, me_ly_do=reason)
        self._save_state()
        self.lich_sig = None
        alert = {'ts': now_ms(), 'loai': kind, 'muc': ALERT_LEVEL[kind], 'noi_dung': text or f'Mẻ ấp tạm dừng: {reason}.',
                 'phien': self.engine.session_id if self.engine else None, 'nhiet_c': None}
        try:
            self._post_alerts({f'{alert["ts"]}_{kind}': alert})
        except CloudError:
            pass
        log(alert['noi_dung'])

    def _supervise_batch(self):
        """Giữ mẻ chạy như máy ấp thật: hết phiên thì chạy phiên mới, Pi khởi động lại thì chạy tiếp, hết ngày 21 thì dừng."""
        if self.state.get('me_cho_ket_thuc'):
            if not self.running():
                self._archive_batch()
                self._save_state()
            return
        if not self.state.get('me_chay') or self.source != 'truc_tiep':
            return
        try:
            info = me_ap.current(me_ap.load(self.lich_path))
        except me_ap.LichError:
            return self._pause_batch('không còn file lịch của mẻ')
        busy = self.running()
        if info['het_lich']:
            if busy:
                self.execute_stop({})
            return self._pause_batch('đã hết 21 ngày', 'HET_ME', 'Mẻ ấp đã đủ 21 ngày: hệ thống dừng sưởi.')
        if busy:
            return
        now = time.time()
        last = self.state.get('me_khoi_dong_ts') or 0
        if now - last < ME_LAUNCH_GAP_S:
            return
        if last and now - last < ME_RETRY_WINDOW_S:
            self.state['me_loi'] = self.state.get('me_loi', 0) + 1
            if self.state['me_loi'] >= ME_MAX_FAILS:
                return self._pause_batch(
                    f'chương trình điều khiển dừng {ME_MAX_FAILS} lần liên tiếp trong {ME_RETRY_WINDOW_S // 60} phút',
                    text='Mẻ ấp TẠM DỪNG: chương trình điều khiển dừng 3 lần liên tiếp ngay sau khi chạy. '
                         'Kiểm tra cảm biến DS18B20, bóng, adapter 12 V rồi bấm "Chạy tiếp" trên app.')
        elif last:
            self.state['me_loi'] = 0
        if self.box_temperature() is None:
            self.state['me_khoi_dong_ts'] = now  # đợi rồi thử lại; tính như một lần lỗi nếu cứ lặp lại
            self._save_state()
            log('Mẻ ấp: chưa đọc được DS18B20, chờ để chạy phiên mới.')
            return
        left = (info['giay_den_ngay_sau'] or 0) + (me_ap.SO_NGAY - info['ngay']) * info['giay_moi_ngay']
        minutes = max(1, min(MAX_SEGMENT_MINUTES, math.ceil(left / 60)))
        from do_am import read_latest
        humidity_ok = read_latest(self.do_am_path)[2] == ''
        try:
            how = self.launcher(self.base, 'rl', minutes, humidity_ok, batch=True)
        except Exception as exc:  # noqa: BLE001
            self.state['me_khoi_dong_ts'] = now
            self._save_state()
            log(f'Mẻ ấp: không chạy được phiên mới: {type(exc).__name__}: {exc}')
            return
        first = not last
        self.state['me_khoi_dong_ts'] = now
        self._save_state()
        kind = 'BAT_DAU_LUOT' if first else 'TIEP_TUC_ME'
        text = (f'Mẻ ấp bắt đầu chạy RL ({me_ap.describe(info)}); phiên {minutes} phút, {how}.' if first else
                f'Mẻ ấp chạy phiên mới ({me_ap.describe(info)}); {minutes} phút, {how}.')
        alert = {'ts': now_ms(), 'loai': kind, 'muc': ALERT_LEVEL[kind], 'noi_dung': text,
                 'phien': None, 'nhiet_c': None}
        try:
            self._post_alerts({f'{alert["ts"]}_{kind}': alert})
        except CloudError:
            pass
        log(text)

    def running(self):
        return self.running_probe()

    def _handle_manual_command(self):
        """Chỉnh tay có hạn giờ, đè lên RL/thermostat trong lượt ap_trung đang chạy. Bảo vệ trên Pi vẫn thắng."""
        command = self._take_command('tay')
        if command is None:
            return
        who = str(command.get('by', '?'))[:100]
        action = command.get('hanh_dong')
        if action == 'tra_ve':
            self._write_manual({'bong': 0, 'quat': 100, 'het_han': 0, 'by': who})
            return self._reply('tay', command, 'DA_TRA_VE', 'TRA_VE_RL', f'{who} trả quyền điều khiển cho bộ điều khiển tự động.')
        lamp, fan, seconds = command.get('bong'), command.get('quat'), command.get('thoi_han_s')
        if action != 'dat' or any(isinstance(v, bool) for v in (lamp, fan, seconds)) or lamp not in MANUAL_LAMP or fan not in MANUAL_FAN or seconds not in MANUAL_SECONDS \
                or (lamp == 100 and fan == 100):
            return self._reply('tay', command, 'KHONG_HOP_LE')
        if self.source != 'truc_tiep' or not os.path.isdir('/proc'):
            return self._reply('tay', command, 'TU_CHOI: chỉ chỉnh tay được trên Raspberry Pi')
        if not any('ap_trung.py' in cmd for _, cmd in self.running()):
            return self._reply('tay', command, 'TU_CHOI: không có lượt ap_trung đang chạy (bắt đầu lượt trước)')
        until = time.time() + seconds
        self._write_manual({'bong': int(lamp), 'quat': int(fan), 'het_han': until, 'by': who, 'ts': command.get('ts')})
        command = dict(command, het_han_ms=int(until * 1000))
        return self._reply('tay', command, 'DA_AP_DUNG', 'CHINH_TAY',
                           f'{who} chỉnh tay: bóng {lamp} %, quạt {fan} % trong {seconds // 60} phút '
                           '(bảo vệ 38,3 / 38,8 °C vẫn hoạt động).')

    def _write_manual(self, data):
        temp = self.tay_path.with_suffix('.tmp')
        temp.write_text(json.dumps(dict(data, ghi_luc=time.time()), ensure_ascii=False), encoding='utf-8')
        os.replace(temp, self.tay_path)  # Ghi nguyên khối: ap_trung không bao giờ đọc file dở.

    # ---- thử nhiễu (đo khả năng phục hồi của bộ điều khiển)
    def _active_test(self):
        test = self.state.get('thu_nhieu')
        return test if test and test.get('trang_thai') in tn.ACTIVE else None

    def _track_disturbance(self, out):
        """Đưa điểm đo mới vào phép thử đang chạy. Trả phép thử cần gửi lên (đang chạy / vừa xong) hoặc None."""
        test = self.state.get('thu_nhieu')
        if not test or test.get('da_bao'):
            return None
        if test['trang_thai'] in tn.ACTIVE:
            for t, temp, in_band, cls in out.get('diem', []):
                tn.feed(test, t, temp, in_band, cls)
            if self.engine.s['ended'] and test['trang_thai'] in tn.ACTIVE:
                tn.cancel(test, 'lượt chạy kết thúc trước khi đo xong')
        if test['trang_thai'] not in tn.ACTIVE:
            kind = 'KET_QUA_THU_NHIEU'
            out['alerts'][f'{test["id"]}_{kind}'] = {
                'ts': now_ms() if test['trang_thai'] == 'HUY' else max(test['het_han_ts'], int((test['last_t'] or 0) * 1000)),
                'loai': kind,
                'muc': ALERT_LEVEL[kind], 'noi_dung': tn.summary_text(test), 'phien': test['phien'],
                'nhiet_c': test['nhiet_c']}
        return test

    def _log_disturbance(self, test):
        try:  # Lưu cả trên Pi để đưa vào báo cáo, kể cả khi mất Firebase.
            with self.thu_log_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(test, ensure_ascii=False) + '\n')
        except OSError as exc:
            log(f'Không ghi được {self.thu_log_path.name}: {exc}')
        log(tn.summary_text(test))

    def _manual_active(self):
        try:
            return float(json.loads(self.tay_path.read_text(encoding='utf-8')).get('het_han', 0)) > time.time()
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    def _handle_disturbance_command(self):
        command = self._take_command('thu_nhieu')
        if command is None:
            return
        who = str(command.get('by', '?'))[:100]
        action = command.get('hanh_dong')
        active = self._active_test()
        if action == 'huy':
            if active is None:
                return self._reply('thu_nhieu', command, 'KHONG_CO_THU_NHIEU')
            if active['trang_thai'] == 'DANG_NHIEU':
                self._write_manual({'bong': 0, 'quat': 100, 'het_han': 0, 'by': who})
            tn.cancel(active, f'{who} hủy')
            self._save_state()
            return self._reply('thu_nhieu', command, 'DA_HUY_THU')
        kind, seconds = command.get('kieu'), command.get('thoi_han_s')
        if action != 'bat_dau' or kind not in tn.KIEU or isinstance(seconds, bool) or seconds not in tn.THOI_HAN:
            return self._reply('thu_nhieu', command, 'KHONG_HOP_LE')
        reasons = []
        if self.source != 'truc_tiep' or not os.path.isdir('/proc'):
            reasons.append('chỉ chạy được trên Raspberry Pi')
        if not any('ap_trung.py' in cmd for _, cmd in self.running()):
            reasons.append('không có lượt ap_trung đang chạy')
        latest = self.engine.s['latest'] if self.engine else None
        if not latest or self.engine.s['ended'] or now_ms() - latest['ts'] > 30000:
            reasons.append('chưa có số đo mới của lượt đang chạy')
        elif latest['giai_doan'] != 'giu_nhiet':
            reasons.append(f'lượt chưa ở giai đoạn giữ nhiệt (đang: {latest["giai_doan_ten"]})')
        elif not latest['trong_vung']:
            reasons.append('nhiệt đang ngoài vùng mục tiêu, chờ ổn định rồi thử')
        if active is not None:
            reasons.append('đang có một phép thử nhiễu khác')
        if self._manual_active():
            reasons.append('đang chỉnh tay')
        if reasons:
            return self._reply('thu_nhieu', command, 'TU_CHOI: ' + '; '.join(reasons))
        lamp, fan = tn.KIEU[kind]
        now = time.time()
        self._write_manual({'bong': lamp, 'quat': fan, 'het_han': now + seconds, 'by': f'thử nhiễu ({who})',
                            'ts': command.get('ts')})
        test = tn.new_test(kind, seconds, now, who, latest['muc_tieu_c'], latest['vung_c'],
                           self.meta['bo_dieu_khien'], self.engine.session_id)
        self.state['thu_nhieu'] = test
        self._save_state()
        try:
            self.store.put(self._path('thu_nhieu', test['id']), test)
        except CloudError:
            pass  # chu kỳ sau gửi lại cùng số đo
        command = dict(command, thu_id=test['id'])
        return self._reply('thu_nhieu', command, 'DANG_THU_NHIEU', 'THU_NHIEU',
                           f'{who} bắt đầu thử nhiễu {tn.KIEU_TEN[kind]} trong {seconds // 60} phút; '
                           'sau đó đo thời gian bộ điều khiển kéo nhiệt về vùng.')

    # ---- sức khỏe thiết bị (chỉ đọc)
    def _publish_health(self):
        now = self.clock()
        if self.health_at is not None and now - self.health_at < HEALTH_EVERY_S:
            return
        self.health_at = now
        try:
            data = self.health_reader(self.base)
        except Exception as exc:  # noqa: BLE001 - đọc hệ thống lỗi không được làm hỏng bridge
            log(f'Không đọc được sức khỏe thiết bị: {type(exc).__name__}: {exc}')
            return
        s = self.engine.s if self.engine else {}
        n, bad = s.get('dem_do', 0), s.get('dem_loi_do', 0)
        data['ds18b20'] = ({'doc': n, 'loi': bad, 'ty_le_ok_pct': round(100 * (n - bad) / n, 1),
                            'phien': self.engine.session_id, 'dang_chay': not s.get('ended')} if n else None)
        bot = self.notifier
        data['telegram'] = {'bat': bot is not None,
                            'so_chat': len(getattr(bot, 'config', {}).get('chat_id', [])),
                            'lan_cuoi_ok_ts': getattr(bot, 'last_ok_ts', None),
                            'loi_cuoi': getattr(bot, 'last_error', None)}
        data.update(ts=now_ms(), bridge=VERSION, bridge_chay_s=int(now - self.started_at))
        try:
            self.store.put(self._path('suc_khoe'), data)
        except CloudError:
            self.health_at = None  # thử lại chu kỳ sau

    # ---- "RL đang nghĩ gì": ap_trung ghi nao_rl.json mỗi quyết định, bridge chuyển lên app
    def _publish_brain(self):
        try:
            data = json.loads(self.nao_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        ts = data.get('ts') if isinstance(data, dict) else None
        if not isinstance(ts, (int, float)) or ts == self.nao_ts or now_ms() - ts > NAO_FRESH_S * 1000:
            return
        try:
            self.store.put(self._path('nao_rl'), dict(data, bridge_ts=now_ms()))
            self.nao_ts = ts
        except CloudError:
            pass

    def _handle_run_command(self):
        command = self._take_command('luot')
        if command is None:
            return
        who = str(command.get('by', '?'))[:100]
        controller, minutes = command.get('bo_dieu_khien'), command.get('phut')
        if command.get('hanh_dong') != 'bat_dau' or controller not in ('rl', 'thermostat') or minutes not in RUN_MINUTES:
            return self._reply('luot', command, 'KHONG_HOP_LE')
        reasons = []
        if command.get('co_nguoi') is not True:
            reasons.append('chưa xác nhận có người ở cạnh hộp')
        if self.source != 'truc_tiep' or not os.path.isdir('/proc'):
            reasons.append('chỉ bật được trên Raspberry Pi')
        busy = self.running()
        if busy:
            reasons.append(f'đang có chương trình điều khiển chạy (PID {busy[0][0]})')
        try:
            me_ap.load(self.lich_path)
        except me_ap.LichError:
            reasons.append('chưa có mẻ ấp (tạo mẻ trước)')
        temp = self.box_temperature()
        if temp is None:
            reasons.append('không đọc được DS18B20')
        elif temp > START_MAX_C:
            reasons.append(f'hộp còn {temp:.1f} °C > {START_MAX_C:.0f} °C, chờ nguội')
        if reasons:
            return self._reply('luot', command, 'TU_CHOI: ' + '; '.join(reasons))
        from do_am import read_latest
        humidity_ok = read_latest(self.do_am_path)[2] == ''
        try:
            how = self.launcher(self.base, controller, minutes, humidity_ok)
        except Exception as exc:  # noqa: BLE001 - báo lỗi về app thay vì làm sập bridge
            return self._reply('luot', command, f'LOI_KHOI_DONG: {type(exc).__name__}: {exc}')
        name = 'Q-learning' if controller == 'rl' else 'Thermostat'
        return self._reply('luot', command, f'DA_BAT_DAU ({how})', 'BAT_DAU_LUOT',
                           f'{who} bắt đầu lượt {name} {minutes} phút từ app (hộp {temp:.1f} °C).')

    def _publish_humidity(self):
        """Độ ẩm từ do_am.py (dịch vụ hop-ap-do-am) → /do_am, cả khi không có lượt chạy. Chỉ giám sát."""
        try:
            data = json.loads(self.do_am_path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return  # Không chạy do_am.py: không ghi gì, app dùng độ ẩm trong lượt (nếu có).
        except (OSError, ValueError):
            return
        if not isinstance(data, dict) or not isinstance(data.get('ts'), (int, float)):
            return
        fresh = now_ms() - data['ts'] <= 30_000
        payload = {k: data.get(k) for k in ('do_am_pct', 'nhiet_dht_c', 'nhiet_ds18b20_c', 'ts', 'ts_doc_ok_cuoi',
                                            'lan_doc', 'lan_doc_ok', 'ty_le_ok_pct', 'loi_cuoi')}
        payload['con_cap_nhat'] = fresh
        sig = json.dumps([payload.get('do_am_pct'), payload.get('loi_cuoi'), fresh])
        now = self.clock()
        if sig == self.do_am_sig and now - self.do_am_put_at < 10:
            return
        try:
            self.store.put(self._path('do_am'), dict(payload, bridge_ts=now_ms()))
            self.do_am_sig, self.do_am_put_at = sig, now
        except CloudError:
            pass

    def _handle_day_command(self):
        try:
            command = self.store.get(self._path('commands', 'ngay_ap'))
        except CloudError:
            return
        if not isinstance(command, dict) or command.get('da_xu_ly') is True:
            return
        ts = command.get('ts')
        if not isinstance(ts, (int, float)) or ts <= self.state.get('ngay_handled_ts', 0):
            return
        day = command.get('ngay')
        requester = str(command.get('by', '?'))[:100]
        if now_ms() - ts > STOP_MAX_AGE_S * 1000:
            result = 'BO_QUA_LENH_CU'
        elif isinstance(day, bool) or not isinstance(day, (int, float)) or day != int(day) or not 1 <= day <= 21:
            result = 'KHONG_HOP_LE'
        else:
            day = int(day)
            if not self.state.get('me_chay') or not self.lich_path.exists():
                result = 'TU_CHOI: chỉ đổi ngày được khi mẻ ấp đang chạy'
            else:
                try:
                    me_ap.set_day(day, self.lich_path, nguon=f'app:{requester}')
                    result = 'DA_DOI'
                except me_ap.LichError as exc:
                    result = f'LOI: {exc}'[:120]
        self.state['ngay_handled_ts'] = ts
        self._save_state()
        reply = {'ngay': command.get('ngay'), 'ts': ts, 'by': self._pi_email(), 'yeu_cau_boi': requester,
                 'da_xu_ly': True, 'ket_qua': result, 'xu_ly_ts': now_ms()}
        try:
            self.store.put(self._path('commands', 'ngay_ap'), reply)
        except CloudError:
            pass
        if result == 'DA_DOI':
            info = me_ap.current(me_ap.load(self.lich_path))
            alert = {'ts': now_ms(), 'loai': 'DOI_NGAY', 'muc': 'thong_tin',
                     'noi_dung': f'{requester} đổi sang {me_ap.describe(info)}.',
                     'phien': self.engine.session_id if self.engine else None, 'nhiet_c': None}
            try:
                self._post_alerts({f'{alert["ts"]}_DOI_NGAY': alert})
            except CloudError:
                pass
            self.lich_sig = None  # Gửi lịch mới ngay chu kỳ này.
        log(f'LỆNH ĐỔI NGÀY {command.get("ngay")!r} từ {requester}: {result}')

    def _reset_stop(self, command, result):
        try:
            self.store.put(self._path('commands', 'stop'), {
                'value': False, 'ts': command.get('ts'), 'by': self.store.config.get('pi_email', 'pi')
                if hasattr(self.store, 'config') else 'pi', 'ket_qua': result, 'xu_ly_ts': now_ms()})
        except CloudError:
            pass

    def run(self, stop_event=None, until_finished=False):
        log(f'Cloud bridge {VERSION} chạy; chu kỳ {self.period:g} s. Ctrl+C để dừng bridge '
            '(không ảnh hưởng chương trình điều khiển).')
        while stop_event is None or not stop_event.is_set():
            started = self.clock()
            try:
                self.cycle()
            except Exception as exc:  # Bridge không bao giờ được làm sập chỉ vì một chu kỳ lỗi.
                log(f'Lỗi chu kỳ (bỏ qua): {type(exc).__name__}: {exc}')
            sid = self.engine.session_id if self.engine else None
            if until_finished and sid and self.state.get('summary_done_' + sid):
                return
            time.sleep(max(0.2, self.period - (self.clock() - started)))


# --------------------------------------------------------------------------- tải lượt cũ lên lịch sử

def upload_completed(store, csv_path, label=None, source='tai_len'):
    csv_path = Path(csv_path).resolve()
    if not is_control_csv(csv_path):
        raise SystemExit(f'{csv_path} không phải CSV của do_nhiet_hop.py')
    config = read_run_config(csv_path)
    target, lower, upper = band_for(config)
    sid = session_id_for(csv_path)
    engine = Engine(sid, lower, upper, alerts=False)
    rows, _ = CsvTail(csv_path).read_new()
    out = engine.feed(rows)
    summary = summarize_csv(csv_path, lower, upper, target)
    summary['bo_dieu_khien'] = describe_controller(config, label)
    summary['ket_qua_goc'] = original_result(csv_path)
    latest = engine.s['latest'] or {'ts': 0, 'elapsed_s': 0}
    meta = {'bo_dieu_khien': summary['bo_dieu_khien'], 'file': csv_path.name, 'thu_muc': csv_path.parent.name,
            'muc_tieu_c': target, 'vung_c': [lower, upper], 'nguon': source,
            'bat_dau_ts': latest['ts'] - int(latest['elapsed_s'] * 1000)}
    patch = {'meta': meta, 'summary': summary}
    patch.update({f'samples/{k}': v for k, v in out['samples'].items()})
    patch.update({f'events/{k}': v for k, v in out['events'].items()})
    store.patch(f'{DEVICE}/sessions/{sid}', patch)
    return sid, summary, len(out['samples'])


# --------------------------------------------------------------------------- phát lại một CSV như đang chạy thật

def replay_writer(source, target, speed, done):
    with Path(source).open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.reader(stream))
    header, body = rows[0], rows[1:]
    started = time.time()
    with Path(target).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        stream.flush()
        for values in body:
            elapsed = num(values[1]) or 0
            delay = started + elapsed / speed - time.time()
            if delay > 0:
                if done.wait(delay):
                    return
            values = list(values)
            # Mốc giờ = lúc dòng thực sự được ghi khi phát lại (nhanh hơn speed lần); elapsed_s giữ nguyên.
            values[0] = datetime.fromtimestamp(started + elapsed / speed, timezone.utc).isoformat(timespec='milliseconds')
            writer.writerow(values)
            stream.flush()


# --------------------------------------------------------------------------- dòng lệnh

def telegram_cli(command):
    import thong_bao_telegram as tg
    try:
        raw = json.loads(tg.FILE.read_text(encoding='utf-8'))
        config = tg.load_config(tg.FILE) if command == 'telegram-thu' else {
            'token': str(raw.get('token', '')).strip(), 'chat_id': [], 'muc': (), 'them': ()}
    except (OSError, ValueError) as exc:
        log(f'LỖI: đọc {tg.FILE.name}: {exc}')
        return 1
    bot = tg.TelegramNotifier(config, background=False, log=log)
    try:
        if command == 'telegram-chat-id':
            chats = bot.chat_ids()
            if not chats:
                log('Chưa thấy tin nhắn nào. Mở Telegram, nhắn /start cho bot (hoặc thêm bot vào nhóm) rồi chạy lại.')
            for chat_id, name in chats:
                log(f'chat_id {chat_id}  ({name})')
            return 0
        if not config['chat_id']:
            log('LỖI: chưa có chat_id trong file cấu hình.')
            return 1
        bot.send_text('🟢 Thử kết nối · Hộp ấp nhóm 13\nCloud bridge trên Pi gửi được tin Telegram.\n' + tg.APP_URL)
        log(f'Đã gửi tin thử tới {len(config["chat_id"])} cuộc trò chuyện.')
        return 0
    except tg.TelegramError as exc:
        log(f'LỖI Telegram: {exc}')
        return 1


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--cau-hinh', type=Path, help='firebase_bi_mat.json (mặc định: cạnh script hoặc thư mục cha)')
    common.add_argument('--ghi-file', type=Path, help='Ghi JSON cục bộ thay vì Firebase')
    sub = parser.add_subparsers(dest='lenh', required=True)
    p = sub.add_parser('chay', parents=[common], help='Theo dõi CSV mới nhất và đẩy lên đám mây')
    p.add_argument('--thu-muc', type=Path, default=here, help='Thư mục chứa ket_qua_*/ và logs/')
    p.add_argument('--csv', type=Path, help='Chỉ theo dõi đúng file này')
    p.add_argument('--chu-ky', type=float, default=5.0)
    p.add_argument('--lich', type=Path, default=me_ap.MAC_DINH, help='File lịch mẻ ấp (me_ap.py)')
    p = sub.add_parser('phat-lai', parents=[common], help='Phát lại CSV cũ như đang chạy thật (không GPIO)')
    p.add_argument('csv', type=Path)
    p.add_argument('--toc-do', type=float, default=10.0)
    p.add_argument('--chu-ky', type=float, default=2.0)
    p = sub.add_parser('tai-len', parents=[common], help='Đưa các lượt đã xong lên lịch sử')
    p.add_argument('csv', type=Path, nargs='+')
    p.add_argument('--bo-dieu-khien', help='Ghi đè nhãn bộ điều khiển')
    sub.add_parser('kiem-tra', parents=[common], help='Thử đăng nhập, ghi và đọc')
    sub.add_parser('telegram-chat-id', help='In chat_id của những ai vừa nhắn cho bot (cần telegram_bi_mat.json)')
    sub.add_parser('telegram-thu', help='Gửi một tin thử tới các chat_id trong telegram_bi_mat.json')
    args = parser.parse_args(argv)
    if args.lenh.startswith('telegram-'):
        return telegram_cli(args.lenh)
    store = make_store(args)

    if args.lenh == 'kiem-tra':
        try:
            if isinstance(store, FirebaseStore):
                store.login()
                log(f'Đăng nhập OK (UID khớp file: {store.uid == store.config.get("pi_uid")}).')
            store.put(f'{DEVICE}/trang_thai/bridge', {'ts': now_ms(), 'phien_ban': VERSION, 'may': socket.gethostname()})
            log('Ghi trang_thai/bridge OK.')
            log(f'Đọc commands/stop OK: {store.get(f"{DEVICE}/commands/stop")!r}')
        except CloudError as exc:
            log(f'LỖI: {exc}')
            return 1
        return 0

    if args.lenh == 'tai-len':
        for path in args.csv:
            sid, summary, n = upload_completed(store, path, args.bo_dieu_khien)
            log(f'Tải lên {sid}: {n} mẫu, {summary.get("bo_dieu_khien")}, MAE {summary.get("mae_c")} °C, '
                f'trong vùng {summary.get("trong_vung_pct")} %')
        return 0

    if args.lenh == 'phat-lai':
        if not is_control_csv(args.csv):
            raise SystemExit(f'{args.csv} không phải CSV của do_nhiet_hop.py')
        if args.toc_do <= 0:
            raise SystemExit('--toc-do phải > 0')
        stamp = datetime.now().strftime('%H%M%S')
        folder = here / '.cloud_bridge' / 'phat_lai' / f'phat_lai_{session_id_for(args.csv)}_{stamp}'
        folder.mkdir(parents=True)
        for name in ('cau_hinh.json',):
            if (args.csv.parent / name).exists():
                shutil.copy2(args.csv.parent / name, folder / name)
        done = threading.Event()
        writer = threading.Thread(target=replay_writer, args=(args.csv, folder / 'du_lieu.csv', args.toc_do, done),
                                  daemon=True)
        writer.start()
        time.sleep(0.5)
        bridge = Bridge(store, here, csv_path=folder / 'du_lieu.csv', period=args.chu_ky, source='phat_lai',
                        state_path=folder / 'trang_thai.json')
        original = original_result(args.csv)
        if original is not None:
            def copy_result():  # Giống thực tế: ket_qua.json xuất hiện sau END.
                writer.join()
                (folder / 'ket_qua.json').write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')
            threading.Thread(target=copy_result, daemon=True).start()
        try:
            bridge.run(until_finished=True)
        except KeyboardInterrupt:
            done.set()
        log('Phát lại xong.')
        return 0

    from thong_bao_telegram import make_notifier
    bridge = Bridge(store, args.thu_muc, csv_path=args.csv, period=args.chu_ky, lich_path=args.lich,
                    notifier=make_notifier(log=log))
    try:
        bridge.run()
    except KeyboardInterrupt:
        log('Đã dừng bridge. Chương trình điều khiển (nếu đang chạy) không bị ảnh hưởng.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
