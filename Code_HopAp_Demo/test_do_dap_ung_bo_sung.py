"""Virtual response experiment tests; none of these are measured hardware data."""
import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import do_nhiet_hop as core
import do_dap_ung_bo_sung as app
from test_do_nhiet_hop import Clock, FakeWorker, FakeOutputs


def read(at, t=37.):
    return core.Reading(at, t)


def ready_policy():
    p = app.ResponseSurvey()
    p(0,read(0,25))
    for s in range(1,32):
        p(s,read(s))
    return p


class SurveyTests(unittest.TestCase):
    def test_one_temperature_complete_matrix_plan_and_scope(self):
        p=app.ResponseSurvey(dwell=1200,target=37.5,prepare_seconds=600,post_seconds=300,
                             warm_seconds=900,single_target_full_matrix=True)
        self.assertEqual(p.limit,21902)
        self.assertEqual(set(p.pairs),{(h,f) for h in (0,25,50,75,100) for f in (75,100)})
        self.assertTrue(p.metadata()['single_target_full_matrix'])
        with self.assertRaises(ValueError):
            app.ResponseSurvey(dwell=1200,prepare_seconds=600,post_seconds=300,warm_seconds=900)
        with self.assertRaises(ValueError):
            app.ResponseSurvey(single_target_full_matrix=True,heat_levels=(50,))
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'main',side_effect=AssertionError('GPIO')):
            folder=Path(tmp)/'out'
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(app.main(['do','--mot-moc','--giai-doan','2','--dry-run','--out',str(folder)]),0)
            self.assertIn('365.0',output.getvalue())
            self.assertIn('10:',output.getvalue())
            self.assertFalse(folder.exists())

    def test_extended_core_limit_only_for_explicit_complete_matrix(self):
        p=app.ResponseSurvey(dwell=1200,target=37.5,prepare_seconds=600,post_seconds=300,
                             warm_seconds=900,single_target_full_matrix=True)
        command=['giu','--bong','0','--quat','100','--giay','21902','--ngat-nhiet','38.5','--dry-run']
        with patch.object(core,'Outputs',side_effect=AssertionError('GPIO')), \
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(core.main(command,control_policy=p,max_session_seconds=21902,single_temperature_matrix=True),0)
            for options in (dict(control_policy=p,max_session_seconds=21902),
                            dict(control_policy=lambda *_:None,max_session_seconds=21902,single_temperature_matrix=True)):
                with self.assertRaises(SystemExit):core.main(command,**options)
            with self.assertRaises(SystemExit):
                core.main([*command,'--ngat-nhiet','40'],control_policy=p,max_session_seconds=21902,single_temperature_matrix=True)
            with self.assertRaises(SystemExit):
                core.main(command,control_policy=p,max_session_seconds=21902,single_temperature_matrix=True,
                          fan_off_trial_limits=core.FanOffTrialLimits())

    def test_extended_session_sensor_faults_still_shutdown(self):
        for scenario in ('crc','stale','hot'):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as tmp:
                clock=Clock();FakeOutputs.instances.clear()
                p=app.ResponseSurvey(single_target_full_matrix=True)
                with patch.object(core.time,'monotonic',clock.monotonic),patch.object(core.time,'sleep',clock.sleep), \
                     patch.object(core,'find_sensor',return_value=Path('/fake/28-test/w1_slave')), \
                     patch.object(core,'Outputs',FakeOutputs), \
                     patch.object(core,'SensorWorker',side_effect=lambda path:FakeWorker(path,clock,scenario)), \
                     contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    code=core.main(['giu','--bong','0','--quat','100','--giay','21902','--ngat-nhiet','38.5',
                                   '--khong-oled','--csv',str(Path(tmp)/'data.csv')],control_policy=p,
                                   max_session_seconds=21902,single_temperature_matrix=True)
                self.assertNotEqual(code,0)
                self.assertEqual(FakeOutputs.instances[-1].lamp.value,0)
                self.assertEqual(FakeOutputs.instances[-1].fan.value,0)

    def test_real_measurement_targets_for_three_stages(self):
        for stage,target in ((1,37.8),(2,37.5),(3,37.2)):
            p=app.ResponseSurvey(target=target,heat_levels=(50,))
            p(0,read(0,25))
            for s in range(1,32):p(s,read(s,target))
            self.assertEqual(p.stage,'probe')
            self.assertAlmostEqual(p.records[0]['start_temperature_c'],target)
            with patch.object(core,'main',side_effect=AssertionError('GPIO')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(app.main(['do','--giai-doan',str(stage),'--do-dai','--dry-run']),0)
            self.assertIn(f'Nền {target:g}',output.getvalue())

    def test_high_stage_does_not_start_probe_at_or_above_upper_cutoff(self):
        p=app.ResponseSurvey(target=37.8,heat_levels=(50,))
        p(0,read(0,25))
        for s in range(1,35):p(s,read(s,37.925))
        self.assertEqual(p.stage,'condition')
        self.assertEqual(p.records,[])

    def test_stage_and_explicit_target_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            app.main(['do','--giai-doan','2','--nhiet-nen','37.5','--dry-run'])

    def test_long_trial_does_not_finish_after_five_minutes(self):
        p=app.ResponseSurvey(dwell=1200,heat_levels=(50,),prepare_seconds=600,post_seconds=300,warm_seconds=900)
        self.assertEqual(p.limit,5102)
        p(0,read(0,25))
        for s in range(1,32):p(s,read(s))
        start=p.stage_at
        p(start+300,read(start+300))
        self.assertEqual(p.stage,'probe')
        p(start+1199,read(start+1199))
        self.assertEqual(p.stage,'probe')
        p(start+1200,read(start+1200))
        self.assertEqual(p.stage,'post')
        self.assertEqual(p.records[0]['actual_probe_s'],1200)
        p(start+1290,read(start+1290))
        self.assertEqual(p.index,0)
        p(start+1500,read(start+1500))
        self.assertEqual(p.index,1)
        self.assertEqual(p.metadata()['post_s'],300)
        p=app.ResponseSurvey(dwell=1200,heat_levels=(100,),prepare_seconds=600,post_seconds=300,warm_seconds=900)
        p(0,read(0,25))
        for s in range(1,32):p(s,read(s))
        self.assertEqual(p(32,read(32,38)).lamp,0)
        self.assertFalse(p.records[0]['full_duration'])

    def test_long_profile_cli_and_oversized_schedule_rejected_before_gpio(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'main',side_effect=AssertionError('GPIO')):
            folder=Path(tmp)/'out'
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(app.main(['do','--do-dai','--dry-run','--out',str(folder)]),0)
            self.assertIn('1200s',output.getvalue())
            self.assertIn('85.0',output.getvalue())
            self.assertFalse(folder.exists())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(app.main(['do','--do-dai','--muc-bong','25','50','75','--out',str(folder)]),1)
            self.assertFalse(folder.exists())
        with self.assertRaises(ValueError):app.ResponseSurvey(dwell=1800)
        self.assertLess(app.ResponseSurvey(dwell=1800,heat_levels=(50,),prepare_seconds=600,
                                         post_seconds=300,warm_seconds=900).limit,7200)

    def test_selected_pair_and_lower_temperature_band(self):
        p=app.ResponseSurvey(target=33,heat_levels=(50,50))
        self.assertEqual(p.pairs,[(50,75),(50,100)])
        self.assertEqual((p.lower,p.upper),(32,34))
        self.assertEqual(p.limit,1862)
        p(0,read(0,25))
        for s in range(1,32):p(s,read(s,33))
        self.assertEqual(p.stage,'probe')
        self.assertEqual(p.records[0]['start_temperature_c'],33)
        self.assertEqual(p.metadata()['initial_target_c'],33)
        self.assertEqual(p(32,read(32,34)).lamp,0)
        self.assertEqual(p.records[0]['end_reason'],'upper_34c')
        self.assertEqual(app.ResponseSurvey(target=35).upper,36)
        for options in (dict(target=38),dict(heat_levels=()),dict(heat_levels=(101,))):
            with self.assertRaises(ValueError):app.ResponseSurvey(**options)

    def test_same_pairs_reversed_and_time_budget(self):
        p = app.ResponseSurvey()
        self.assertEqual(len(set(p.pairs)),10)
        self.assertEqual(app.ResponseSurvey(True).pairs,p.pairs[::-1])
        self.assertLess(p.limit,core.MAX_SURVEY_SECONDS)
        self.assertTrue(all(f>=75 for _,f in p.pairs))
        with self.assertRaises(ValueError):app.ResponseSurvey(dwell=1801)

    def test_initial_hot_and_warm_timeout(self):
        with self.assertRaises(ValueError):app.ResponseSurvey()(0,read(0,31))
        p=app.ResponseSurvey();p(0,read(0,25))
        with self.assertRaises(core.StopRun):p(600,read(600,26))

    def test_stable_window_required_and_timeout(self):
        p=app.ResponseSurvey();p(0,read(0,25));p(1,read(1))
        self.assertEqual(p.stage,'condition')
        for s in range(2,32):p(s,read(s,37+(.2 if s%2 else -.2)))
        self.assertEqual(p.stage,'condition')
        with self.assertRaises(core.StopRun):p(241,read(241))

    def test_memory_matching_gates_start(self):
        p=app.ResponseSurvey();p.reference_memory=.5
        p(0,read(0,25))
        for s in range(1,35):p(s,read(s))
        self.assertEqual(p.stage,'condition')
        p.memory=.5;p(35,read(35))
        self.assertEqual(p.stage,'probe')

    def test_warmup_probe_cutoff_and_guard_latch(self):
        p=ready_policy()
        self.assertEqual(p.stage,'probe')
        self.assertEqual((p(32,read(32)).lamp,p(32,read(32)).fan),(50,75))
        self.assertEqual(p(33,read(33,37.95)).lamp,0)
        self.assertEqual(p.records[0]['end_reason'],'upper_37_9c')
        self.assertFalse(p.records[0]['full_duration'])
        self.assertEqual(p(34,read(34,38)).fan,100)
        self.assertEqual(p(35,read(35,37.5)).lamp,0)
        self.assertTrue(p.guard)
        p(36,read(36,37));self.assertFalse(p.guard)

    def test_applied_memory_includes_previous_output(self):
        p=app.ResponseSurvey();p.observe_output(0,0,100)
        p.observe_output(1,100,100);self.assertEqual(p.memory,0)
        p.observe_output(26,0,100)
        self.assertAlmostEqual(p.memory,1-app.math.exp(-1))

    def test_full_sequence_completes(self):
        p=app.ResponseSurvey(dwell=120);p(0,read(0,25))
        for s in range(1,4000):
            d=p(s,read(s))
            if d is None:break
            self.assertGreaterEqual(d.fan,75)
        self.assertTrue(p.completed)
        self.assertEqual(len(p.records),10)
        self.assertTrue(all(r['full_duration'] for r in p.records))

    def test_core_sensor_faults_and_hot_reading_stop_outputs(self):
        for scenario in ('crc','stale','hot'):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as tmp:
                clock=Clock();FakeOutputs.instances.clear()
                with patch.object(core.time,'monotonic',clock.monotonic),patch.object(core.time,'sleep',clock.sleep), \
                     patch.object(core,'find_sensor',return_value=Path('/fake/28-test/w1_slave')), \
                     patch.object(core,'Outputs',FakeOutputs), \
                     patch.object(core,'SensorWorker',side_effect=lambda path:FakeWorker(path,clock,scenario)), \
                     contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                    code=core.main(['giu','--bong','0','--quat','100','--giay','30','--ngat-nhiet','38.5',
                                    '--khong-oled','--csv',str(Path(tmp)/'x.csv')],control_policy=app.ResponseSurvey())
                self.assertNotEqual(code,0)
                output=FakeOutputs.instances[-1]
                self.assertEqual(output.lamp.value,0)
                self.assertEqual(output.fan.value,0)

    def test_dry_run_no_gpio_or_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'out'
            with patch.object(core,'main',side_effect=AssertionError('GPIO')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.main(['do','--out',str(folder),'--dry-run','--dht11']),0)
            self.assertFalse(folder.exists())

    def test_analysis_rejects_shortened_or_wrong_applied_pwm(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'data.csv'
            rows=[]
            def row(event,at,phase,h=50):
                r={k:'' for k in core.CSV_FIELDS}
                r.update(event=event,elapsed_s=str(at),phase=phase,temperature_c=str(37+at/10000),
                         temperature_age_s='0',sensor_id='28-synthetic',lamp_command_pct=str(h),fan_command_pct='75')
                return r
            rows.append(row('COMMAND',0,'id_01_kich_thich'))
            rows.extend(row('MEASUREMENT',s,'id_01_kich_thich') for s in range(1,300))
            rows.extend(row('MEASUREMENT',s,'id_01_sau_tat',0) for s in range(300,390))
            rows.append(row('END',390,'id_01_sau_tat',0))
            profile=dict(completed=True,dwell_s=300,records=[dict(trial=1,lamp=50,fan=75,
                full_duration=True,actual_probe_s=300,end_reason='duration',start_temperature_c=37,
                start_slope_c_per_min=0,start_heat_memory=.5)])
            def analyze():
                with log.open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=core.CSV_FIELDS);w.writeheader();w.writerows(rows)
                return app.analyze(log,profile,0)['trials'][0]
            self.assertTrue(analyze()['continuous_full_probe'])
            self.assertGreater(analyze()['slope_30_90_c_per_min'],0)
            profile['records'][0]['full_duration']=False
            self.assertFalse(analyze()['continuous_full_probe'])
            profile['records'][0]['full_duration']=True;rows[20]['lamp_command_pct']='0'
            self.assertFalse(analyze()['continuous_full_probe'])
            rows[20]['lamp_command_pct']='50'
            profile['dwell_s']=1200
            self.assertFalse(analyze()['continuous_full_probe'])
            self.assertIsNone(analyze()['tail_180s_slope_c_per_min'])
            rows=[]
            rows.append(row('COMMAND',0,'id_01_kich_thich'))
            rows.extend(row('MEASUREMENT',s,'id_01_kich_thich') for s in range(1,1200))
            rows.append(row('END',1200,'id_01_sau_tat',0))
            self.assertTrue(analyze()['continuous_full_probe'])
            self.assertAlmostEqual(analyze()['slope_900_1200_c_per_min'],.006)
            self.assertGreaterEqual(analyze()['tail_180s_coverage_s'],175)


if __name__=='__main__':unittest.main()
