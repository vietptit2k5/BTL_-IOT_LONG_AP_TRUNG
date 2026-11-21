"""Fixtures hoàn toàn TỔNG HỢP, không phải dữ liệu đo hộp thật."""

import contextlib
import csv
import io
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import do_nhiet_hop as core
import khao_sat_nhiet as survey
import phan_tich_reward as study


def synthetic_csv(path, seconds=600, constant=False):
    """Một plant giả đã biết; dùng kiểm tra số học/parser, không chứng minh RL thực."""
    rng = random.Random(14)
    pairs = [(h, f) for h in (0., .35, .75) for f in (.5, 1.)]
    order = pairs * 3
    rng.shuffle(order)
    temperature, delta, memory = 33., 0., 0.
    def control(t):
        if constant or t < 20:
            return 0., 1., 'SYNTHETIC_baseline'
        if t < 140:
            return .75, 1., 'SYNTHETIC_warm'
        if t >= 560:
            return 0., 1., 'SYNTHETIC_cool'
        index = min(int((t - 140) // 30), len(order) - 1)
        h, f = order[index]
        return h, f, f'SYNTHETIC_probe_{index}'
    records = []
    previous = None
    for t in range(0, seconds, 5):
        h, f, phase = control(t)
        if (h, f, phase) != previous:
            records.append((t, 'COMMAND', temperature, h, f, phase))
            previous = h, f, phase
        before = temperature
        if not constant:
            memory += (h - memory) * (1 - math.exp(-5 / 10))
            delta = (-.025 * (temperature - 30) + .4 * delta + .35 * memory
                     + .02 * (f - .75) + .12 * memory * (f - .75) + rng.gauss(0, .003))
            temperature += delta
        for second in range(5):
            value = before + second / 5 * (temperature - before)
            records.append((t + second, 'MEASUREMENT', round(value / .0625) * .0625, h, f, phase))
    records.append((seconds, 'MEASUREMENT', round(temperature / .0625) * .0625, h, f, phase))
    records.append((seconds, 'END', temperature, 0., 0., 'SYNTHETIC_end'))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=core.CSV_FIELDS)
        writer.writeheader()
        for t, event, temp, h, f, phase in records:
            writer.writerow(dict(timestamp_utc='SYNTHETIC_TEST_ONLY', elapsed_s=t, event=event,
                                 phase=phase, sensor_id='28-000000000001', temperature_c=temp,
                                 temperature_age_s=0, gpio_control=1, lamp_requested_pct=100 * h,
                                 fan_requested_pct=100 * f, lamp_command_pct=100 * h,
                                 fan_command_pct=100 * f, fan_pwm_hz=100, cutoff_c=40,
                                 note='SYNTHETIC FIXTURE, NOT HARDWARE'))


class SurveyTests(unittest.TestCase):
    def test_ten_pairs_are_balanced_and_order_is_reproducible(self):
        first, second = survey.SurveyPolicy(), survey.SurveyPolicy()
        self.assertEqual(first.phases, second.phases)
        trials = [p for p in first.phases if p.name.startswith('thu_')]
        self.assertEqual(len(trials), 20)
        for h in (0, 25, 50, 75, 100):
            for f in (75, 100):
                self.assertEqual(sum((p.lamp, p.fan) == (h, f) for p in trials), 2)
        self.assertTrue(all(p.seconds == 120 for p in trials))
        self.assertEqual(first.nominal_seconds, 2760)
        self.assertLess(first.nominal_seconds, first.seconds)

    def test_warm_and_soft_guard_hysteresis(self):
        policy = survey.SurveyPolicy()
        def call(t, temperature):
            return policy(t, core.Reading(t, temperature))
        self.assertEqual(call(0, 25).lamp, 0)
        self.assertEqual(call(61, 25).lamp, 75)
        self.assertTrue(call(62, 37).phase.startswith('thu_'))
        decision = call(63, 38.1)
        self.assertEqual((decision.lamp, decision.fan), (0, 100))
        self.assertTrue(call(70, 37.5).phase.startswith('bao_ve_mem_'))
        self.assertFalse(call(80, 36.9).phase.startswith('bao_ve_mem_'))
        self.assertEqual(policy.guard_count, 1)

    def test_policy_can_finish_within_hard_time_budget(self):
        policy = survey.SurveyPolicy()
        decision = None
        for i in range(int(policy.seconds) + 1):
            now = float(i)
            decision = policy(now, core.Reading(now, 25))
            if decision is None:
                break
        self.assertTrue(policy.completed)
        self.assertLess(now, policy.seconds)

    def test_longer_observations_do_not_shrink_to_fit_short_budget(self):
        policy = survey.SurveyPolicy(seconds=600, dwell=180)
        trials = [p for p in policy.phases if p.name.startswith('thu_')]
        self.assertTrue(all(p.seconds == 180 for p in trials))
        self.assertEqual(policy.nominal_seconds, 3960)
        self.assertGreater(policy.nominal_seconds, policy.seconds)

    def test_dry_run_does_not_touch_gpio_or_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'must_not_exist'
            with contextlib.redirect_stdout(io.StringIO()), patch.object(core, 'main') as live:
                self.assertEqual(survey.main(['do', '--dry-run', '--out', str(folder)]), 0)
                live.assert_not_called()
            self.assertFalse(folder.exists())

    def test_live_rate_units_and_minimum_span(self):
        self.assertIsNone(core.temperature_rate([(0, 25), (1, 26)]))
        self.assertAlmostEqual(core.temperature_rate([(t, 25 + .01 * t) for t in range(31)]), .6)

    def test_live_wrapper_saves_config_and_calls_shared_safe_controller(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'SYNTHETIC_WRAPPER'
            def fake_live(argv, control_policy, max_session_seconds):
                log = Path(argv[argv.index('--csv') + 1])
                synthetic_csv(log)
                control_policy.completed = True
                control_policy.warm_reached = True
                self.assertIn('--ngat-nhiet', argv)
                self.assertEqual(argv[argv.index('--ngat-nhiet') + 1], '40')
                self.assertEqual(max_session_seconds, core.MAX_SURVEY_SECONDS)
                self.assertEqual(argv[argv.index('--giay') + 1], '5400')
                return 0
            with patch.object(core, 'main', fake_live), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(survey.main(['do', '--chi-do', '--out', str(folder)]), 0)
            self.assertTrue((folder / 'du_lieu.csv').is_file())
            self.assertTrue((folder / 'cau_hinh.json').is_file())
            self.assertTrue((folder / 'phan_tich' / 'KET_QUA.md').is_file())


class IdentificationTests(unittest.TestCase):
    def test_interrupted_segments_do_not_count_as_one_long_observation(self):
        samples = []
        for t in range(150):
            guard = 60 <= t < 90
            samples.append(dict(t=float(t), temperature=35 + .001 * t,
                                phase='bao_ve_mem_1' if guard else 'thu_1_bong_100_quat_75',
                                h=0. if guard else 1., f=1. if guard else .75,
                                rh=0. if guard else 1., rf=1. if guard else .75))
        session = dict(path='SYNTHETIC.csv', samples=samples,
                       commands=[(0, 1, .75), (60, 0, 1), (90, 1, .75)],
                       planned_phases={'thu_1_bong_100_quat_75': dict(seconds=120, h=1., f=.75)},
                       issues=[], sensors=['28-000000000001'], frequencies=[100])
        blocks = study.summarize_phases([session])
        trials = [r for r in blocks if r['phase'].startswith('thu_')]
        self.assertEqual(len(trials), 2)
        self.assertTrue(all(r['continuous_window_complete'] is False for r in trials))
        _, report, _, actions, _ = study.identify([session], 37.5, .5)
        self.assertFalse(report['action_observation_support'][0]['qualified'])
        self.assertNotIn((1., .75), actions)

    def test_full_observation_and_near_flat_hint_are_separate_fields(self):
        samples = [dict(t=float(t), temperature=35 + .001 * t, phase='thu_1', h=.5, f=.75, rh=.5, rf=.75)
                   for t in range(120)]
        session = dict(path='SYNTHETIC.csv', samples=samples,
                       planned_phases={'thu_1': dict(seconds=120, h=.5, f=.75)})
        row = study.summarize_phases([session])[0]
        self.assertTrue(row['continuous_window_complete'])
        self.assertTrue(row['near_flat_hint'])
        self.assertAlmostEqual(row['last_30s_slope_c_per_min'], .06)

    def test_qr_recovers_known_coefficients_and_rejects_rank_deficiency(self):
        rng = random.Random(2)
        rows = [[1.] + [rng.uniform(-3, 3) for _ in range(5)] for _ in range(80)]
        expected = [2., -.3, .4, .8, .1, -.2]
        actual = [sum(a * b for a, b in zip(row, expected)) for row in rows]
        estimated, _ = study.least_squares_qr(rows, actual)
        for a, b in zip(expected, estimated):
            self.assertAlmostEqual(a, b, places=9)
        with self.assertRaises(ValueError):
            study.least_squares_qr([[1, i, i] for i in range(20)], list(range(20)))

    def test_actuator_integration_respects_changes_between_measurements(self):
        self.assertEqual(study.mean_input([(0, 0, 1), (2.5, 1, .5)], 0, 5), (.5, .75))

    def test_synthetic_plant_has_held_out_fit_and_rising_falling_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'SYNTHETIC.csv'
            synthetic_csv(path)
            session = study.read_log(path)
            summaries = study.summarize_phases([session])
            self.assertTrue(any(r['slope_c_per_min'] is not None and r['slope_c_per_min'] > .1 for r in summaries))
            self.assertTrue(any(r['slope_c_per_min'] is not None and r['slope_c_per_min'] < -.1 for r in summaries))
            model, report, issues, actions, rows = study.identify([session], 37.5, .5)
            self.assertIsNotNone(model, report)
            self.assertEqual(len(actions), 6)
            self.assertTrue(rows)
            self.assertLess(report['selected']['test']['rollout_30s_rmse_c'], .3)

    def test_changing_test_data_does_not_change_selected_model(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'SYNTHETIC.csv'
            synthetic_csv(path)
            session = study.read_log(path)
            model1, report1, _, _, _ = study.identify([session], 37.5, .5)
            for row in session['samples']:
                if row['t'] >= 500:
                    row['temperature'] += 3
            model2, report2, _, _, _ = study.identify([session], 37.5, .5)
            self.assertIsNotNone(model1)
            self.assertIsNotNone(model2)
            self.assertEqual(model1.coefficients, model2.coefficients)
            self.assertEqual(model1.tau, model2.tau)
            self.assertGreater(report2['selected']['test']['rollout_30s_rmse_c'], report1['selected']['test']['rollout_30s_rmse_c'])

    def test_insufficient_data_does_not_export_qtable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / 'SYNTHETIC_constant.csv'
            synthetic_csv(path, constant=True)
            report = study.analyze([path], folder / 'analysis', target=37.5, band=.5, episodes=10)
            self.assertEqual(report['status'], 'NEEDS_MORE_MEASUREMENTS')
            self.assertFalse((folder / 'analysis' / 'qtable_UNG_VIEN_MO_PHONG.json').exists())
            self.assertTrue((folder / 'analysis' / 'dap_ung_tung_buoc.csv').is_file())

    def test_offline_cli_does_not_access_hardware(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / 'SYNTHETIC.csv'
            synthetic_csv(path)
            with contextlib.redirect_stdout(io.StringIO()), patch.object(core, 'main') as live:
                self.assertEqual(survey.main(['phan-tich', '--log', str(path), '--out', str(folder / 'offline'), '--episodes', '10']), 0)
                live.assert_not_called()
            self.assertTrue((folder / 'offline' / 'phan_tich' / 'thu_he_so_reward.csv').is_file())
            self.assertTrue((folder / 'offline' / 'phan_tich' / 'so_sanh_MO_PHONG.csv').is_file())

    def test_normal_budget_end_is_not_confused_with_a_hardware_fault(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / 'SYNTHETIC.csv'
            synthetic_csv(path)
            manifest = folder / 'cau_hinh.json'
            manifest.write_text(json.dumps(dict(schedule={'completed_schedule': False}, hardware_program_exit_code=0)), encoding='utf-8')
            session = study.read_log(path)
            self.assertFalse(session['issues'])
            self.assertTrue(session['warnings'])
            manifest.write_text(json.dumps(dict(schedule={'completed_schedule': False}, hardware_program_exit_code=1)), encoding='utf-8')
            self.assertTrue(study.read_log(path)['issues'])

    def test_reward_penalizes_heat_and_does_not_call_duty_energy(self):
        weights = dict(hot=3., duty=.05, switch=.03)
        at_target = study.reward_value(37.5, (.35, .5), (.35, .5), 37.5, .5, weights)
        too_hot = study.reward_value(39, (.35, .5), (.35, .5), 37.5, .5, weights)
        self.assertLess(too_hot, at_target)


class RewardSelectionTests(unittest.TestCase):
    def test_uses_average_seeds_and_never_selects_weights_using_test(self):
        def fake_train(model, rows, actions, target, band, weights, seed, episodes):
            return (weights, seed), None
        def cases(model, rows, target, seed, number):
            return [seed]
        def metrics(error):
            return dict(mae_c=error, in_band_pct=95., hot_area_c_min=0., mean_duty_proxy=.5,
                        mean_change=.1, guard_rate=0., fallback_rate=0., unsupported_fraction=0., max_temperature_c=38.)
        def evaluate(model, actions, case_seed, target, band, q=None, visits=None, baseline=None):
            if baseline is not None:
                return metrics(.6)
            weights, seed = q
            if case_seed[0] == 905:
                return metrics(.01 if weights['hot'] == 1 else .9)
            if weights['hot'] == 1:
                return metrics(0 if seed == 11 else 2.)
            return metrics(.3 if weights['hot'] == 3 else .5)
        with patch.object(study, 'train_q', fake_train), patch.object(study, 'scenarios', cases), \
             patch.object(study, 'evaluate', evaluate), patch.object(study, 'rollout', return_value=(metrics(0), [])), \
             contextlib.redirect_stdout(io.StringIO()):
            result, policies, _ = study.tune_reward(None, [], [(0, .5), (.75, 1)], 37.5, .5, 10)
        self.assertEqual(result['selected']['weights']['hot'], 3)
        self.assertEqual(len(policies), 2)
        self.assertEqual(result['test_mean']['mae_c'], .9)


if __name__ == '__main__':
    unittest.main()
