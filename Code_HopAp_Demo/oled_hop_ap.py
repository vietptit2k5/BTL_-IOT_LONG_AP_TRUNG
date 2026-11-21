#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OLED SSD1306 I2C cho phép đo hộp. I/O màn hình chỉ chạy ở luồng riêng.

Thử riêng màn hình, không đọc DS18B20/không điều khiển tải:
    python3 oled_hop_ap.py --giay 10
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import queue
import sys
import threading
import time


@dataclass(frozen=True)
class OLEDFrame:
    temperature: float | None
    sample_at: float | None
    lamp: float | None
    fan: float | None
    mode: str
    elapsed: float
    status: str
    created_at: float
    humidity: float | None = None
    humidity_at: float | None = None
    humidity_enabled: bool = False


def address_arg(text):
    try:
        address = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Địa chỉ OLED cần là 0x3c hoặc 0x3d.') from exc
    if address not in (0x3C, 0x3D):
        raise argparse.ArgumentTypeError('Chỉ chọn 0x3c hoặc 0x3d cho OLED này.')
    return address


def frame_lines(frame, now, stale_after=3.0):
    stale = frame.sample_at is not None and now - frame.sample_at >= stale_after
    valid = frame.temperature is not None and math.isfinite(frame.temperature) and not stale
    temperature = f'T {frame.temperature:.2f} C' if valid else 'T --.-- C'
    def duty(value):
        return '--' if value is None else f'{value:.1f}'.rstrip('0').rstrip('.') + '%'
    controls = f'H:{duty(frame.lamp)} F:{duty(frame.fan)}'
    elapsed = max(0, frame.elapsed + now - frame.created_at)
    mode = {'doc': 'READ', 'giu': 'FIXED', 'tay': 'MANUAL', 'kich-ban': 'SEQUENCE', 'khao-sat': 'AUTO'}.get(frame.mode, 'TEST')
    status = frame.status
    if stale and status in ('RUN', 'READ ONLY', 'FAN START', 'FAN POSTRUN', 'WARMUP', 'SOFT GUARD'):
        status = 'SENSOR STALE'
    info = f'{mode} {elapsed:.0f}s'
    if frame.humidity_enabled:
        fresh = frame.humidity_at is not None and now - frame.humidity_at <= 10
        info = (f'RH {frame.humidity:.0f} %' if fresh and frame.humidity is not None
                and math.isfinite(frame.humidity) else 'RH -- % (DHT ERR)')
    return temperature, controls, info, status


class LumaBackend:
    """Chỉ được tạo/gọi từ luồng OLED, không chạy trên vòng điều khiển nhiệt."""

    def __init__(self, address=None, height=64):
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import ssd1306
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise RuntimeError('Cài trên Pi: sudo apt install python3-luma.oled i2c-tools') from exc
        self.Image, self.ImageDraw = Image, ImageDraw
        self.device = None
        failures = []
        for candidate in ((address,) if address is not None else (0x3C, 0x3D)):
            serial = None
            try:
                serial = i2c(port=1, address=candidate)
                self.device = ssd1306(serial, width=128, height=height)
                self.address = candidate
                break
            except Exception as exc:
                failures.append(f'0x{candidate:02x}: {exc}')
                if serial is not None:
                    try:
                        serial.cleanup()
                    except Exception:
                        pass
        if self.device is None:
            raise RuntimeError('Không mở được SSD1306 trên I2C-1. ' + '; '.join(failures))
        self.small = ImageFont.load_default()
        self.big = self.small
        try:
            font = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
            self.small = ImageFont.truetype(font, 10)
            self.big = ImageFont.truetype(font, 18)
        except OSError:
            pass

    def draw(self, lines):
        image = self.Image.new('1', self.device.size, 0)
        draw = self.ImageDraw.Draw(image)
        if self.device.height == 32:
            rows = ((lines[0], 0, self.small), (lines[1], 11, self.small),
                    (lines[2] if lines[2].startswith('RH ') and lines[3] in ('RUN', 'READ ONLY') else lines[3], 22, self.small))
        else:
            rows = ((lines[0], 0, self.big), (lines[1], 24, self.small),
                    (lines[2], 38, self.small), (lines[3], 52, self.small))
        for text, top, font in rows:
            # Căn theo mép glyph và cắt chữ nếu font dự phòng rộng hơn dự kiến.
            while text and draw.textbbox((0, 0), text, font=font)[2] > self.device.width:
                text = text[:-1]
            if text:
                box = draw.textbbox((0, 0), text, font=font)
                draw.text((-box[0], top - box[1]), text, font=font, fill=255)
        self.device.display(image)

    def close(self):
        if self.device is not None:
            self.device.cleanup()


class OLEDDisplay:
    """Nhận ảnh trạng thái mới nhất; update/close không đợi giao dịch I2C."""

    def __init__(self, enabled=True, address=None, height=64, backend_factory=None, warn=None):
        self.enabled = enabled
        self.address, self.height = address, height
        self.backend_factory = backend_factory or LumaBackend
        self.warn = warn or self._warn
        self.frames = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.failed = threading.Event()
        self.error = ''
        self.thread = None

    @staticmethod
    def _warn(message):
        try:
            print(f'OLED: {message}. Tiếp tục Terminal/CSV.', file=sys.stderr, flush=True)
        except Exception:
            pass

    def start(self):
        if self.enabled and self.thread is None:
            self.thread = threading.Thread(target=self._run, args=(), daemon=True)
            self.thread.start()

    def update(self, frame):
        if not self.enabled or self.failed.is_set() or self.stop.is_set():
            return
        try:
            self.frames.put_nowait(frame)
        except queue.Full:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
            try:
                self.frames.put_nowait(frame)
            except queue.Full:
                pass

    def _run(self):
        backend = None
        current = None
        drawn_at = -math.inf
        try:
            backend = self.backend_factory(address=self.address, height=self.height)
            while not self.stop.is_set():
                changed = False
                try:
                    current = self.frames.get(timeout=0.2)
                    changed = True
                except queue.Empty:
                    pass
                now = time.monotonic()
                if current is not None and (changed or now - drawn_at >= 1):
                    backend.draw(frame_lines(current, now))
                    drawn_at = now
                    self.ready.set()
        except Exception as exc:
            self.error = str(exc)
            self.failed.set()
            self.warn(self.error)
        finally:
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    pass

    def close(self):
        self.stop.set()
        if self.thread is not None and self.thread.ident is not None:
            # I2C treo không được giữ chương trình lại trước/sau khi tắt tải.
            self.thread.join(timeout=0.2)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dia-chi', type=address_arg, default=None)
    parser.add_argument('--cao', type=int, choices=(32, 64), default=64)
    parser.add_argument('--giay', type=float, default=10)
    args = parser.parse_args(argv)
    if not math.isfinite(args.giay) or not 1 <= args.giay <= 30:
        parser.error('--giay phải từ 1 đến 30.')
    display = OLEDDisplay(
        address=args.dia_chi, height=args.cao,
        warn=lambda message: print(f'OLED: {message}', file=sys.stderr, flush=True),
    )
    now = time.monotonic()
    display.update(OLEDFrame(None, None, None, None, 'test', 0, 'OLED TEST', now))
    display.start()
    try:
        end = time.monotonic() + 3
        while not display.ready.is_set():
            if display.failed.is_set() or time.monotonic() >= end:
                print('Chưa xác nhận được OLED. Kiểm tra I2C, thư viện và dây.', file=sys.stderr)
                return 1
            time.sleep(0.05)
        print('Đã gửi khung OLED TEST. Kiểm tra màn hình thật; T --.-- là chưa có số đo.', flush=True)
        time.sleep(args.giay)
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        display.close()


if __name__ == '__main__':
    raise SystemExit(main())
