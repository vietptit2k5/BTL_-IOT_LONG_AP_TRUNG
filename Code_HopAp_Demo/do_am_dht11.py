"""DHT11 on BCM17, isolated from the heater control loop."""
from __future__ import annotations

import math
import multiprocessing as mp
import queue
import time


def _read_loop(messages, stop):
    device = None
    try:
        from dht_reader import open_dht11
        device = open_dht11()  # Driver kernel nếu đã bật dtoverlay=dht11, không thì thư viện Adafruit.
        while not stop.is_set():
            try:
                value, _ = device.read()
                if value is None or not math.isfinite(value) or not 0 <= value <= 100:
                    raise RuntimeError('Invalid humidity sample')
                item = (float(value), time.monotonic(), '')
            except RuntimeError as exc:
                item = (None, time.monotonic(), str(exc))
            try:
                messages.put_nowait(item)
            except queue.Full:
                pass
            stop.wait(3.0)
    except Exception as exc:
        try:
            messages.put_nowait((None, time.monotonic(), str(exc)))
        except queue.Full:
            pass
    finally:
        if device is not None:
            device.exit()


class HumidityWorker:
    def __init__(self):
        ctx = mp.get_context('spawn')
        self.messages = ctx.Queue(maxsize=8)
        self.stop = ctx.Event()
        self.process = ctx.Process(target=_read_loop, args=(self.messages, self.stop), daemon=True)
        self.latest = (None, None, 'WAIT DHT11')

    def start(self):
        self.process.start()

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        while True:
            try:
                self.latest = self.messages.get_nowait()
            except queue.Empty:
                break
        value, at, error = self.latest
        age = None if at is None else max(0., now - at)
        if not self.process.is_alive():
            return None, age, error or 'DHT11 STOPPED'
        if age is not None and age > 10:
            return None, age, 'DHT11 STALE'
        return value, age, error

    def close(self):
        self.stop.set()
        if self.process.pid is not None:
            self.process.join(timeout=.2)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=.2)
        self.messages.close()


class FileHumiditySource:
    """Cùng giao diện HumidityWorker, nhưng đọc do_am_moi_nhat.json do do_am.py ghi: KHÔNG mở GPIO17.

    Dùng khi do_am.py đang chạy (dịch vụ hop-ap-do-am) để chương trình điều khiển và do_am.py không tranh chân.
    """

    def __init__(self, path):
        self.path = path

    def start(self):
        pass

    def snapshot(self, now=None):
        from do_am import read_latest  # Nhập muộn: do_am kéo theo kiem_tra_dht11, chỉ cần khi dùng nguồn file.
        return read_latest(self.path)

    def close(self):
        pass
