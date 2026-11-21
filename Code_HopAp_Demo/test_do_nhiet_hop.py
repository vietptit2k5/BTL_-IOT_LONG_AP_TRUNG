"""Kiểm tra điều khiển bằng đầu ra giả; không truy cập GPIO thật."""
import contextlib
import csv
import io
from pathlib import Path
import queue
import signal
import tempfile
import types
import unittest
from unittest.mock import patch

import do_nhiet_hop as app


class FakeDevice:
    def __init__(self):
        self.value = 0
        self.closed = False
        self.fail_off = False

    def off(self):
        if self.fail_off:
            raise RuntimeError('output off failed')
        self.value = 0

    def close(self):
        self.closed = True


class FakeOutputs(app.Outputs):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.opened = False
        self.trace = []
        self.instances.append(self)

    def open(self):
        self.opened = True
        if self.enabled:
            self.lamp, self.fan, self.factory = FakeDevice(), FakeDevice(), FakeDevice()

    def _apply(self, lamp, fan):
        super()._apply(lamp, fan)
        self.trace.append((lamp, fan))


class Clock:
    def __init__(self):
        self.now = 0.0
        self.on_sleep = lambda: None

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.on_sleep()


class FakeWorker:
    def __init__(self, path, clock, scenario):
        self.messages = queue.Queue()
        self.clock, self.scenario = clock, scenario
        self.next_read = 1.0
        self.closed = self.fired = False

    def start(self):
        if self.scenario != 'no_read':
            self.messages.put(app.Reading(self.clock.now, 40.0 if self.scenario == 'hot_start' else 25.0))
        self.clock.on_sleep = self.advance

    def advance(self):
        now = self.clock.now
        if not self.fired and now >= 1.5:
            if self.scenario == 'crc':
                self.messages.put(app.Reading(now, None, 'CRC failure'))
                self.fired = True
            elif self.scenario == 'hot':
                self.messages.put(app.Reading(now, 40.0))
                self.fired = True
            elif self.scenario == 'signal':
                self.fired = True
                raise app.SignalStop(signal.SIGTERM)
        if self.scenario not in ('stale', 'no_read') and not self.fired and now >= self.next_read:
            self.messages.put(app.Reading(now, 25.0 if self.scenario == 'stable' else 25.0 + now / 10))
            self.next_read = now + 1

    def close(self):
        self.closed = True


class SensorTests(unittest.TestCase):
    def test_valid_and_negative_temperature(self):
        self.assertEqual(app.parse_temperature('aa crc=00 YES\naa t=25375\n'), 25.375)
        self.assertEqual(app.parse_temperature('aa YES\naa t=-1250\n'), -1.25)

    def test_bad_crc_sentinel_and_missing_data(self):
        for text in ('', 'aa NO\naa t=25000', 'aa NOTYES\naa t=25000',
                     'aa YES\naa', 'aa YES\naa t=85000', 'aa YES\naa t=-127000'):
            with self.subTest(text=text), self.assertRaises(app.SensorError):
                app.parse_temperature(text)

    def test_multiple_sensors_must_be_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(app.SensorError):
                app.find_sensor(root=root)
            for code in ('28-000000000001', '28-000000000002'):
                (root / code).mkdir()
                (root / code / 'w1_slave').touch()
            with self.assertRaises(app.SensorError):
                app.find_sensor(root=root)
            self.assertEqual(app.find_sensor('28-000000000001', root).parent.name, '28-000000000001')

    def test_worker_reports_bad_read_instead_of_reusing_temperature(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'w1_slave'
            path.write_text('aa NO\naa t=25000', encoding='ascii')
            worker = app.SensorWorker(path)
            worker.start()
            reading = worker.messages.get(timeout=2)
            worker.close()
            self.assertIsNone(reading.temperature)
            self.assertTrue(reading.error)


class OutputTests(unittest.TestCase):
    def test_kick_then_both_pwm_and_invalid_command(self):
        outputs = FakeOutputs(True)
        outputs.open()
        outputs.command(35, 75, 0)
        self.assertEqual((outputs.lamp.value, outputs.fan.value), (0, 1))
        outputs.tick(1.0)
        self.assertEqual((outputs.lamp.value, outputs.fan.value), (.35, .75))
        for lamp, fan in ((float('nan'), 100), (25, 0), (101, 100), (0, -1)):
            with self.assertRaises(ValueError):
                outputs.command(lamp, fan, 2)
            self.assertEqual((outputs.requested_lamp, outputs.requested_fan), (35, 75))
        app.apply_text('tat', outputs, 3)
        self.assertEqual((outputs.lamp.value, outputs.fan.value), (0, 0))

    def test_cleanup_attempts_fan_and_all_closes_even_if_lamp_off_fails(self):
        outputs = FakeOutputs(True)
        outputs.open()
        outputs.lamp.fail_off = True
        outputs.fan.value = 1
        self.assertTrue(outputs.shutdown())
        self.assertEqual(outputs.fan.value, 0)
        self.assertTrue(all(item.closed for item in (outputs.lamp, outputs.fan, outputs.factory)))

    def test_partial_initialization_is_cleaned(self):
        lamp, factory = FakeDevice(), FakeDevice()
        gpiozero = types.ModuleType('gpiozero')
        pins = types.ModuleType('gpiozero.pins')
        lgpio = types.ModuleType('gpiozero.pins.lgpio')
        lgpio.LGPIOFactory = lambda **kwargs: factory
        calls = []
        def create(*args, **kwargs):
            calls.append(args)
            if len(calls) == 2:
                raise RuntimeError('fan initialization failed')
            return lamp
        gpiozero.PWMOutputDevice = create
        with patch.dict('sys.modules', {'gpiozero': gpiozero, 'gpiozero.pins': pins,
                                       'gpiozero.pins.lgpio': lgpio}):
            outputs = app.Outputs(True)
            with self.assertRaises(RuntimeError):
                outputs.open()
            self.assertEqual(outputs.shutdown(), [])
        self.assertTrue(lamp.closed and factory.closed)


class SessionTests(unittest.TestCase):
    def run_case(self, scenario='normal', mode='giu', extra=(), stdin='', oled=False,
                 control_policy=None, duration=4, max_session_seconds=app.MAX_SECONDS):
        clock = Clock()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            sensor = folder / '28-000000000001' / 'w1_slave'
            sensor.parent.mkdir()
            sensor.touch()
            logfile = folder / 'measure.csv'
            argv = [mode, '--csv', str(logfile), *extra]
            if not oled:
                argv.append('--khong-oled')
            if mode == 'kich-ban':
                plan = folder / 'plan.csv'
                plan.write_text('ten,giay,bong_pct,quat_pct\nheat,1.2,25,100\ncool,1.2,0,75\n', encoding='utf-8')
                argv += ['--tep', str(plan)]
            else:
                argv += ['--giay', str(duration)]
            if mode == 'giu':
                argv += ['--bong', '35', '--quat', '75']
            workers = []
            def make_worker(path):
                result = FakeWorker(path, clock, scenario)
                workers.append(result)
                return result
            def make_thread(*, target, args, daemon):
                return types.SimpleNamespace(start=lambda: target(*args))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                 patch.object(app.time, 'monotonic', clock.monotonic), \
                 patch.object(app.time, 'sleep', clock.sleep), \
                 patch.object(app, 'COOLDOWN_SECONDS', .1), \
                 patch.object(app, 'find_sensor', return_value=sensor), \
                 patch.object(app, 'Outputs', FakeOutputs), \
                 patch.object(app, 'SensorWorker', make_worker), \
                 patch.object(app.threading, 'Thread', make_thread), \
                 patch.object(app.sys, 'stdin', io.StringIO(stdin)):
                result = app.main(argv, control_policy=control_policy, max_session_seconds=max_session_seconds)
            with logfile.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            outputs = FakeOutputs.instances[-1]
            self.assertTrue(workers[0].closed)
            if outputs.enabled:
                self.assertEqual((outputs.lamp.value, outputs.fan.value), (0, 0))
                self.assertTrue(outputs.lamp.closed and outputs.fan.closed and outputs.factory.closed)
            return result, rows, outputs, clock.now

    def test_normal_session_records_requested_and_kick_pwm_separately(self):
        result, rows, outputs, _ = self.run_case()
        self.assertEqual(result, 0)
        commands = [row for row in rows if row['event'] == 'COMMAND']
        self.assertEqual(commands[0]['lamp_requested_pct'], '35')
        self.assertEqual(commands[0]['lamp_command_pct'], '0')
        self.assertEqual(commands[0]['fan_command_pct'], '100')
        self.assertTrue(any(row['lamp_command_pct'] == '35' and row['fan_command_pct'] == '75' for row in rows))
        self.assertEqual(rows[-1]['event'], 'END')

    def test_crc_overtemperature_and_stale_stop_heating(self):
        for scenario in ('crc', 'hot', 'stale'):
            with self.subTest(scenario=scenario):
                result, rows, outputs, elapsed = self.run_case(scenario)
                self.assertEqual(result, 1)
                self.assertTrue(outputs.had_heat)
                self.assertTrue(any(row['event'] == 'ERROR' for row in rows))
                self.assertTrue(all(row['lamp_command_pct'] == '0' for row in rows if row['event'] == 'ERROR'))
                self.assertLess(elapsed, 3.3 if scenario == 'stale' else 1.8)

    def test_no_initial_read_or_hot_start_never_allows_heating(self):
        for scenario in ('no_read', 'hot_start'):
            with self.subTest(scenario=scenario):
                result, _, outputs, elapsed = self.run_case(scenario)
                self.assertEqual(result, 1)
                self.assertFalse(outputs.had_heat)
                self.assertLess(elapsed, 3.2)

    def test_plan_changes_both_channels_at_boundary(self):
        result, rows, _, elapsed = self.run_case(mode='kich-ban')
        self.assertEqual(result, 0)
        commands = [row for row in rows if row['event'] == 'COMMAND' and row['phase'] != 'giu_quat_cuoi']
        self.assertEqual([(r['phase'], r['lamp_requested_pct'], r['fan_requested_pct']) for r in commands],
                         [('heat', '25', '100'), ('cool', '0', '75')])
        self.assertLess(elapsed, 2.7)

    def test_logging_error_turns_heater_off_before_error_record(self):
        original = app.Recorder.row
        failed = []
        def row(recorder, event, *args, **kwargs):
            if event == 'MEASUREMENT' and recorder.outputs.lamp_pct > 0 and not failed:
                failed.append(True)
                raise OSError('simulated CSV failure')
            if event == 'ERROR':
                self.assertEqual(recorder.outputs.lamp.value, 0)
            return original(recorder, event, *args, **kwargs)
        with patch.object(app.Recorder, 'row', row):
            result, _, outputs, _ = self.run_case()
        self.assertEqual(result, 1)
        self.assertTrue(failed and outputs.had_heat)

    def test_signal_also_shuts_down(self):
        result, _, _, _ = self.run_case('signal')
        self.assertEqual(result, 128 + signal.SIGTERM)

    def test_auto_policy_cannot_bypass_hot_sensor_guard(self):
        decisions = []
        def policy(now, reading):
            decisions.append(reading.temperature)
            return app.AutoDecision('auto_test', 35, 100)
        result, rows, outputs, _ = self.run_case('hot', control_policy=policy)
        self.assertEqual(result, 1)
        self.assertTrue(outputs.had_heat)
        self.assertNotIn(40, decisions)
        self.assertTrue(any(row['phase'] == 'auto_test' for row in rows))

    def test_auto_policy_finishes_and_turns_outputs_off(self):
        def policy(now, reading):
            return app.AutoDecision('auto_test', 25, 100) if now < 1.5 else None
        result, rows, _, elapsed = self.run_case(control_policy=policy)
        self.assertEqual(result, 0)
        self.assertLess(elapsed, 2)
        self.assertTrue(any(row['event'] == 'STOP' for row in rows))

    def test_auto_output_observer_sees_applied_kick_and_never_sees_hot_sensor(self):
        observations=[];decisions=[]
        class Policy:
            def observe_output(self,now,lamp,fan):
                observations.append((now,lamp,fan))
            def __call__(self,now,reading):
                decisions.append(reading.temperature)
                return app.AutoDecision('observer_test',35,100)
        result,_,_,_=self.run_case('stable',control_policy=Policy(),duration=3)
        self.assertEqual(result,0)
        self.assertTrue(any(lamp==0 and fan==100 for _,lamp,fan in observations))
        self.assertTrue(any(lamp==35 and fan==100 for _,lamp,fan in observations))
        decisions.clear()
        result,_,_,_=self.run_case('hot',control_policy=Policy())
        self.assertEqual(result,1)
        self.assertNotIn(40,decisions)

    def test_extended_survey_really_runs_beyond_ten_minutes_with_fresh_sensor(self):
        def policy(now, reading):
            return app.AutoDecision('auto_long_test', 25, 100) if now < 620 else None
        result, rows, outputs, elapsed = self.run_case(
            'stable', control_policy=policy, duration=650, max_session_seconds=app.MAX_SURVEY_SECONDS)
        self.assertEqual(result, 0)
        self.assertGreaterEqual(elapsed, 620)
        self.assertLess(elapsed, 621)
        self.assertTrue(any(float(row['elapsed_s']) > 600 for row in rows))
        self.assertTrue(outputs.lamp.closed and outputs.fan.closed)

    def test_oled_gets_temperature_and_fault_after_heater_off(self):
        displays = []
        class Display:
            def __init__(self, **kwargs):
                self.frames = []
                self.closed = False
                displays.append(self)
            def start(self):
                pass
            def update(self, frame):
                self.frames.append(frame)
            def close(self):
                self.closed = True
        with patch.object(app, 'OLEDDisplay', Display):
            result, _, _, _ = self.run_case('hot', oled=True)
        self.assertEqual(result, 1)
        display = displays[-1]
        self.assertTrue(display.closed)
        self.assertTrue(any(frame.temperature == 25 for frame in display.frames))
        fault = [frame for frame in display.frames if frame.status == 'OVER TEMP']
        self.assertTrue(fault)
        self.assertTrue(all(frame.lamp == 0 for frame in fault))

    def test_read_only_does_not_open_gpio_or_invent_pwm(self):
        result, rows, outputs, _ = self.run_case(mode='doc')
        self.assertEqual(result, 0)
        self.assertIsNone(outputs.lamp)
        self.assertTrue(all(row['gpio_control'] == '0' and row['lamp_command_pct'] == '' for row in rows))

    def test_eof_in_manual_mode_stops(self):
        result, rows, _, elapsed = self.run_case(mode='tay')
        self.assertEqual(result, 0)
        self.assertTrue(any(row['event'] == 'STOP' and 'EOF' in row['note'] for row in rows))
        self.assertLess(elapsed, 4)

    def test_missing_sensor_does_not_initialize_outputs(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
             patch.object(app, 'find_sensor', side_effect=app.SensorError('missing')), \
             patch.object(app.Outputs, 'open') as opened:
            self.assertEqual(app.main(['giu', '--bong', '25', '--quat', '100', '--khong-oled']), 1)
            opened.assert_not_called()

    def test_existing_csv_is_preserved_before_gpio_initialization(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            sensor = folder / '28-000000000001' / 'w1_slave'
            sensor.parent.mkdir()
            sensor.touch()
            logfile = folder / 'existing.csv'
            logfile.write_text('original data', encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                 patch.object(app, 'find_sensor', return_value=sensor), \
                 patch.object(app.Outputs, 'open') as opened:
                self.assertEqual(app.main(['giu', '--bong', '25', '--quat', '100', '--csv', str(logfile), '--khong-oled']), 1)
                opened.assert_not_called()
            self.assertEqual(logfile.read_text(encoding='utf-8'), 'original data')


class ArgumentTests(unittest.TestCase):
    def test_only_explicit_auto_policy_can_extend_session_duration(self):
        args = ['giu', '--bong', '0', '--quat', '100', '--giay', '5400', '--dry-run']
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
             patch.object(app, 'Outputs') as outputs:
            with self.assertRaises(SystemExit):
                app.main(args)
            with self.assertRaises(SystemExit):
                app.main(args, max_session_seconds=app.MAX_SURVEY_SECONDS)
            self.assertEqual(app.main(args, control_policy=lambda now, reading: None,
                                      max_session_seconds=app.MAX_SURVEY_SECONDS), 0)
            with self.assertRaises(SystemExit):
                app.main(args, control_policy=lambda now, reading: None, max_session_seconds=7201)
            outputs.assert_not_called()

    def test_invalid_values_rejected_before_hardware(self):
        for args in (['giu', '--bong', 'nan', '--quat', '100'],
                     ['giu', '--bong', '25', '--quat', '0'],
                     ['tay', '--giay', '601'], ['doc', '--giay', 'inf'],
                     ['giu', '--bong', '10', '--quat', '100', '--ngat-nhiet', '45']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                 patch.object(app, 'Outputs') as outputs, self.assertRaises(SystemExit) as error:
                app.main(args)
            self.assertEqual(error.exception.code, 2)
            outputs.assert_not_called()

    def test_plan_is_fully_validated_and_dry_run_never_touches_sensor(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.csv'
            path.write_text('ten,giay,bong_pct,quat_pct\na,60,0,100\nb,60,35,75\n', encoding='utf-8')
            self.assertEqual(len(app.load_plan(path)), 2)
            with contextlib.redirect_stdout(io.StringIO()), patch.object(app, 'find_sensor') as find:
                self.assertEqual(app.main(['kich-ban', '--tep', str(path), '--dry-run']), 0)
                find.assert_not_called()
            path.write_text('ten,giay,bong_pct,quat_pct\na,600,0,100\nb,1,35,75\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                app.load_plan(path)


if __name__ == '__main__':
    unittest.main()
