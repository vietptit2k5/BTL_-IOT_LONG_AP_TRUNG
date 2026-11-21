"""Kiểm thử phần phân loại lỗi và kết luận của kiem_tra_dht11.py (không cần Pi)."""
import tempfile
from pathlib import Path
import unittest

import kiem_tra_dht11 as k


class TestDht11Diagnosis(unittest.TestCase):
    def test_classify_real_library_messages(self):
        self.assertEqual(k.classify_error('DHT sensor not found, check wiring'), 'not_found')
        self.assertEqual(k.classify_error('Checksum did not validate. Try again.'), 'checksum')
        self.assertEqual(k.classify_error('A full buffer was not returned. Try again.'), 'timing')
        self.assertEqual(k.classify_error('Unable to set line 17 to input'), 'busy')
        self.assertEqual(k.classify_error("No module named 'adafruit_dht'"), 'library')
        self.assertEqual(k.classify_error('weird'), 'other')

    def test_summary_fail_lists_wiring_fixes(self):
        verdict, lines = k.summarize([(None, None, 'not_found', 'x')] * 10)
        self.assertEqual(verdict, 'KHONG_DAT')
        self.assertTrue(any('GPIO17' in line for line in lines))

    def test_summary_pass_with_occasional_timing_and_ds_comparison(self):
        results = [(58.0, 30.0, None, '')] * 7 + [(None, None, 'timing', 'x')] * 3
        verdict, lines = k.summarize(results, ds_temp=37.4)
        self.assertEqual(verdict, 'DAT')
        self.assertTrue(any('Lệch > 3 °C' in line for line in lines))
        self.assertFalse(any('giảm tải CPU' in line for line in lines))  # lỗi nhịp lẻ tẻ: không cần hướng dẫn

    def test_read_ds18b20_from_sysfs_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev = Path(tmp) / '28-000000ca6c1f'
            dev.mkdir()
            (dev / 'w1_slave').write_text('72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n72 01 4b 46 7f ff 0e 10 57 t=37437\n',
                                          encoding='ascii')
            self.assertAlmostEqual(k.read_ds18b20(tmp), 37.437)


if __name__ == '__main__':
    unittest.main(verbosity=2)
