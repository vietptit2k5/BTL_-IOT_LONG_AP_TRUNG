"""Kiểm thử 3 tính năng demo: thử nhiễu, cảnh báo Telegram, "RL đang nghĩ gì" (bridge 1.5)."""
import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import cloud_bridge as cb
import thong_bao_telegram as tg
import thu_nhieu as tn
from test_cloud_bridge import row, write_csv


# --------------------------------------------------------------------------- thử nhiễu (hàm thuần)
class TestThuNhieu(unittest.TestCase):
    def make(self):
        return tn.new_test('lanh', 60, 1000.0, 'a@b.c', 37.5, (37.3, 37.7), 'Q-learning 3 giai đoạn', 'S1')

    def run_points(self, test, points):
        for t, temp in points:
            tn.feed(test, t, temp, 37.3 <= temp <= 37.7, 'tay' if t <= 1060 else 'giu_nhiet')

    def test_recovery_times(self):
        test = self.make()
        pts = [(1000 + i, 37.5 - 0.006 * i) for i in range(1, 61)]                # nhiễu: tụt tới 37,14
        pts += [(1060 + i, 37.14 + 0.006 * i) for i in range(1, 31)]              # RL kéo lên, vào vùng ~ +27 s
        pts += [(1090 + i, 37.4) for i in range(1, 100)]                           # ở yên trong vùng
        self.run_points(test, pts)
        self.assertEqual(test['trang_thai'], 'XONG')
        self.assertTrue(test['ra_vung'])
        self.assertAlmostEqual(test['ve_vung_s'], 27, delta=1.5)
        self.assertEqual(test['on_dinh_s'], test['ve_vung_s'])
        self.assertAlmostEqual(test['lech_max_c'], 0.36, delta=0.01)
        self.assertIn('về vùng sau 0:2', tn.summary_text(test))

    def test_never_left_band_and_repeat_points_ignored(self):
        test = self.make()
        self.run_points(test, [(1000 + i, 37.45) for i in range(1, 200)])
        self.assertEqual(test['trang_thai'], 'XONG')
        self.assertFalse(test['ra_vung'])
        self.assertIn('KHÔNG ra khỏi vùng', tn.summary_text(test))
        self.assertFalse(tn.feed(test, 1300, 36.0, False, 'giu_nhiet'))  # đã xong: không đổi kết quả

    def test_streak_resets_and_timeout(self):
        test = self.make()
        self.run_points(test, [(1000 + i, 37.2) for i in range(1, 61)])
        self.run_points(test, [(1060 + i, 37.4 if i < 40 else 37.2) for i in range(1, 80)])  # vào rồi lại ra
        self.assertEqual(test['trang_thai'], 'DANG_PHUC_HOI')
        self.assertIsNone(test['chuoi_tu'])
        tn.feed(test, 1060 + tn.HET_GIO_S + 1, 37.1, False, 'giu_nhiet')
        self.assertEqual(test['trang_thai'], 'CHUA_VE_VUNG')
        self.assertFalse(tn.feed(test, 1061, 37.5, True, 'giu_nhiet'))

    def test_cancel(self):
        test = tn.cancel(self.make(), 'a@b.c hủy')
        self.assertEqual(test['trang_thai'], 'HUY')
        self.assertIn('đã hủy', tn.summary_text(test))


# --------------------------------------------------------------------------- Telegram
class FakeResponse:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, result=None, fail=None):
        self.calls, self.result, self.fail = [], result, fail

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        if self.fail:
            raise self.fail
        return FakeResponse({'ok': True, 'result': self.result})


class TestTelegram(unittest.TestCase):
    CONFIG = {'token': '123:SECRET', 'chat_id': [11, 22], 'muc': tg.DEFAULT_LEVELS, 'them': tg.DEFAULT_EXTRA}

    def notifier(self, session, clock=lambda: 2_000_000.0):
        return tg.TelegramNotifier(self.CONFIG, session=session, clock=clock, background=False,
                                   log=lambda m: None, sleep=lambda s: None)

    def alert(self, kind, level, ts=2_000_000_000):
        return {'ts': ts, 'loai': kind, 'muc': level, 'noi_dung': f'{kind} nội dung', 'nhiet_c': 38.31}

    def test_sends_only_important_once_to_every_chat(self):
        s = FakeSession()
        n = self.notifier(s)
        self.assertTrue(n.offer('k1', self.alert('BAO_VE', 'canh_bao')))
        self.assertFalse(n.offer('k1', self.alert('BAO_VE', 'canh_bao')))        # đã gửi
        self.assertFalse(n.offer('k2', self.alert('DOI_NGAY', 'thong_tin')))     # thông tin thường: không
        self.assertTrue(n.offer('k3', self.alert('KET_THUC', 'thong_tin')))      # nằm trong danh sách "them"
        self.assertEqual([c[1]['chat_id'] for c in s.calls], [11, 22, 11, 22])
        text = s.calls[0][1]['text']
        self.assertIn('🟠 Cảnh báo · Hộp ấp nhóm 13', text)
        self.assertIn('38,31 °C', text)
        self.assertTrue(s.calls[0][0].endswith('/bot123:SECRET/sendMessage'))

    def test_old_backfilled_alerts_skipped(self):
        n = self.notifier(FakeSession(), clock=lambda: 2_000_000 + tg.MAX_AGE_S + 5)
        self.assertFalse(n.offer('k', self.alert('LOI', 'nguy_hiem', ts=2_000_000_000)))

    def test_errors_hide_token(self):
        logs = []
        n = tg.TelegramNotifier(self.CONFIG, session=FakeSession(fail=OSError('fail https://x/bot123:SECRET/send')),
                                background=False, log=logs.append, sleep=lambda s: None)
        n.offer('k', self.alert('LOI', 'nguy_hiem', ts=int(time.time() * 1000)))
        self.assertEqual(len(logs), tg.RETRIES)
        self.assertTrue(all('SECRET' not in m and '<token>' in m for m in logs))

    def test_chat_ids_and_config(self):
        s = FakeSession(result=[{'message': {'chat': {'id': 5, 'first_name': 'An', 'last_name': 'Lê'}}},
                                {'message': {'chat': {'id': -9, 'title': 'Nhóm 13'}}}])
        self.assertEqual(self.notifier(s).chat_ids(), [(5, 'An Lê'), (-9, 'Nhóm 13')])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'telegram_bi_mat.json'
            self.assertIsNone(tg.make_notifier(path, log=lambda m: None))          # chưa có file: tắt
            path.write_text('{"token": "bad"}', encoding='utf-8')
            self.assertIsNone(tg.make_notifier(path, log=lambda m: None))
            path.write_text('{"token": "1:A", "chat_id": 7}', encoding='utf-8')
            self.assertEqual(tg.load_config(path)['chat_id'], [7])


# --------------------------------------------------------------------------- bridge 1.5
class FakeNotifier:
    def __init__(self):
        self.offers = []

    def offer(self, key, alert):
        self.offers.append(alert['loai'])


def append_rows(path, rows):
    with Path(path).open('a', encoding='utf-8', newline='') as stream:
        csv.writer(stream).writerows(rows)


class TestBridgeTinhNang(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.store = cb.FileStore(self.base / 'db')
        self.csv = self.base / 'ket_qua_ap_trung' / 'lan1' / 'du_lieu.csv'
        self.csv.parent.mkdir(parents=True)
        now = time.time()
        write_csv(self.csv, [row(now - 40 + i, 900 + i, 37.5, phase='ap_ngay12_gd2') for i in range(40)])
        self.tay, self.nao, self.log = self.base / 'lenh_tay.json', self.base / 'nao_rl.json', self.base / 'thu.jsonl'
        self.notifier = FakeNotifier()
        self.bridge = cb.Bridge(self.store, self.base, csv_path=self.csv, state_path=self.base / 's.json',
                                lich_path=self.base / 'lich.json', do_am_path=self.base / 'do_am.json',
                                tay_path=self.tay, nao_path=self.nao, notifier=self.notifier, thu_log_path=self.log)
        self.bridge.running_probe = lambda: [(42, 'python3 ap_trung.py --phut 30')]
        self.is_pi = mock.patch('cloud_bridge.os.path.isdir', return_value=True)
        self.is_pi.start()
        self.bridge.cycle()

    def tearDown(self):
        self.is_pi.stop()
        self.tmp.cleanup()

    def send(self, **data):
        self.store.put('hop_ap_01/commands/thu_nhieu', dict(data, ts=cb.now_ms(), by='a@b.c', da_xu_ly=False))
        self.bridge.cycle()
        return self.store.get('hop_ap_01/commands/thu_nhieu')

    def test_full_disturbance_measures_recovery(self):
        reply = self.send(hanh_dong='bat_dau', kieu='lanh', thoi_han_s=60)
        self.assertEqual(reply['ket_qua'], 'DANG_THU_NHIEU')
        manual = json.loads(self.tay.read_text(encoding='utf-8'))
        self.assertEqual((manual['bong'], manual['quat']), (0, 100))
        self.assertAlmostEqual(manual['het_han'], time.time() + 60, delta=5)
        test = self.bridge.state['thu_nhieu']
        start = test['bat_dau_ts'] / 1000
        self.assertEqual(self.store.get(f'hop_ap_01/thu_nhieu/{test["id"]}')['trang_thai'], 'DANG_NHIEU')
        self.assertIn('THU_NHIEU', self.notifier.offers or ['THU_NHIEU'])  # thông tin: Telegram tự lọc
        rows = [row(start + i, 1000 + i, 37.5 - 0.005 * i, phase='ap_ngay12_gd2_tay', lamp=0) for i in range(1, 61)]
        rows += [row(start + 60 + i, 1060 + i, 37.2 + 0.005 * i, phase='ap_ngay12_gd2') for i in range(1, 41)]
        rows += [row(start + 100 + i, 1100 + i, 37.45, phase='ap_ngay12_gd2') for i in range(1, 80)]
        append_rows(self.csv, rows)
        self.bridge.cycle()
        result = self.store.get(f'hop_ap_01/thu_nhieu/{test["id"]}')
        self.assertEqual(result['trang_thai'], 'XONG')
        self.assertAlmostEqual(result['ve_vung_s'], 21, delta=1.5)
        alerts = [a for a in self.store.get('hop_ap_01/alerts').values() if a['loai'] == 'KET_QUA_THU_NHIEU']
        self.assertEqual(len(alerts), 1)
        self.assertIn('về vùng sau', alerts[0]['noi_dung'])
        self.assertIn('KET_QUA_THU_NHIEU', self.notifier.offers)
        self.assertEqual(json.loads(self.log.read_text(encoding='utf-8').splitlines()[0])['id'], test['id'])
        self.bridge.cycle()  # không báo lại
        self.assertEqual(len([a for a in self.store.get('hop_ap_01/alerts').values()
                              if a['loai'] == 'KET_QUA_THU_NHIEU']), 1)

    def test_refusals_and_cancel(self):
        self.assertEqual(self.send(hanh_dong='bat_dau', kieu='lanh', thoi_han_s=300)['ket_qua'], 'KHONG_HOP_LE')
        self.assertEqual(self.send(hanh_dong='bat_dau', kieu='gio', thoi_han_s=60)['ket_qua'], 'KHONG_HOP_LE')
        self.assertEqual(self.send(hanh_dong='huy')['ket_qua'], 'KHONG_CO_THU_NHIEU')
        self.tay.write_text(json.dumps({'het_han': time.time() + 50}), encoding='utf-8')
        self.assertIn('đang chỉnh tay', self.send(hanh_dong='bat_dau', kieu='nong', thoi_han_s=60)['ket_qua'])
        self.tay.unlink()
        self.bridge.running_probe = lambda: []
        self.assertIn('không có lượt ap_trung', self.send(hanh_dong='bat_dau', kieu='nong', thoi_han_s=60)['ket_qua'])
        self.bridge.running_probe = lambda: [(42, 'python3 ap_trung.py')]
        append_rows(self.csv, [row(time.time(), 1000, 37.9, phase='ap_ngay12_gd2')])
        self.bridge.cycle()
        self.assertIn('ngoài vùng', self.send(hanh_dong='bat_dau', kieu='nong', thoi_han_s=60)['ket_qua'])
        append_rows(self.csv, [row(time.time(), 1001, 37.5, phase='ap_ngay12_gd2')])
        self.bridge.cycle()
        self.assertEqual(self.send(hanh_dong='bat_dau', kieu='nong', thoi_han_s=120)['ket_qua'], 'DANG_THU_NHIEU')
        self.assertIn('thử nhiễu khác', self.send(hanh_dong='bat_dau', kieu='lanh', thoi_han_s=60)['ket_qua'])
        self.assertEqual(self.send(hanh_dong='huy')['ket_qua'], 'DA_HUY_THU')
        self.assertEqual(json.loads(self.tay.read_text(encoding='utf-8'))['het_han'], 0)
        test_id = self.bridge.state['thu_nhieu']['id']
        self.bridge.cycle()
        self.assertEqual(self.store.get(f'hop_ap_01/thu_nhieu/{test_id}')['trang_thai'], 'HUY')

    def test_brain_published_only_when_fresh(self):
        self.nao.write_text(json.dumps({'ts': cb.now_ms(), 'che_do': 'q', 'chon': 3, 'q': [1.0] * 9}), encoding='utf-8')
        self.bridge.cycle()
        self.assertEqual(self.store.get('hop_ap_01/nao_rl')['chon'], 3)
        self.nao.write_text(json.dumps({'ts': cb.now_ms() - 120_000, 'che_do': 'q', 'chon': 5}), encoding='utf-8')
        self.bridge.cycle()
        self.assertEqual(self.store.get('hop_ap_01/nao_rl')['chon'], 3)

    def test_alerts_reach_notifier_only_for_live_source(self):
        append_rows(self.csv, [row(time.time(), 1000 + i, 38.35, phase='ap_ngay12_gd2_bao_ve', lamp=0) for i in range(3)])
        self.bridge.cycle()
        self.assertIn('BAO_VE', self.notifier.offers)
        replay = cb.Bridge(self.store, self.base, csv_path=self.csv, state_path=self.base / 's2.json',
                           source='phat_lai', notifier=FakeNotifier())
        replay.cycle()
        self.assertEqual(replay.notifier.offers, [])


# --------------------------------------------------------------------------- ap_trung ghi "bộ não"
class TestNaoRl(unittest.TestCase):
    def test_decode_state_roundtrip(self):
        import ap_trung
        from rl_vung_on_dinh import state_id
        for temp, delta, memory, prev, guard in [(37.0, -0.1, 0.1, 0, False), (37.55, 0.0, 0.5, 4, False),
                                                 (38.4, 0.2, 0.9, 8, True)]:
            s = state_id(temp, delta, memory, prev, guard)
            parts = ap_trung.decode_state(s)
            self.assertEqual(state_id(temp, delta, memory, prev, guard),
                             ((((parts['sai_so'] * 3 + parts['xu_huong']) * 5 + parts['nho_nhiet']) * 9
                               + parts['truoc']) * 2 + parts['bao_ve']))
            self.assertEqual((parts['truoc'], parts['bao_ve']), (prev, int(guard)))

    def test_policy_writes_brain_file(self):
        import me_ap
        from test_ap_trung import TestPolicy
        case = TestPolicy('test_finishes_after_requested_minutes')
        TestPolicy.setUpClass()
        case.setUp()
        try:
            nao = Path(case.tmp.name) / 'nao_rl.json'
            p = case.make()
            p.nao_path = nao
            case.call(p, 28.0)
            self.assertEqual(json.loads(nao.read_text(encoding='utf-8'))['che_do'], 'lam_am')
            case.call(p, 37.8)
            data = json.loads(nao.read_text(encoding='utf-8'))
            self.assertEqual(data['che_do'], 'q')
            self.assertEqual(len(data['q']), 9)
            self.assertIn(data['chon'], range(9))
            self.assertEqual(data['muc_tieu_c'], 37.8)
            self.assertEqual(set(data['thanh_phan']), {'sai_so', 'xu_huong', 'nho_nhiet', 'truoc', 'bao_ve'})
            if data['ly_do'] == 'q_max':
                best = max(v for v in data['q'] if v is not None)
                self.assertEqual(data['q'][data['chon']], best)
            self.assertTrue(me_ap.load(case.lich))
        finally:
            case.tearDown()


# --------------------------------------------------------------------------- sức khỏe thiết bị
class TestSucKhoe(unittest.TestCase):
    def fake_pi(self, root):
        root = Path(root)
        (root / 'sys/class/thermal/thermal_zone0').mkdir(parents=True)
        (root / 'sys/class/thermal/thermal_zone0/temp').write_text('52615\n', encoding='utf-8')
        (root / 'proc/net').mkdir(parents=True)
        (root / 'proc/uptime').write_text('93784.21 350000.00\n', encoding='utf-8')
        (root / 'proc/meminfo').write_text('MemTotal:  1000000 kB\nMemFree: 100 kB\nMemAvailable:  750000 kB\n',
                                          encoding='utf-8')
        (root / 'proc/net/wireless').write_text(
            'Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n'
            ' face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n'
            ' wlan0: 0000   58.  -52.  -256        0      0      0      0     44        0\n', encoding='utf-8')
        return root

    def test_collect_reads_pi_files(self):
        import suc_khoe
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root = self.fake_pi(tmp)
            run = lambda *a, **k: SimpleNamespace(stdout='throttled=0x50005\n')
            d = suc_khoe.collect(tmp, sys_root=root / 'sys', proc_root=root / 'proc', run=run)
        self.assertEqual((d['cpu_c'], d['uptime_s'], d['ram_dung_pct'], d['wifi_dbm']), (52.6, 93784, 25.0, -52))
        self.assertEqual(d['nguon'], {'yeu_hien_tai': True, 'giam_xung_hien_tai': True, 'tung_yeu': True,
                                      'tung_giam_xung': True, 'ma': '0x50005'})
        self.assertGreater(d['the_nho_trong_gb'], 0)

    def test_missing_files_give_none(self):
        import suc_khoe

        def no_cmd(*a, **k):
            raise FileNotFoundError('vcgencmd')
        with tempfile.TemporaryDirectory() as tmp:
            d = suc_khoe.collect(tmp, sys_root=Path(tmp) / 'x', proc_root=Path(tmp) / 'y', run=no_cmd)
        self.assertEqual([d[k] for k in ('cpu_c', 'uptime_s', 'ram_dung_pct', 'wifi_dbm', 'nguon')], [None] * 5)

    def test_bridge_publishes_health_every_30s_with_sensor_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = cb.FileStore(base / 'db')
            path = base / 'ket_qua_ap_trung' / 'l' / 'du_lieu.csv'
            path.parent.mkdir(parents=True)
            now = time.time()
            rows = [row(now - 20 + i, i, 37.5, phase='ap_ngay12_gd2') for i in range(18)]
            rows += [row(now - 2, 18, None, phase='ap_ngay12_gd2'), row(now - 1, 19, 37.5, phase='ap_ngay12_gd2')]
            write_csv(path, rows)
            clock = [1000.0]
            bridge = cb.Bridge(store, base, csv_path=path, state_path=base / 's.json', lich_path=base / 'l.json',
                               do_am_path=base / 'd.json', tay_path=base / 't.json', nao_path=base / 'n.json',
                               clock=lambda: clock[0])
            calls = []
            bridge.health_reader = lambda b: calls.append(b) or {'cpu_c': 50.0}
            bridge.cycle()
            data = store.get('hop_ap_01/suc_khoe')
            self.assertEqual((data['cpu_c'], data['bridge']), (50.0, cb.VERSION))
            self.assertEqual((data['ds18b20']['doc'], data['ds18b20']['loi'], data['ds18b20']['ty_le_ok_pct']),
                             (20, 1, 95.0))
            self.assertEqual(data['telegram']['bat'], False)
            clock[0] += 10
            bridge.cycle()
            self.assertEqual(len(calls), 1)  # chưa tới 30 s
            clock[0] += 25
            bridge.cycle()
            self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
