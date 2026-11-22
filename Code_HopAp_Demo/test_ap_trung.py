#!/usr/bin/env python3
"""Kiểm thử me_ap.py (lịch) và ap_trung.py (policy 3 giai đoạn). Không GPIO, không mạng."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import ap_trung
import me_ap
from thu_rl_du_lieu_moi import read_package

HERE = Path(__file__).resolve().parent
WALL0 = 1_800_000_000.0


class TestLich(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'lich.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_stage_boundaries(self):
        expected = {1: (1, 37.8), 10: (1, 37.8), 11: (2, 37.5), 17: (2, 37.5), 18: (3, 37.2), 21: (3, 37.2)}
        for day, (stage, target) in expected.items():
            s = me_ap.stage_for_day(day)
            self.assertEqual((s['giai_doan'], s['muc_tieu_c']), (stage, target), day)
        for bad in (0, 22, 1.5, True, '3'):
            with self.assertRaises(me_ap.LichError):
                me_ap.stage_for_day(bad)

    def test_start_and_set_day_keep_advancing(self):
        me_ap.start_batch(self.path, now=WALL0, ngay=5)
        self.assertEqual(me_ap.current(me_ap.load(self.path), WALL0)['ngay'], 5)
        self.assertEqual(me_ap.current(me_ap.load(self.path), WALL0 + 86400)['ngay'], 6)  # tự tăng
        me_ap.set_day(12, self.path, now=WALL0 + 100)
        info = me_ap.current(me_ap.load(self.path), WALL0 + 100)
        self.assertEqual((info['ngay'], info['giai_doan'], info['muc_tieu_c']), (12, 2, 37.5))
        self.assertEqual(me_ap.load(self.path)['nguon'], 'dong_lenh')

    def test_demo_batch_starts_paused_and_resumes_where_it_stopped(self):
        me_ap.start_batch(self.path, now=WALL0, ngay=3, giay_moi_ngay=60)
        info = me_ap.current(me_ap.load(self.path), WALL0 + 600)      # 10 phút sau: vẫn ngày 3 vì đang dừng
        self.assertEqual((info['ngay'], info['tam_dung']), (3, True))
        me_ap.resume(self.path, now=WALL0 + 600)
        self.assertEqual(me_ap.current(me_ap.load(self.path), WALL0 + 600 + 125)['ngay'], 5)  # +2 ngày sau 125 s
        me_ap.pause(self.path, now=WALL0 + 725)
        self.assertEqual(me_ap.current(me_ap.load(self.path), WALL0 + 5000)['ngay'], 5)        # dừng lại: giữ ngày 5
        me_ap.set_day(12, self.path, now=WALL0 + 5000)                                        # đổi ngày khi đang dừng
        state = me_ap.load(self.path)
        self.assertEqual((me_ap.current(state, WALL0 + 9000)['ngay'], me_ap.is_paused(state)), (12, True))

    def test_real_time_batch_never_pauses(self):
        me_ap.start_batch(self.path, now=WALL0, ngay=5)
        me_ap.pause(self.path, now=WALL0 + 10)
        self.assertFalse(me_ap.is_paused(me_ap.load(self.path)))
        self.assertEqual(me_ap.current(me_ap.load(self.path), WALL0 + 86400)['ngay'], 6)

    def test_compressed_demo_and_end_of_schedule(self):
        me_ap.start_batch(self.path, now=WALL0, ngay=1, giay_moi_ngay=60, paused=False)
        state = me_ap.load(self.path)
        self.assertEqual(me_ap.current(state, WALL0 + 60 * 10)['ngay'], 11)
        self.assertTrue(me_ap.current(state, WALL0 + 60 * 10)['rut_gon'])
        late = me_ap.current(state, WALL0 + 60 * 30)
        self.assertEqual((late['ngay'], late['giai_doan'], late['het_lich']), (21, 3, True))

    def test_invalid_files(self):
        with self.assertRaises(me_ap.LichError):
            me_ap.load(self.path)  # chưa có
        self.path.write_text('{hỏng', encoding='utf-8')
        with self.assertRaises(me_ap.LichError):
            me_ap.load(self.path)
        with self.assertRaises(me_ap.LichError):
            me_ap.start_batch(self.path, now=WALL0, giay_moi_ngay=5)  # quá nhanh

    def test_cli(self):
        me_ap.start_batch(self.path, now=WALL0)
        self.assertEqual(me_ap.main(['--file', str(self.path), 'dat-ngay', '18']), 0)
        self.assertEqual(me_ap.current(me_ap.load(self.path))['giai_doan'], 3)
        self.assertEqual(me_ap.main(['--file', str(self.path), 'dat-ngay', '30']), 1)


class TestPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = read_package(HERE / 'goi_rl_moi_20261120.json')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lich = Path(self.tmp.name) / 'lich.json'
        self.tay = Path(self.tmp.name) / 'lenh_tay.json'
        self.now = 0.0
        me_ap.start_batch(self.lich, now=self.wall(), ngay=5)

    def tearDown(self):
        self.tmp.cleanup()

    def wall(self):
        return WALL0 + self.now

    def make(self, package=None, minutes=30):
        p = ap_trung.ApTrungPolicy(package or self.package, minutes, self.lich, wall_clock=self.wall,
                                   tay_path=self.tay)
        p.bind_sensor(self.package['sensor_id'])
        p.observe_output(self.now, 0, 100)
        return p

    def call(self, p, temp, dt=5.0):
        self.now += dt
        dec = p(self.now, SimpleNamespace(temperature=temp, at=self.now))
        if dec is not None:
            p.observe_output(self.now, dec.lamp, dec.fan)
        return dec

    def test_refuses_hot_box_and_missing_schedule(self):
        with self.assertRaises(ValueError):
            self.call(self.make(), 31.0)
        self.lich.unlink()
        with self.assertRaises(me_ap.LichError):
            ap_trung.ApTrungPolicy(self.package, 30, self.lich, wall_clock=self.wall)

    def test_warmup_then_q_with_stage_phase(self):
        p = self.make()
        dec = self.call(p, 28.0)
        self.assertEqual((dec.phase, dec.lamp, dec.fan), ('lam_am_ap', 75, 100))
        dec = self.call(p, 37.2)  # < 37,8 − 0,5 = 37,3: vẫn làm ấm
        self.assertEqual(dec.phase, 'lam_am_ap')
        dec = self.call(p, 37.4)
        self.assertEqual(dec.phase, 'ap_ngay05_gd1')

    def test_changing_day_changes_target_and_phase(self):
        p = self.make()
        self.call(p, 28.0)
        self.call(p, 37.8)
        self.assertEqual(p.info['muc_tieu_c'], 37.8)
        me_ap.set_day(19, self.lich, now=self.wall())
        dec = self.call(p, 37.8)
        self.assertEqual(p.info['muc_tieu_c'], 37.2)
        self.assertEqual(dec.phase, 'ap_ngay19_gd3')
        self.assertEqual(dec.lamp, 0)  # 0,6 °C trên mốc mới: không sưởi
        self.assertEqual(p.stats['chuyen_giai_doan'], 1)
        self.assertEqual(p.history[-1]['ngay'], 19)

    def test_guard_is_fixed_and_independent_of_day(self):
        p = self.make()
        self.call(p, 28.0)
        self.call(p, 37.8)
        dec = self.call(p, 38.3)
        self.assertEqual((dec.lamp, dec.fan), (0, 100))
        self.assertTrue(dec.phase.endswith('_bao_ve'))
        dec = self.call(p, 37.9)  # chưa về 37,8: vẫn bảo vệ
        self.assertTrue(dec.phase.endswith('_bao_ve'))
        dec = self.call(p, 37.8)
        self.assertFalse(dec.phase.endswith('_bao_ve'))

    def test_broken_schedule_file_keeps_last_target(self):
        p = self.make()
        self.call(p, 28.0)
        self.call(p, 37.8)
        self.lich.write_text('{hỏng', encoding='utf-8')
        dec = self.call(p, 37.8)
        self.assertEqual(p.info['muc_tieu_c'], 37.8)
        self.assertTrue(dec.phase.startswith('ap_ngay05_gd1'))
        self.assertEqual(p.stats['loi_doc_lich'], 1)

    def test_unseen_state_cools_above_and_warms_below(self):
        blind = copy.deepcopy(self.package)
        blind['policy']['visits'] = [[0] * 9 for _ in range(2430)]
        p = self.make(blind)
        self.call(p, 28.0)
        dec = self.call(p, 37.9)
        self.assertEqual((dec.lamp, dec.fan), (0, 100))
        self.assertEqual(p.stats['du_phong_lam_mat'], 1)
        dec = self.call(p, 37.6)  # dưới mốc 37,8, chưa học: làm ấm phục hồi, không đoán
        self.assertTrue(dec.phase.endswith('_phuc_hoi'))

    def test_thermostat_follows_schedule_with_same_phases(self):
        p = ap_trung.ApTrungPolicy(self.package, 30, self.lich, wall_clock=self.wall, controller='thermostat')
        p.bind_sensor(self.package['sensor_id'])
        p.observe_output(self.now, 0, 100)
        self.assertEqual(self.call(p, 28.0).phase, 'lam_am_ap')
        dec = self.call(p, 37.5)                       # dưới 37,8 − 0,1: bật sưởi tối đa
        self.assertEqual((dec.phase, dec.lamp), ('ap_ngay05_gd1', 100))
        dec = self.call(p, 37.95)                      # trên 37,8 + 0,1: tắt sưởi
        self.assertEqual(dec.lamp, 0)
        me_ap.set_day(19, self.lich, now=self.wall())
        dec = self.call(p, 37.1)                       # mốc mới 37,2: 37,1 nằm trong ±0,1 → giữ trạng thái tắt
        self.assertEqual((dec.phase, dec.lamp), ('ap_ngay19_gd3', 0))
        dec = self.call(p, 37.05)                      # dưới 37,1: bật lại
        self.assertEqual(dec.lamp, 100)
        self.assertEqual(p.metadata()['bo_dieu_khien'], 'Thermostat 3 giai đoạn')
        dec = self.call(p, 38.4)                       # bảo vệ chung vẫn ưu tiên
        self.assertTrue(dec.phase.endswith('_bao_ve'))

    def test_demo_schedule_frozen_during_warmup_then_runs_and_pauses_at_end(self):
        me_ap.start_batch(self.lich, now=self.wall(), ngay=1, giay_moi_ngay=60)   # demo: tạm dừng
        p = self.make(minutes=2)
        for _ in range(60):                                                       # 5 phút làm ấm
            self.assertEqual(self.call(p, 30.0).phase, 'lam_am_ap')
        self.assertEqual(p.info['ngay'], 1)                                       # lịch không trôi khi làm ấm
        self.assertEqual(self.call(p, 37.4).phase, 'ap_ngay01_gd1')               # RL nhận: lịch chạy tiếp
        self.assertFalse(me_ap.is_paused(me_ap.load(self.lich)))
        for _ in range(14):
            dec = self.call(p, 37.8)
        self.assertEqual(p.info['ngay'], 2)                                       # ~70 s RL = sang ngày 2
        while dec is not None:
            dec = self.call(p, 37.8)
        self.assertTrue(me_ap.is_paused(me_ap.load(self.lich)))                   # hết lượt: lịch dừng lại
        self.now += 3600
        self.assertEqual(me_ap.current(me_ap.load(self.lich), self.wall())['ngay'], 3)

    def test_rejects_unknown_controller(self):
        with self.assertRaises(ValueError):
            ap_trung.ApTrungPolicy(self.package, 30, self.lich, wall_clock=self.wall, controller='pid')

    def write_manual(self, lamp, fan, seconds, by='a@b.c'):
        self.tay.write_text(json.dumps({'bong': lamp, 'quat': fan, 'het_han': self.wall() + seconds, 'by': by,
                                        'ghi_luc': self.wall()}), encoding='utf-8')

    def test_manual_override_expires_and_returns_to_rl(self):
        p = self.make()
        self.call(p, 28.0)
        self.call(p, 37.8)
        self.write_manual(0, 75, 60)
        for _ in range(3):
            dec = self.call(p, 37.8)
            self.assertEqual((dec.phase, dec.lamp, dec.fan), ('ap_ngay05_gd1_tay', 0, 75))
        self.assertIn('a@b.c', dec.note)
        self.assertEqual(p.stats['chinh_tay'], 1)  # một lần chỉnh tay dù kéo dài nhiều bước
        self.now += 60  # hết hạn: RL quyết định lại
        dec = self.call(p, 37.8)
        self.assertEqual(dec.phase, 'ap_ngay05_gd1')
        self.assertFalse(p.manual_active)

    def test_manual_return_now_and_rejects_unsurveyed_pairs(self):
        p = self.make()
        self.call(p, 28.0)
        self.call(p, 37.8)
        for lamp, fan in ((100, 100), (50, 0), (30, 75)):  # không thuộc 9 hành động đã khảo sát
            self.write_manual(lamp, fan, 120)
            self.assertFalse(self.call(p, 37.8).phase.endswith('_tay'), (lamp, fan))
        self.write_manual(100, 75, 120)
        self.assertTrue(self.call(p, 37.8).phase.endswith('_tay'))
        self.tay.write_text('{"bong": 0, "quat": 100, "het_han": 0}', encoding='utf-8')  # trả về RL
        self.assertFalse(self.call(p, 37.8).phase.endswith('_tay'))
        self.tay.write_text('{hỏng', encoding='utf-8')
        self.assertFalse(self.call(p, 37.8).phase.endswith('_tay'))

    def test_manual_command_from_previous_run_is_ignored(self):
        self.write_manual(0, 75, 300)  # ghi lúc lượt trước còn chạy, vẫn còn hạn
        self.now += 10
        p = self.make()
        self.call(p, 28.0)
        self.call(p, 37.8)
        self.assertFalse(self.call(p, 37.8).phase.endswith('_tay'))
        self.write_manual(0, 75, 300)
        self.assertTrue(self.call(p, 37.8).phase.endswith('_tay'))

    def test_guard_beats_manual_and_warmup_ignores_it(self):
        p = self.make()
        self.write_manual(100, 75, 300)
        self.assertEqual(self.call(p, 28.0).phase, 'lam_am_ap')  # chưa giữ nhiệt: không nhận lệnh tay
        self.call(p, 37.8)
        self.assertTrue(self.call(p, 37.9).phase.endswith('_tay'))
        dec = self.call(p, 38.3)
        self.assertEqual((dec.lamp, dec.fan), (0, 100))
        self.assertTrue(dec.phase.endswith('_bao_ve'))

    def test_batch_session_limits_and_warm_start(self):
        with self.assertRaises(ValueError):
            ap_trung.ApTrungPolicy(self.package, ap_trung.MAX_MINUTES_ME, self.lich, wall_clock=self.wall)
        p = ap_trung.ApTrungPolicy(self.package, ap_trung.MAX_MINUTES_ME, self.lich, wall_clock=self.wall,
                                   check_start_temperature=False, max_minutes=ap_trung.MAX_MINUTES_ME,
                                   tay_path=self.tay)
        p.bind_sensor(self.package['sensor_id'])
        p.observe_output(self.now, 0, 100)
        dec = self.call(p, 37.6)  # phiên nối tiếp: hộp đang ấm, giao ngay cho RL, không đòi ≤ 30 °C
        self.assertEqual(dec.phase, 'ap_ngay05_gd1')

    def test_finishes_after_requested_minutes(self):
        p = self.make(minutes=1)
        self.call(p, 28.0)
        self.call(p, 37.8)
        for _ in range(11):
            self.assertIsNotNone(self.call(p, 37.8))
        self.assertIsNone(self.call(p, 37.8))
        self.assertTrue(p.completed)
        json.dumps(p.metadata())


if __name__ == '__main__':
    unittest.main(verbosity=2)
