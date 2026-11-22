#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gửi cảnh báo của hộp ấp tới Telegram (bot riêng của nhóm), kể cả khi không ai mở app.

Cấu hình: telegram_bi_mat.json cạnh code (KHÔNG đẩy lên git):
    {"token": "123456789:AA...", "chat_id": [123456789]}
Tùy chọn: "muc": ["canh_bao", "nguy_hiem"] (mức được gửi), "them": ["KET_THUC", "KET_QUA_THU_NHIEU"]
(loại thông tin vẫn gửi dù mức thấp).

Thử trên Pi:
    python3 cloud_bridge.py telegram-chat-id    # nhắn /start cho bot trước, lệnh này in chat_id
    python3 cloud_bridge.py telegram-thu        # gửi một tin thử

Gửi bằng HTTPS tới Bot API của Telegram, trong luồng nền: mạng chậm không làm trễ vòng 5 s của bridge.
Token không bao giờ được ghi ra log (thông báo lỗi của requests có chứa URL, nên được che lại).
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import time

API = 'https://api.telegram.org/bot{token}/{method}'
FILE = Path(__file__).with_name('telegram_bi_mat.json')
APP_URL = 'https://hop-ap-nhom13.web.app'
LEVEL_ICON = {'nguy_hiem': '🔴', 'canh_bao': '🟠', 'thong_tin': '🟢'}
LEVEL_NAME = {'nguy_hiem': 'NGUY HIỂM', 'canh_bao': 'Cảnh báo', 'thong_tin': 'Thông tin'}
DEFAULT_LEVELS = ('canh_bao', 'nguy_hiem')
DEFAULT_EXTRA = ('KET_THUC', 'KET_QUA_THU_NHIEU')
MAX_AGE_S = 900        # Cảnh báo gửi bù sau khi mất mạng quá 15 phút thì không nhắn nữa (đã cũ).
RETRIES = 3


class TelegramError(RuntimeError):
    pass


def load_config(path=FILE):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    token = str(data.get('token', '')).strip()
    if ':' not in token:
        raise ValueError('token không đúng dạng 123456789:AA... (lấy từ @BotFather)')
    chats = data.get('chat_id')
    chats = chats if isinstance(chats, list) else [chats]
    chats = [c for c in chats if c not in (None, '')]
    return {'token': token, 'chat_id': chats, 'muc': tuple(data.get('muc', DEFAULT_LEVELS)),
            'them': tuple(data.get('them', DEFAULT_EXTRA))}


def format_alert(alert, device='Hộp ấp nhóm 13'):
    level = alert.get('muc', 'canh_bao')
    lines = [f'{LEVEL_ICON.get(level, "⚪")} {LEVEL_NAME.get(level, level)} · {device}',
             str(alert.get('noi_dung') or alert.get('loai') or '')]
    meta = []
    if isinstance(alert.get('ts'), (int, float)):
        meta.append(datetime.fromtimestamp(alert['ts'] / 1000).strftime('%H:%M:%S %d/%m'))
    if isinstance(alert.get('nhiet_c'), (int, float)):
        meta.append(f'{alert["nhiet_c"]:.2f} °C'.replace('.', ','))
    if meta:
        lines.append(' · '.join(meta))
    lines.append(APP_URL)
    return '\n'.join(lines)


class TelegramNotifier:
    def __init__(self, config, session=None, clock=time.time, background=True, timeout=10, log=print, sleep=time.sleep):
        if session is None:
            import requests
            session = requests.Session()
        self.config, self.http, self.clock, self.timeout = config, session, clock, timeout
        self.log, self.sleep, self.background = log, sleep, background
        self.sent = deque(maxlen=500)
        self.last_ok_ts, self.last_error = None, None  # cho thẻ sức khỏe thiết bị trên app
        self.queue = queue.Queue(maxsize=50)
        if background:
            threading.Thread(target=self._worker, name='telegram', daemon=True).start()

    # ---- chọn cảnh báo
    def wants(self, alert):
        return alert.get('muc') in self.config['muc'] or alert.get('loai') in self.config['them']

    def offer(self, key, alert):
        """Nhận một cảnh báo vừa ghi lên Firebase; gửi nếu đúng mức, chưa gửi và chưa quá cũ."""
        if key in self.sent or not self.wants(alert):
            return False
        ts = alert.get('ts')
        if isinstance(ts, (int, float)) and self.clock() - ts / 1000 > MAX_AGE_S:
            return False
        self.sent.append(key)
        text = format_alert(alert)
        if not self.background:
            self._deliver(text)
            return True
        try:
            self.queue.put_nowait(text)
        except queue.Full:
            self.log('Telegram: hàng đợi đầy, bỏ một tin.')
            return False
        return True

    # ---- gửi
    def send_text(self, text):
        for chat in self.config['chat_id']:
            self._call('sendMessage', {'chat_id': chat, 'text': text, 'disable_web_page_preview': True})

    def chat_ids(self):
        """Các cuộc trò chuyện đã nhắn cho bot gần đây: [(chat_id, tên)]."""
        seen = {}
        for update in self._call('getUpdates', {}) or []:
            msg = update.get('message') or update.get('channel_post') or {}
            chat = msg.get('chat') or {}
            if 'id' in chat:
                seen[chat['id']] = chat.get('title') or ' '.join(
                    x for x in (chat.get('first_name'), chat.get('last_name')) if x) or chat.get('username') or '?'
        return list(seen.items())

    def _call(self, method, payload):
        url = API.format(token=self.config['token'], method=method)
        try:
            response = self.http.post(url, json=payload, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 - lỗi mạng: che token trước khi báo
            raise TelegramError(self._hide(f'{type(exc).__name__}: {exc}')) from None
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200 or not data.get('ok'):
            raise TelegramError(f'{method}: HTTP {response.status_code} {data.get("description", "")}'.strip())
        return data.get('result')

    def _hide(self, text):
        return text.replace(self.config['token'], '<token>')

    def _deliver(self, text):
        for attempt in range(RETRIES):
            try:
                self.send_text(text)
                self.last_ok_ts, self.last_error = int(time.time() * 1000), None
                return True
            except TelegramError as exc:
                self.last_error = str(exc)[:200]
                self.log(f'Telegram: gửi lỗi (lần {attempt + 1}/{RETRIES}): {exc}')
                if attempt + 1 < RETRIES:
                    self.sleep(5 * (attempt + 1))
        return False

    def _worker(self):
        while True:
            self._deliver(self.queue.get())


def make_notifier(path=FILE, log=print):
    """Bridge gọi khi khởi động: có file cấu hình thì bật, không có thì tắt lặng lẽ (chỉ ghi log 1 lần)."""
    if not Path(path).exists():
        log(f'Telegram: chưa có {Path(path).name}, không gửi cảnh báo qua Telegram.')
        return None
    try:
        config = load_config(path)
    except (OSError, ValueError) as exc:
        log(f'Telegram: cấu hình lỗi ({exc}); không gửi.')
        return None
    if not config['chat_id']:
        log('Telegram: chưa có chat_id; chạy "python3 cloud_bridge.py telegram-chat-id" để lấy.')
        return None
    log(f'Telegram: bật, gửi tới {len(config["chat_id"])} cuộc trò chuyện.')
    return TelegramNotifier(config, log=log)
