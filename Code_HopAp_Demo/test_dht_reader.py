"""Kiểm thử dht_reader.py: tìm driver kernel dht11 và đọc qua sysfs IIO (thư mục giả, không cần Pi)."""
import errno
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import dht_reader as dr
from kiem_tra_dht11 import classify_error


def fake_iio(root, name='dht11@11', temp='31000', rh='58000'):
    import os
    dev = Path(root) / ('iio:device0' if os.name == 'posix' else 'iio_device0')  # Windows không cho ':' trong tên
    dev.mkdir(parents=True)
    (dev / 'name').write_text(name + '\n')
    (dev / 'in_temp_input').write_text(temp + '\n')
    (dev / 'in_humidityrelative_input').write_text(rh + '\n')
    return dev


class TestKernelDHT(unittest.TestCase):
    def test_find_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(dr.find_kernel_dht11(tmp))
            dev = fake_iio(tmp)
            self.assertEqual(dr.find_kernel_dht11(tmp), dev)
            reader = dr.open_dht11('auto', root=tmp)
            self.assertEqual(reader.kind, 'kernel')
            self.assertEqual(reader.read(), (58.0, 31.0))

    def test_ignores_other_iio_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_iio(tmp, name='ads1015')
            self.assertIsNone(dr.find_kernel_dht11(tmp))
            with self.assertRaises(RuntimeError):
                dr.open_dht11('kernel', root=tmp)

    def test_errors_map_to_diagnosis(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader = dr.KernelDHT(fake_iio(tmp))
            cases = {errno.ETIMEDOUT: 'not_found', errno.EIO: 'checksum'}
            for code, kind in cases.items():
                with mock.patch.object(Path, 'read_text', side_effect=OSError(code, 'x')):
                    with self.assertRaises(RuntimeError) as ctx:
                        reader.read()
                self.assertEqual(classify_error(str(ctx.exception)), kind)


if __name__ == '__main__':
    unittest.main(verbosity=2)
