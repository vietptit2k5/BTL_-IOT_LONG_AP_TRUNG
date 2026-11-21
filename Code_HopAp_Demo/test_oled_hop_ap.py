"""OLED giả: kiểm tra hiển thị và I2C lỗi/treo không chặn vòng điều khiển."""
import argparse
import threading
import time
import types
import unittest
from unittest.mock import patch

import oled_hop_ap as oled


def make_frame(**changes):
    now = time.monotonic()
    fields = dict(temperature=37.5, sample_at=now, lamp=35, fan=75,
                  mode='tay', elapsed=12, status='RUN', created_at=now)
    fields.update(changes)
    return oled.OLEDFrame(**fields)


class FrameTests(unittest.TestCase):
    def test_temperature_commands_and_mode(self):
        frame = make_frame()
        lines = oled.frame_lines(frame, frame.created_at)
        self.assertEqual(lines, ('T 37.50 C', 'H:35% F:75%', 'MANUAL 12s', 'RUN'))

    def test_read_only_and_missing_sensor_do_not_show_fake_values(self):
        frame = make_frame(temperature=None, sample_at=None, lamp=None, fan=None,
                           mode='doc', status='WAIT SENSOR')
        lines = oled.frame_lines(frame, frame.created_at)
        self.assertEqual(lines[0], 'T --.-- C')
        self.assertEqual(lines[1], 'H:-- F:--')
        self.assertEqual(lines[3], 'WAIT SENSOR')

    def test_stale_reading_is_hidden_and_fault_status_is_preserved(self):
        frame = make_frame()
        lines = oled.frame_lines(frame, frame.created_at + 3)
        self.assertEqual(lines[0], 'T --.-- C')
        self.assertEqual(lines[3], 'SENSOR STALE')
        frame = make_frame(status='OVER TEMP')
        self.assertEqual(oled.frame_lines(frame, frame.created_at + 4)[3], 'OVER TEMP')

    def test_address_validation(self):
        self.assertEqual(oled.address_arg('0x3d'), 0x3D)
        for value in ('0x3f', 'xyz', '-1'):
            with self.assertRaises(argparse.ArgumentTypeError):
                oled.address_arg(value)


class WorkerTests(unittest.TestCase):
    def test_disabled_display_never_initializes_backend(self):
        with patch.object(oled, 'LumaBackend') as backend:
            display = oled.OLEDDisplay(enabled=False)
            display.start()
            display.update(make_frame())
            display.close()
            backend.assert_not_called()
        self.assertIsNone(display.thread)

    def test_worker_draws_and_closes_backend(self):
        closed = threading.Event()
        rendered = []
        class Backend:
            def __init__(self, address, height):
                self.address, self.height = address, height
            def draw(self, lines):
                rendered.append(lines)
            def close(self):
                closed.set()
        display = oled.OLEDDisplay(backend_factory=Backend)
        display.update(make_frame())
        display.start()
        try:
            self.assertTrue(display.ready.wait(1))
            self.assertEqual(rendered[0][0], 'T 37.50 C')
        finally:
            display.close()
        self.assertTrue(closed.wait(1))

    def test_missing_library_or_device_is_reported_once(self):
        warnings = []
        def fail(**kwargs):
            raise RuntimeError('I2C not available')
        display = oled.OLEDDisplay(backend_factory=fail, warn=warnings.append)
        display.start()
        self.assertTrue(display.failed.wait(1))
        display.update(make_frame())
        display.close()
        self.assertEqual(warnings, ['I2C not available'])

    def test_i2c_hang_does_not_block_updates_or_close(self):
        drawing = threading.Event()
        release = threading.Event()
        closed = threading.Event()
        class Backend:
            def __init__(self, **kwargs):
                pass
            def draw(self, lines):
                drawing.set()
                release.wait(3)
            def close(self):
                closed.set()
        display = oled.OLEDDisplay(backend_factory=Backend)
        display.update(make_frame())
        display.start()
        try:
            self.assertTrue(drawing.wait(1))
            began = time.monotonic()
            for _ in range(100):
                display.update(make_frame(lamp=0, status='SENSOR ERROR'))
            self.assertLess(time.monotonic() - began, .2)
            began = time.monotonic()
            display.close()
            self.assertLess(time.monotonic() - began, .6)
            self.assertLessEqual(display.frames.qsize(), 1)
        finally:
            release.set()
        self.assertTrue(closed.wait(1))


class BackendTests(unittest.TestCase):
    def test_auto_address_and_frame_fit_with_fake_luma_and_pillow(self):
        serials = []
        devices = []
        texts = []
        class Serial:
            def __init__(self, port, address):
                self.address = address
                self.closed = False
                serials.append(self)
            def cleanup(self):
                self.closed = True
        class Device:
            def __init__(self, serial, width, height):
                if serial.address == 0x3C:
                    raise OSError('no device at 0x3c')
                self.width, self.height, self.size = width, height, (width, height)
                self.serial = serial
                devices.append(self)
            def display(self, image):
                self.image = image
            def cleanup(self):
                self.serial.cleanup()
        class Draw:
            def textbbox(self, xy, text, font):
                return (0, 2, len(text) * 6, 12)
            def text(self, xy, text, font, fill):
                texts.append((xy, text))
        def unavailable_font(*args):
            raise OSError('no external font')
        modules = {}
        for name in ('luma', 'luma.core', 'luma.core.interface', 'luma.core.interface.serial',
                     'luma.oled', 'luma.oled.device', 'PIL'):
            modules[name] = types.ModuleType(name)
        modules['luma.core.interface.serial'].i2c = Serial
        modules['luma.oled.device'].ssd1306 = Device
        modules['PIL'].Image = types.SimpleNamespace(new=lambda mode, size, fill: (mode, size, fill))
        modules['PIL'].ImageDraw = types.SimpleNamespace(Draw=lambda image: Draw())
        modules['PIL'].ImageFont = types.SimpleNamespace(load_default=lambda: 'font', truetype=unavailable_font)
        with patch.dict('sys.modules', modules):
            for height in (64, 32):
                texts.clear()
                backend = oled.LumaBackend(height=height)
                self.assertEqual(backend.address, 0x3D)
                self.assertTrue(serials[-2].closed)
                backend.draw(('T 37.50 C', 'H:35% F:75%', 'MANUAL 12s', 'X' * 50))
                for (x, y), text in texts:
                    self.assertLessEqual(len(text) * 6, 128)
                    self.assertGreaterEqual(y + 2, 0)
                    self.assertLessEqual(y + 12, height)
                backend.close()
                self.assertTrue(serials[-1].closed)


if __name__ == '__main__':
    unittest.main()
