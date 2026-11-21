"""Kiểm thử do_am.py, nguồn độ ẩm qua file và việc bridge đưa độ ẩm lên app (không cần Pi/mạng)."""
import json
from pathlib import Path
import tempfile
import unittest

import cloud_bridge as cb
import do_am
from do_am_dht11 import FileHumiditySource

T0 = 1_800_000_000.0


class TestDoAm(unittest.TestCase):
    def test_median_filter_ignores_one_bad_jump(self):
        s = do_am.DoAm()
        for rh in (58, 59, 90):        # 90: một lần đọc nhảy
            s.add(rh, 30, None, T0)
        self.assertEqual(s.record(T0)['do_am_pct'], 59)
        s.add(None, None, 'Checksum did not validate', T0 + 3)
        rec = s.record(T0 + 3)
        self.assertEqual((rec['lan_doc'], rec['lan_doc_ok'], rec['ty_le_ok_pct']), (4, 3, 75.0))
        self.assertIn('Checksum', rec['loi_cuoi'])
        self.assertEqual(rec['do_am_pct'], 59)  # vẫn còn số tốt gần đây

    def test_value_expires_after_30s_without_good_read(self):
        s = do_am.DoAm()
        s.add(58, 30, None, T0)
        for i in range(1, 12):
            s.add(None, None, 'DHT sensor not found, check wiring', T0 + 3 * i)
        self.assertIsNone(s.record(T0 + 33)['do_am_pct'])

    def test_rejects_out_of_range(self):
        s = do_am.DoAm()
        s.add(150, 30, None, T0)
        self.assertEqual(s.ok, 0)
        self.assertIsNone(s.record(T0)['do_am_pct'])

    def test_read_latest_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'do_am.json'
            self.assertEqual(do_am.read_latest(path, T0)[2], 'Chưa chạy do_am.py')
            s = do_am.DoAm()
            s.add(57, 30, None, T0)
            do_am.write_atomic(path, s.record(T0))
            rh, age, err = do_am.read_latest(path, T0 + 2)
            self.assertEqual((rh, err), (57.0, ''))
            self.assertAlmostEqual(age, 2.0)
            self.assertEqual(do_am.read_latest(path, T0 + 60)[2], 'do_am.py không còn cập nhật')
            path.write_text('{hỏng', encoding='utf-8')
            self.assertEqual(do_am.read_latest(path, T0)[0], None)

    def test_file_source_has_humidity_worker_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'do_am.json'
            src = FileHumiditySource(path)
            src.start()
            self.assertEqual(src.snapshot()[0], None)
            s = do_am.DoAm()
            import time
            s.add(61, 30, None, time.time())
            do_am.write_atomic(path, s.record(time.time()))
            self.assertEqual(src.snapshot()[0], 61.0)
            src.close()

    def test_format_line(self):
        s = do_am.DoAm()
        s.add(None, None, 'DHT sensor not found, check wiring', T0)
        line = do_am.format_line(s.record(T0), 'not_found')
        self.assertIn('RH = -- %', line)
        self.assertIn('Không có tín hiệu', line)


class TestBridgeHumidity(unittest.TestCase):
    def test_publish_fresh_stale_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = cb.FileStore(base / 'db')
            path = base / 'do_am.json'
            bridge = cb.Bridge(store, base, state_path=base / 's.json', lich_path=base / 'lich.json', do_am_path=path)
            bridge.cycle()
            self.assertIsNone(store.get('hop_ap_01/do_am'))  # chưa chạy do_am.py: không ghi gì
            now = cb.now_ms() / 1000
            s = do_am.DoAm()
            s.add(58, 31, None, now)
            do_am.write_atomic(path, s.record(now))
            bridge.cycle()
            data = store.get('hop_ap_01/do_am')
            self.assertEqual((data['do_am_pct'], data['con_cap_nhat']), (58.0, True))
            old = s.record(now - 120)
            do_am.write_atomic(path, old)
            bridge.do_am_put_at = 0
            bridge.cycle()
            self.assertFalse(store.get('hop_ap_01/do_am')['con_cap_nhat'])

    def test_replay_does_not_publish_humidity(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = cb.FileStore(base / 'db')
            path = base / 'do_am.json'
            s = do_am.DoAm()
            s.add(58, 31, None, cb.now_ms() / 1000)
            do_am.write_atomic(path, s.record(cb.now_ms() / 1000))
            bridge = cb.Bridge(store, base, state_path=base / 's.json', source='phat_lai', do_am_path=path)
            bridge.cycle()
            self.assertIsNone(store.get('hop_ap_01/do_am'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
