#!/usr/bin/env python3
"""Kiểm thử cloud_bridge.py: không cần mạng, Firebase hay GPIO."""

import csv
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

import cloud_bridge as cb

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'Du_lieu_giu_nhiet'
PILOT = DATA / '20261120_pilot_01' / 'du_lieu.csv'


def row(t, elapsed, temp, phase='kiem_tra_rl_moi', event='MEASUREMENT', lamp=50, fan=100, age=0.05, note='', rh=''):
    from datetime import datetime, timezone
    stamp = datetime.fromtimestamp(t, timezone.utc).isoformat(timespec='milliseconds')
    return [stamp, f'{elapsed:.3f}', event, phase, '28-x', '' if temp is None else f'{temp:.4f}', f'{age:.3f}',
            '1', str(lamp), str(fan), str(lamp), str(fan), '100', '38.5', '', note, rh, '', '']


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(cb.CSV_FIELDS)
        writer.writerows(rows)


class TestBasics(unittest.TestCase):
    def test_csv_fields_match_controller(self):
        import do_nhiet_hop
        self.assertEqual(cb.CSV_FIELDS, do_nhiet_hop.CSV_FIELDS)

    def test_classify(self):
        cases = {'cho_cam_bien': 'cho', 'lam_am_rl_moi': 'lam_am', 'lam_am_bao_ve': 'bao_ve',
                 'kiem_tra_rl_moi': 'giu_nhiet', 'kiem_tra_giu_nhiet': 'giu_nhiet', 'kiem_tra_bao_ve': 'bao_ve',
                 'kiem_tra_rl_moi_phuc_hoi': 'phuc_hoi', 'bao_ve_mem_2': 'bao_ve', 'giu_quat_cuoi': 'quat_cuoi',
                 'giu_co_dinh': 'giu_nhiet', 'xyz': 'khac'}
        for phase, expected in cases.items():
            self.assertEqual(cb.classify(phase), expected, phase)

    def test_safe_key(self):
        self.assertEqual(cb.safe_key('a.b/c d#e'), 'a_b_c_d_e')


class TestTail(unittest.TestCase):
    def test_partial_line_bom_and_quoted_comma(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'du_lieu.csv'
            write_csv(path, [row(1000, 1, 37.0, note='a, b')])
            with path.open('ab') as stream:
                stream.write(b'2026-11-20T00:00:00')  # Dòng đang ghi dở.
            tail = cb.CsvTail(path)
            rows, offset = tail.read_new()
            self.assertEqual(rows[0], list(cb.CSV_FIELDS))  # Đã bỏ BOM.
            self.assertEqual(rows[1][15], 'a, b')
            self.assertEqual(len(rows), 2)
            tail.offset = offset
            self.assertEqual(tail.read_new()[0], [])

    def test_newest_csv_ignores_replay_and_foreign_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real = base / 'ket_qua_rl_moi' / 'r1' / 'du_lieu.csv'
            real.parent.mkdir(parents=True)
            write_csv(real, [row(1000, 1, 37)])
            replay = base / '.cloud_bridge' / 'phat_lai' / 'p' / 'du_lieu.csv'
            replay.parent.mkdir(parents=True)
            write_csv(replay, [row(1000, 1, 37)])
            other = base / 'ket_qua_x' / 'r2' / 'du_lieu.csv'
            other.parent.mkdir(parents=True)
            other.write_text('a,b\n1,2\n', encoding='utf-8')
            os.utime(real, (1, 1))
            self.assertEqual(cb.newest_csv(base), real.resolve())


class TestEngine(unittest.TestCase):
    def feed(self, rows, engine=None):
        engine = engine or cb.Engine('s')
        return engine, engine.feed([list(cb.CSV_FIELDS)] + rows)

    def test_samples_every_5s(self):
        rows = [row(1000 + i, i, 37.5) for i in range(0, 21)]
        _, out = self.feed(rows)
        self.assertEqual(sorted(out['samples']), ['000000', '000005', '000010', '000015', '000020'])

    def test_out_of_band_then_settled_and_cooldown(self):
        t0, rows = 1000, []
        rows += [row(t0 + i, i, 37.5) for i in range(0, 10)]                 # giữ nhiệt bắt đầu
        rows += [row(t0 + i, i, 37.9) for i in range(10, 80)]                # ngoài vùng 70 s
        rows += [row(t0 + i, i, 37.5) for i in range(80, 150)]               # trở lại 70 s
        rows += [row(t0 + i, i, 37.9) for i in range(150, 230)]              # lại ngoài vùng (trong 5 phút)
        _, out = self.feed(rows)
        kinds = [a['loai'] for a in out['alerts'].values()]
        self.assertEqual(kinds.count('NGOAI_VUNG'), 1)  # Lần 2 bị chặn bởi giới hạn 5 phút.
        self.assertEqual(kinds.count('ON_DINH'), 1)

    def test_durations_use_elapsed_not_wall_clock(self):
        """Phát lại ×10: mốc giờ cách 0,1 s nhưng elapsed cách 1 s; 60 s ngoài vùng vẫn phải là 60 s đo."""
        rows = [row(1000 + i / 10, i, 37.5) for i in range(10)]
        rows += [row(1000 + i / 10, i, 37.9) for i in range(10, 65)]      # 55 s ngoài vùng: chưa báo
        _, out = self.feed(rows)
        self.assertEqual(out['alerts'], {})
        rows += [row(1000 + i / 10, i, 37.9) for i in range(65, 75)]      # đủ 60 s
        _, out = self.feed(rows)
        alert = next(iter(out['alerts'].values()))
        self.assertEqual(alert['loai'], 'NGOAI_VUNG')
        self.assertEqual(alert['ts'], int((1000 + 7.0) * 1000))           # thời điểm hiển thị = mốc giờ của dòng

    def test_no_band_alert_during_warmup(self):
        rows = [row(1000 + i, i, 30 + i * 0.01, phase='lam_am_rl_moi', lamp=75) for i in range(200)]
        _, out = self.feed(rows)
        self.assertEqual(out['alerts'], {})

    def test_drop_with_heater_on_means_lid(self):
        rows = [row(1000 + i, i, 37.5) for i in range(10)]
        rows += [row(1000 + i, i, 37.5 - (i - 10) * 0.03) for i in range(10, 45)]  # tụt ~1 °C/35 s, bóng 50%
        _, out = self.feed(rows)
        self.assertIn('NGHI_MO_NAP', [a['loai'] for a in out['alerts'].values()])

    def test_drop_with_heater_off_is_normal(self):
        rows = [row(1000 + i, i, 37.6) for i in range(10)]
        rows += [row(1000 + i, i, 37.6 - (i - 10) * 0.03, lamp=0) for i in range(10, 45)]
        _, out = self.feed(rows)
        self.assertNotIn('NGHI_MO_NAP', [a['loai'] for a in out['alerts'].values()])

    def test_guard_sensor_error_end(self):
        rows = [row(1000, 0, 37.5), row(1001, 1, 38.0, phase='kiem_tra_bao_ve', lamp=0),
                row(1002, 2, None, age=4), row(1003, 3, 37.9, event='ERROR', note='Mất số đo'),
                row(1004, 4, 37.9, event='END', phase='giu_quat_cuoi')]
        engine, out = self.feed(rows)
        kinds = sorted(a['loai'] for a in out['alerts'].values())
        self.assertEqual(kinds, ['BAO_VE', 'KET_THUC', 'LOI', 'LOI_CAM_BIEN'])
        self.assertTrue(engine.s['ended'])
        self.assertEqual(len(out['events']), 2)

    def test_state_is_json_serializable(self):
        engine, _ = self.feed([row(1000 + i, i, 37.5) for i in range(40)])
        json.dumps(engine.snapshot())


@unittest.skipUnless(DATA.exists(), 'Không có dữ liệu đo thật')
class TestRealData(unittest.TestCase):
    def test_no_false_alarms_on_real_hold_runs(self):
        """Các lượt thật không mở nắp, không lỗi: không được có NGHI_MO_NAP/LOI giả."""
        checked = 0
        for path in DATA.rglob('du_lieu.csv'):
            if not cb.is_control_csv(path):
                continue
            engine = cb.Engine('x')
            rows, _ = cb.CsvTail(path).read_new()
            out = engine.feed(rows)
            kinds = [a['loai'] for a in out['alerts'].values()]
            self.assertNotIn('NGHI_MO_NAP', kinds, path)
            self.assertNotIn('LOI', kinds, path)
            self.assertNotIn('LOI_CAM_BIEN', kinds, path)
            checked += 1
        self.assertGreaterEqual(checked, 3)

    @unittest.skipUnless(PILOT.exists(), 'Thiếu pilot 20/11')
    def test_summary_close_to_original_report(self):
        summary = cb.summarize_csv(PILOT)
        original = json.loads((PILOT.parent / 'ket_qua.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['trang_thai'], 'HOAN_TAT')
        self.assertAlmostEqual(summary['mae_c'], original['mae_c'], delta=0.01)
        self.assertAlmostEqual(summary['trong_vung_pct'], original['in_band_pct'], delta=1.0)
        self.assertEqual(cb.describe_controller(cb.read_run_config(PILOT)), 'Q-learning v2')


class TestBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.csv = base / 'ket_qua_rl_moi' / 'r1' / 'du_lieu.csv'
        self.csv.parent.mkdir(parents=True)
        self.store = cb.FileStore(base / 'db')
        self.base = base

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        return cb.Bridge(self.store, self.base, csv_path=self.csv, state_path=self.base / 'state.json')

    def test_resend_after_network_loss_without_duplicates(self):
        rows = [row(1000 + i, i, 37.5) for i in range(10)] + [row(1000 + i, i, 37.95) for i in range(10, 90)]
        write_csv(self.csv, rows)
        bridge = self.make()
        self.store.fail_next = 1  # Lần PATCH đầu tiên mất mạng.
        bridge.cycle()
        self.assertEqual(bridge.tail.offset, 0)  # Không tiến vị trí khi gửi lỗi.
        bridge.cycle()
        self.assertGreater(bridge.tail.offset, 0)
        tree = self.store.get('hop_ap_01')
        self.assertEqual(len(tree['sessions']['r1']['samples']), 18)
        self.assertEqual([a['loai'] for a in tree['alerts'].values()], ['NGOAI_VUNG'])
        self.assertEqual(tree['live']['trang_thai'], 'DANG_CHAY')
        self.assertIn('meta', tree['sessions']['r1'])

    def test_resume_from_saved_state_after_restart(self):
        write_csv(self.csv, [row(1000 + i, i, 37.5) for i in range(10)])
        self.make().cycle()
        with self.csv.open('a', encoding='utf-8', newline='') as stream:
            csv.writer(stream).writerows([row(1000 + i, i, 37.5) for i in range(10, 20)])
        bridge = self.make()  # Như khởi động lại bridge.
        bridge.cycle()
        samples = self.store.get('hop_ap_01/sessions/r1/samples')
        self.assertEqual(sorted(samples), ['000000', '000005', '000010', '000015'])

    def test_summary_after_end_and_result_file(self):
        rows = [row(1000 + i, i, 37.5) for i in range(0, 600)] + [row(1601, 601, 37.4, event='END', phase='giu_quat_cuoi')]
        write_csv(self.csv, rows)
        (self.csv.parent / 'ket_qua.json').write_text(json.dumps({'mae_c': 0.1, 'status': 'X'}), encoding='utf-8')
        bridge = self.make()
        bridge.cycle()
        summary = self.store.get('hop_ap_01/sessions/r1/summary')
        self.assertEqual(summary['trang_thai'], 'HOAN_TAT')
        self.assertEqual(summary['ket_qua_goc']['mae_c'], 0.1)
        self.assertEqual(self.store.get('hop_ap_01/live/trang_thai'), 'KET_THUC')

    def test_dead_run_without_end_is_closed_only_when_no_controller(self):
        write_csv(self.csv, [row(1000 + i, i, 37.5) for i in range(10)])  # không có END
        clock = {'t': 5000.0}
        bridge = cb.Bridge(self.store, self.base, csv_path=self.csv, state_path=self.base / 'st.json',
                           clock=lambda: clock['t'])
        bridge.running_probe = lambda: [(42, 'python3 ap_trung.py')]
        bridge.cycle()
        clock['t'] += 25
        bridge.cycle()                                    # còn tiến trình: chỉ cảnh báo PI_KHONG_GHI
        self.assertEqual(self.store.get('hop_ap_01/live/trang_thai'), 'DANG_CHAY')
        bridge.running_probe = lambda: []
        clock['t'] += 5
        bridge.cycle()                                    # không còn tiến trình: đóng lượt
        self.assertEqual(self.store.get('hop_ap_01/live/trang_thai'), 'KET_THUC')
        kinds = [a['loai'] for a in self.store.get('hop_ap_01/alerts').values()]
        self.assertIn('PI_KHONG_GHI', kinds)
        self.assertIn('DUNG_BAT_THUONG', kinds)

    def test_stop_fresh_stale_and_handled(self):
        now = cb.now_ms()
        self.assertTrue(cb.stop_is_fresh({'value': True, 'ts': now - 1000}, 0, now))
        self.assertFalse(cb.stop_is_fresh({'value': True, 'ts': now - 1000}, now - 1000, now))  # đã xử lý
        self.assertFalse(cb.stop_is_fresh({'value': True, 'ts': now - 3600_000}, 0, now))      # quá cũ
        self.assertFalse(cb.stop_is_fresh({'value': False, 'ts': now}, 0, now))
        self.assertFalse(cb.stop_is_fresh(None, 0, now))

    def test_stop_command_is_handled_once(self):
        write_csv(self.csv, [row(1000 + i, i, 37.5) for i in range(10)])
        bridge = self.make()
        calls = []
        bridge.execute_stop = lambda command: calls.append(command) or 'DA_GUI_SIGTERM_PID_1'
        self.store.put('hop_ap_01/commands/stop', {'value': True, 'ts': cb.now_ms(), 'by': 'a@b.c'})
        bridge.cycle()
        bridge.cycle()
        self.assertEqual(len(calls), 1)
        command = self.store.get('hop_ap_01/commands/stop')
        self.assertFalse(command['value'])
        self.assertEqual(command['ket_qua'], 'DA_GUI_SIGTERM_PID_1')
        self.assertIn('DUNG_TU_XA', [a['loai'] for a in self.store.get('hop_ap_01/alerts').values()])

    def test_find_writer_pids(self):
        target = os.path.realpath('/x/du_lieu.csv')
        fds = {'101': {'3': target}, '102': {'3': '/other'}, '103': {'4': target}}
        cmd = {'101': 'python3 thu_rl_du_lieu_moi.py', '103': 'tail -f du_lieu.csv'}
        listdir = lambda p: list(fds) if p == '/proc' else list(fds[Path(p).parent.name])
        readlink = lambda p: fds[Path(p).parent.parent.name][Path(p).name]
        pids = cb.find_writer_pids('/x/du_lieu.csv', '/proc', readlink, listdir, lambda pid: cmd.get(pid, ''))
        self.assertEqual(pids, [101])  # 103 mở file nhưng không phải python.


class TestBaGiaiDoan(unittest.TestCase):
    """Lượt ap_trung.py: mốc/vùng theo pha ap_ngayNN_gdK, chuyển giai đoạn, lệnh đổi ngày từ app."""

    def staged_rows(self):
        rows = [row(1000 + i, i, 30 + i * 0.2, phase='lam_am_ap', lamp=75) for i in range(0, 30)]
        rows += [row(1000 + i, i, 37.8, phase='ap_ngay05_gd1') for i in range(30, 130)]     # đúng mốc 1
        rows += [row(1000 + i, i, 37.8 - (i - 130) * 0.01, phase='ap_ngay12_gd2', lamp=0) for i in range(130, 160)]
        rows += [row(1000 + i, i, 37.5, phase='ap_ngay12_gd2') for i in range(160, 260)]    # đúng mốc 2
        return rows

    def test_stage_parsing(self):
        self.assertEqual(cb.stage_of('ap_ngay12_gd2')['muc_tieu_c'], 37.5)
        self.assertEqual(cb.stage_of('ap_ngay05_gd1_bao_ve')['vung_c'], [37.6, 38.0])
        self.assertIsNone(cb.stage_of('kiem_tra_rl_moi'))
        self.assertIsNone(cb.stage_of('ap_ngay30_gd3'))
        self.assertEqual(cb.classify('ap_ngay12_gd2'), 'giu_nhiet')
        self.assertEqual(cb.classify('ap_ngay12_gd2_tay'), 'tay')  # chỉnh tay: không tính vào chỉ số RL
        self.assertEqual(cb.classify('ap_ngay12_gd2_phuc_hoi'), 'phuc_hoi')

    def test_per_row_band_transition_and_no_false_out_of_band(self):
        engine = cb.Engine('s')
        out = engine.feed([list(cb.CSV_FIELDS)] + self.staged_rows())
        kinds = [a['loai'] for a in out['alerts'].values()]
        self.assertEqual(kinds, ['CHUYEN_GIAI_DOAN'])  # 37,8 °C ở mốc 1 không phải "ngoài vùng 37,3–37,7"
        self.assertEqual(engine.s['latest']['muc_tieu_c'], 37.5)
        self.assertEqual(engine.s['latest']['ngay_ap'], 12)
        sample = out['samples']['000100']
        self.assertEqual((sample['n'], sample['k']), (5, 1))

    def test_out_of_band_uses_new_stage_band(self):
        rows = self.staged_rows() + [row(1000 + i, i, 37.85, phase='ap_ngay12_gd2') for i in range(260, 340)]
        _, out = cb.Engine('s'), None
        out = cb.Engine('s').feed([list(cb.CSV_FIELDS)] + rows)
        alert = [a for a in out['alerts'].values() if a['loai'] == 'NGOAI_VUNG'][0]
        self.assertIn('37.3–37.7', alert['noi_dung'])

    def test_summary_per_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'du_lieu.csv'
            write_csv(path, self.staged_rows())
            s = cb.summarize_csv(path)
            self.assertTrue(s['nhieu_giai_doan'])
            self.assertEqual(s['theo_giai_doan']['1']['mae_c'], 0.0)
            self.assertEqual(s['theo_giai_doan']['2']['muc_tieu_c'], 37.5)
            self.assertEqual(s['theo_giai_doan']['1']['trong_vung_pct'], 100.0)

    def make_bridge(self, tmp):
        base = Path(tmp)
        store = cb.FileStore(base / 'db')
        lich = base / 'lich.json'
        return cb.Bridge(store, base, csv_path=None, state_path=base / 'state.json', lich_path=lich), store, lich

    def test_day_command_sets_schedule_once(self):
        import me_ap
        with tempfile.TemporaryDirectory() as tmp:
            bridge, store, lich = self.make_bridge(tmp)
            me_ap.start_batch(lich, ngay=3)
            store.put('hop_ap_01/commands/ngay_ap', {'ngay': 12, 'ts': cb.now_ms(), 'by': 'a@b.c', 'da_xu_ly': False})
            bridge.cycle()
            self.assertEqual(me_ap.current(me_ap.load(lich))['ngay'], 12)
            reply = store.get('hop_ap_01/commands/ngay_ap')
            self.assertEqual((reply['ket_qua'], reply['da_xu_ly'], reply['yeu_cau_boi']), ('DA_DOI', True, 'a@b.c'))
            published = store.get('hop_ap_01/lich')
            self.assertEqual((published['ngay'], published['giai_doan'], published['co_me']), (12, 2, True))
            self.assertIn('DOI_NGAY', [a['loai'] for a in store.get('hop_ap_01/alerts').values()])
            me_ap.set_day(4, lich)  # đổi tay sau đó: lệnh cũ không được áp lại
            bridge.cycle()
            self.assertEqual(me_ap.current(me_ap.load(lich))['ngay'], 4)

    def test_day_command_invalid_stale_and_creates_batch(self):
        import me_ap
        with tempfile.TemporaryDirectory() as tmp:
            bridge, store, lich = self.make_bridge(tmp)
            store.put('hop_ap_01/commands/ngay_ap', {'ngay': 30, 'ts': cb.now_ms(), 'by': 'a@b.c'})
            bridge.cycle()
            self.assertEqual(store.get('hop_ap_01/commands/ngay_ap')['ket_qua'], 'KHONG_HOP_LE')
            self.assertFalse(lich.exists())
            self.assertFalse(store.get('hop_ap_01/lich')['co_me'])
            store.put('hop_ap_01/commands/ngay_ap', {'ngay': 8, 'ts': cb.now_ms() - 3600_000 + 1, 'by': 'a@b.c'})
            bridge.state['ngay_handled_ts'] = 0
            bridge.cycle()
            self.assertEqual(store.get('hop_ap_01/commands/ngay_ap')['ket_qua'], 'BO_QUA_LENH_CU')
            store.put('hop_ap_01/commands/ngay_ap', {'ngay': 8, 'ts': cb.now_ms(), 'by': 'a@b.c'})
            bridge.cycle()
            self.assertEqual(me_ap.current(me_ap.load(lich))['ngay'], 8)  # chưa có mẻ: tạo mẻ ở ngày 8

    def test_replay_never_touches_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = cb.FileStore(base / 'db')
            bridge = cb.Bridge(store, base, state_path=base / 's.json', source='phat_lai', lich_path=base / 'lich.json')
            store.put('hop_ap_01/commands/ngay_ap', {'ngay': 8, 'ts': cb.now_ms(), 'by': 'a@b.c'})
            bridge.cycle()
            self.assertFalse((base / 'lich.json').exists())
            self.assertIsNone(store.get('hop_ap_01/lich'))


class TestLenhTuApp(unittest.TestCase):
    """Tạo/kết thúc mẻ và bắt đầu lượt từ app: chỉ bật tải khi đủ mọi điều kiện an toàn."""

    def setUp(self):
        import me_ap
        self.me_ap = me_ap
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.store = cb.FileStore(self.base / 'db')
        self.lich = self.base / 'lich.json'
        self.tay = self.base / 'lenh_tay.json'
        self.bridge = cb.Bridge(self.store, self.base, state_path=self.base / 's.json', lich_path=self.lich,
                                do_am_path=self.base / 'do_am.json', tay_path=self.tay)
        self.launched = []
        self.bridge.launcher = lambda base, ctrl, minutes, rh: self.launched.append((ctrl, minutes, rh)) or 'gia_lap'
        self.bridge.running_probe = lambda: []
        self.bridge.box_temperature = lambda: 26.0
        from unittest import mock
        self.is_pi = mock.patch('cloud_bridge.os.path.isdir', return_value=True)
        self.is_pi.start()

    def tearDown(self):
        self.is_pi.stop()
        self.tmp.cleanup()

    def send(self, name, **data):
        self.store.put(f'hop_ap_01/commands/{name}', dict(data, ts=data.pop('ts', cb.now_ms()), by='a@b.c', da_xu_ly=False))
        self.bridge.cycle()
        return self.store.get(f'hop_ap_01/commands/{name}')

    def alerts(self):
        return [a['loai'] for a in (self.store.get('hop_ap_01/alerts') or {}).values()]

    def test_create_batch_with_demo_speed(self):
        reply = self.send('me_ap', hanh_dong='tao', ngay=5, giay_moi_ngay=120)
        self.assertEqual(reply['ket_qua'], 'DA_TAO')
        info = self.me_ap.current(self.me_ap.load(self.lich))
        self.assertEqual((info['ngay'], info['giay_moi_ngay'], info['rut_gon']), (5, 120, True))
        self.assertEqual(self.store.get('hop_ap_01/lich')['ngay'], 5)
        self.assertIn('TAO_ME', self.alerts())
        self.assertEqual(self.send('me_ap', hanh_dong='tao', ngay=5, giay_moi_ngay=7)['ket_qua'], 'KHONG_HOP_LE')

    def test_end_batch_refused_while_running_then_archived(self):
        self.me_ap.start_batch(self.lich, ngay=3)
        self.bridge.running_probe = lambda: [(123, 'python3 ap_trung.py')]
        self.assertTrue(self.send('me_ap', hanh_dong='ket_thuc')['ket_qua'].startswith('TU_CHOI'))
        self.assertTrue(self.lich.exists())
        self.bridge.running_probe = lambda: []
        self.assertEqual(self.send('me_ap', hanh_dong='ket_thuc')['ket_qua'], 'DA_KET_THUC')
        self.assertFalse(self.lich.exists())
        self.assertEqual(len(list(self.base.glob('trang_thai_me_ap.ket_thuc_*.json'))), 1)  # lưu lại, không xóa
        self.assertFalse(self.store.get('hop_ap_01/lich')['co_me'])

    def test_start_run_happy_path_once(self):
        self.me_ap.start_batch(self.lich, ngay=5)
        reply = self.send('luot', hanh_dong='bat_dau', bo_dieu_khien='rl', phut=30, co_nguoi=True)
        self.assertEqual(reply['ket_qua'], 'DA_BAT_DAU (gia_lap)')
        self.assertEqual(self.launched, [('rl', 30, False)])
        self.assertIn('BAT_DAU_LUOT', self.alerts())
        self.bridge.cycle()
        self.assertEqual(len(self.launched), 1)  # mỗi lệnh chỉ chạy một lần

    def test_start_run_refusals(self):
        self.me_ap.start_batch(self.lich, ngay=5)
        cases = [
            (dict(co_nguoi=False), 'chưa xác nhận có người'),
            (dict(temp=31.5), 'hộp còn 31.5'),
            (dict(temp=None), 'không đọc được DS18B20'),
            (dict(busy=[(77, 'python3 kiem_tra_giu_nhiet.py')]), 'PID 77'),
        ]
        for case, text in cases:
            self.bridge.box_temperature = lambda t=case.get('temp', 26.0): t
            self.bridge.running_probe = lambda b=case.get('busy', []): b
            reply = self.send('luot', hanh_dong='bat_dau', bo_dieu_khien='thermostat', phut=20,
                              co_nguoi=case.get('co_nguoi', True))
            self.assertTrue(reply['ket_qua'].startswith('TU_CHOI'), case)
            self.assertIn(text, reply['ket_qua'], case)
        self.assertEqual(self.launched, [])

    def test_manual_command_writes_file_with_expiry(self):
        self.bridge.running_probe = lambda: [(123, 'python3 ap_trung.py --phut 30')]
        before = time.time()
        reply = self.send('tay', hanh_dong='dat', bong=0, quat=75, thoi_han_s=120)
        self.assertEqual(reply['ket_qua'], 'DA_AP_DUNG')
        data = json.loads(self.tay.read_text(encoding='utf-8'))
        self.assertEqual((data['bong'], data['quat'], data['by']), (0, 75, 'a@b.c'))
        self.assertAlmostEqual(data['ghi_luc'], before, delta=5)
        self.assertAlmostEqual(data['het_han'], before + 120, delta=5)
        self.assertAlmostEqual(reply['het_han_ms'] / 1000, data['het_han'], delta=0.01)
        self.assertIn('CHINH_TAY', self.alerts())
        reply = self.send('tay', hanh_dong='tra_ve')
        self.assertEqual(reply['ket_qua'], 'DA_TRA_VE')
        self.assertEqual(json.loads(self.tay.read_text(encoding='utf-8'))['het_han'], 0)
        self.assertIn('TRA_VE_RL', self.alerts())

    def test_manual_command_refusals(self):
        self.assertIn('không có lượt ap_trung', self.send('tay', hanh_dong='dat', bong=50, quat=100,
                                                          thoi_han_s=60)['ket_qua'])
        self.bridge.running_probe = lambda: [(9, 'python3 kiem_tra_giu_nhiet.py')]
        self.assertTrue(self.send('tay', hanh_dong='dat', bong=50, quat=100, thoi_han_s=60)['ket_qua']
                        .startswith('TU_CHOI'))
        self.bridge.running_probe = lambda: [(123, 'python3 ap_trung.py')]
        for bad in (dict(bong=100, quat=100, thoi_han_s=60), dict(bong=40, quat=100, thoi_han_s=60),
                    dict(bong=50, quat=0, thoi_han_s=60), dict(bong=50, quat=100, thoi_han_s=600),
                    dict(bong=True, quat=100, thoi_han_s=60), dict(bong=False, quat=True, thoi_han_s=60)):
            self.assertEqual(self.send('tay', hanh_dong='dat', **bad)['ket_qua'], 'KHONG_HOP_LE', bad)
        self.assertFalse(self.tay.exists())

    def test_start_run_needs_batch_valid_args_and_fresh_command(self):
        reply = self.send('luot', hanh_dong='bat_dau', bo_dieu_khien='rl', phut=30, co_nguoi=True)
        self.assertIn('chưa có mẻ ấp', reply['ket_qua'])
        self.me_ap.start_batch(self.lich, ngay=5)
        self.assertEqual(self.send('luot', hanh_dong='bat_dau', bo_dieu_khien='rl', phut=25, co_nguoi=True)['ket_qua'],
                         'KHONG_HOP_LE')
        self.assertEqual(self.send('luot', hanh_dong='bat_dau', bo_dieu_khien='pid', phut=30, co_nguoi=True)['ket_qua'],
                         'KHONG_HOP_LE')
        self.bridge.state['luot_handled_ts'] = 0  # như bridge vừa cài lại và thấy lệnh cũ còn trên Firebase
        old = self.send('luot', hanh_dong='bat_dau', bo_dieu_khien='rl', phut=30, co_nguoi=True,
                        ts=cb.now_ms() - 3600_000 + 5)
        self.assertEqual(old['ket_qua'], 'BO_QUA_LENH_CU')
        self.assertEqual(self.launched, [])

    def test_running_controllers_from_proc(self):
        cmds = {'10': 'python3 ap_trung.py --phut 30', '11': 'bash chay_demo.sh', '12': 'python3 cloud_bridge.py chay',
                '13': '/home/pi/.venv/bin/python do_nhiet_hop.py giu'}
        found = cb.running_controllers('/proc', lambda p: list(cmds), lambda pid: cmds[pid])
        self.assertEqual(sorted(pid for pid, _ in found), [10, 13])


class TestUpload(unittest.TestCase):
    @unittest.skipUnless(PILOT.exists(), 'Thiếu pilot 20/11')
    def test_upload_pilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = cb.FileStore(tmp)
            sid, summary, n = cb.upload_completed(store, PILOT)
            self.assertEqual(sid, '20261120_pilot_01')
            self.assertGreater(n, 150)
            session = store.get(f'hop_ap_01/sessions/{sid}')
            self.assertEqual(session['meta']['bo_dieu_khien'], 'Q-learning v2')
            self.assertIn('ket_qua_goc', session['summary'])
            self.assertIsNone(store.get('hop_ap_01/alerts'))  # Tải lịch sử không tạo cảnh báo.


if __name__ == '__main__':
    unittest.main(verbosity=2)
