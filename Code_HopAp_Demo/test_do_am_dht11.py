"""Verify humidity freshness and errors without accessing Raspberry Pi."""
import queue
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import do_nhiet_hop as core
from test_do_nhiet_hop import Clock, FakeWorker, FakeOutputs
from do_am_dht11 import HumidityWorker
from oled_hop_ap import OLEDFrame, frame_lines


class HumidityTests(unittest.TestCase):
    def test_end_row_written_before_humidity_queue_is_closed(self):
        clock = Clock()
        class Worker:
            closed = False
            def start(self): pass
            def snapshot(self, now):
                if self.closed:
                    raise ValueError('Queue closed')
                return 55., 0., ''
            def close(self): self.closed = True
        humidity = Worker()
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)/'data.csv'
            with patch.object(core.time, 'monotonic', clock.monotonic),patch.object(core.time, 'sleep', clock.sleep), \
                 patch.object(core,'find_sensor',return_value=Path('/fake/28-test/w1_slave')), \
                 patch.object(core,'Outputs',FakeOutputs), \
                 patch.object(core,'SensorWorker',side_effect=lambda path:FakeWorker(path,clock,'stable')), \
                 patch('do_am_dht11.HumidityWorker',return_value=humidity), \
                 contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                code = core.main(['doc','--giay','2','--dht11','--khong-oled','--csv',str(log)])
            self.assertEqual(code,0)
            self.assertIn('END',log.read_text(encoding='utf-8-sig'))
            self.assertTrue(humidity.closed)

    def worker(self):
        worker = HumidityWorker.__new__(HumidityWorker)
        worker.messages = queue.Queue()
        worker.process = SimpleNamespace(is_alive=lambda: True)
        worker.latest = (None, None, 'WAIT DHT11')
        return worker

    def test_missing_valid_error_and_stale(self):
        w = self.worker()
        self.assertIsNone(w.snapshot(100)[0])
        w.messages.put((65., 100., ''))
        self.assertEqual(w.snapshot(101), (65., 1., ''))
        self.assertEqual(w.snapshot(111), (None, 11., 'DHT11 STALE'))
        w.messages.put((None, 112., 'checksum'))
        self.assertEqual(w.snapshot(112), (None, 0., 'checksum'))
        w.process.is_alive = lambda: False
        self.assertIsNone(w.snapshot(112)[0])

    def test_oled_humidity_keeps_thermal_fault_visible(self):
        frame = OLEDFrame(39., 100., 0., 100., 'giu', 10., 'OVER TEMP',
                          100., 65., 100., True)
        self.assertEqual(frame_lines(frame, 100)[2:], ('RH 65 %', 'OVER TEMP'))
        self.assertIn('--', frame_lines(frame, 111)[2])


if __name__ == '__main__':
    unittest.main()
