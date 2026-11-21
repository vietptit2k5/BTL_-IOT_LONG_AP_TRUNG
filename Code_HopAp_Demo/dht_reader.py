"""Đọc DHT11 ở GPIO17 bằng một trong hai cách, dùng chung cho do_am.py, kiem_tra_dht11.py, do_am_dht11.py.

1. **Driver kernel** (khuyên dùng trên Raspberry Pi OS mới): thêm `dtoverlay=dht11,gpiopin=17` vào
   /boot/firmware/config.txt rồi khởi động lại. Kernel tự canh thời gian và đưa số đo ra
   /sys/bus/iio/devices/iio:deviceN/{in_humidityrelative_input, in_temp_input} (đơn vị phần nghìn).
2. **Thư viện adafruit-circuitpython-dht** (đọc bằng cách canh thời gian trong Python): dễ báo
   "DHT sensor not found" dù dây đúng, nhất là trên Raspberry Pi OS Bookworm.

open_dht11() tự chọn driver kernel nếu đã bật, nếu không thì dùng thư viện. Mọi lỗi đọc đều ném RuntimeError
với thông điệp mà kiem_tra_dht11.classify_error hiểu được.
"""
from __future__ import annotations

import errno
from pathlib import Path

IIO_ROOT = Path('/sys/bus/iio/devices')
OVERLAY_LINE = 'dtoverlay=dht11,gpiopin=17'


def find_kernel_dht11(root: Path = IIO_ROOT):
    """Thư mục IIO của driver dht11, hoặc None nếu chưa bật overlay."""
    try:
        devices = sorted(p for p in Path(root).iterdir() if p.name.startswith('iio'))  # iio:device0, iio:device1…
    except OSError:
        return None
    for dev in devices:
        try:
            if (dev / 'name').read_text().strip().startswith('dht11'):
                return dev
        except OSError:
            continue
    return None


class KernelDHT:
    kind = 'kernel'

    def __init__(self, device_dir: Path):
        self.dir = Path(device_dir)

    def _value(self, name):
        try:
            return int((self.dir / name).read_text().strip()) / 1000
        except OSError as exc:
            if exc.errno in (errno.ETIMEDOUT, errno.ENODEV):
                raise RuntimeError(f'DHT sensor not found, check wiring (kernel dht11: {exc.strerror})') from exc
            if exc.errno == errno.EIO:
                raise RuntimeError(f'Checksum did not validate (kernel dht11: {exc.strerror})') from exc
            raise RuntimeError(f'Kernel dht11 lỗi đọc: {exc}') from exc
        except ValueError as exc:
            raise RuntimeError(f'Kernel dht11 trả giá trị lạ: {exc}') from exc

    def read(self):
        # Driver giữ số đo khoảng 2 s: đọc nhiệt rồi ẩm ngay sau đó chỉ kích một lần đo.
        temperature = self._value('in_temp_input')
        humidity = self._value('in_humidityrelative_input')
        return humidity, temperature

    def exit(self):
        pass


class BlinkaDHT:
    kind = 'thu_vien'

    def __init__(self):
        import board
        import adafruit_dht
        self.device = adafruit_dht.DHT11(board.D17, use_pulseio=False)

    def read(self):
        return self.device.humidity, self.device.temperature

    def exit(self):
        self.device.exit()


def open_dht11(prefer: str = 'auto', root: Path = IIO_ROOT):
    """prefer: 'auto' | 'kernel' | 'thu_vien'. Ném RuntimeError/ImportError nếu không mở được."""
    device_dir = find_kernel_dht11(root)
    if prefer in ('auto', 'kernel') and device_dir is not None:
        return KernelDHT(device_dir)
    if prefer == 'kernel':
        raise RuntimeError(f'Chưa bật driver kernel: thêm "{OVERLAY_LINE}" vào /boot/firmware/config.txt rồi sudo reboot')
    return BlinkaDHT()
