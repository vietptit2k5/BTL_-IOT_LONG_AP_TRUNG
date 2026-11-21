"""Kiểm thử phan_tich_ap_trung.py bằng CSV tự tạo (không cần dữ liệu thật)."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Code_HopAp_Demo'))
import phan_tich_ap_trung as pt  # noqa: E402
from cloud_bridge import CSV_FIELDS  # noqa: E402


def row(t, temp, phase, lamp=50, fan=100, event='MEASUREMENT'):
    stamp = datetime.fromtimestamp(1_800_000_000 + t, timezone.utc).isoformat(timespec='milliseconds')
    return [stamp, f'{t:.3f}', event, phase, '28-x', f'{temp:.4f}', '0.05', 1, lamp, fan, lamp, fan, 100, 38.8,
            '', '', '', '', '']


class TestPhanTich(unittest.TestCase):
    def make(self, folder, rows, controller='ap-trung'):
        folder.mkdir(parents=True)
        with (folder / 'du_lieu.csv').open('w', encoding='utf-8-sig', newline='') as s:
            w = csv.writer(s)
            w.writerow(CSV_FIELDS)
            w.writerows(rows)
        (folder / 'cau_hinh.json').write_text(json.dumps({'bo_dieu_khien': controller}), encoding='utf-8')
        return folder

    def rows(self):
        r = [row(t, 30 + t * 0.1, 'lam_am_ap', 75) for t in range(0, 60)]
        r += [row(t, 37.8, 'ap_ngay05_gd1') for t in range(60, 660)]                       # 10 phút đúng mốc 1
        r += [row(t, 37.8 - (t - 660) * 0.005, 'ap_ngay12_gd2', 0) for t in range(660, 720)]  # 60 s chuyển mốc
        r += [row(t, 37.5 + (0.3 if t % 100 < 10 else 0), 'ap_ngay12_gd2', 25 if t % 2 else 50) for t in range(720, 1320)]
        r += [row(1321, 37.5, 'giu_quat_cuoi', 0, 0, 'END')]
        return r

    def test_segments_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = pt.analyze(pt.load_run(self.make(Path(tmp) / 'luot', self.rows())))
            segs = run['doan_theo_ngay']
            self.assertEqual([(s['ngay'], s['giai_doan'], s['muc_tieu_c']) for s in segs], [(5, 1, 37.8), (12, 2, 37.5)])
            self.assertEqual(segs[0]['vao_vung_sau_s'], 0)
            self.assertEqual(segs[0]['trong_vung_pct'], 100.0)
            self.assertEqual(segs[0]['mae_c'], 0.0)
            self.assertEqual(segs[1]['vao_vung_sau_s'], 20)          # 37,8 → 37,7 (biên trên mốc 2) sau 20 s
            self.assertLess(segs[1]['trong_vung_pct'], 100)         # có những lúc 37,8 trong mốc 2
            self.assertGreater(segs[1]['doi_muc_moi_10_phut'], 100)  # đổi bóng liên tục
            self.assertTrue(run['ket_thuc'])
            self.assertFalse(run['mo_phong'])
            self.assertEqual(run['bo_dieu_khien'], 'Q-learning 3 giai đoạn')
            self.assertEqual(set(run['theo_giai_doan']), {'1', '2'})

    def test_report_and_cli_marks_simulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sim = self.make(base / 'sim', self.rows(), 'ap-trung-thermostat')
            cfg = json.loads((sim / 'cau_hinh.json').read_text(encoding='utf-8'))
            (sim / 'cau_hinh.json').write_text(json.dumps(dict(cfg, mo_phong=True)), encoding='utf-8')
            real = self.make(base / 'that', self.rows())
            self.assertEqual(pt.main([str(real), str(sim), '--out', str(base / 'out')]), 0)
            text = (base / 'out' / 'KET_QUA.md').read_text(encoding='utf-8')
            self.assertIn('MÔ PHỎNG', text)
            self.assertIn('Thermostat 3 giai đoạn', text)
            data = json.loads((base / 'out' / 'ket_qua.json').read_text(encoding='utf-8'))
            self.assertEqual([d['mo_phong'] for d in data], [False, True])

    def test_rejects_non_staged_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.make(Path(tmp) / 'cu', [row(t, 37.5, 'kiem_tra_rl_moi') for t in range(100)])
            self.assertEqual(pt.main([str(folder), '--out', str(Path(tmp) / 'out')]), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
