"""Virtual-clock/synthetic tests for the scoped fan-off experiment. No GPIO."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import do_nhiet_hop as core
import thu_quat_lam_am as trial
from test_do_nhiet_hop import Clock,FakeDevice,FakeOutputs,FakeWorker


class FanOffTrialTests(unittest.TestCase):
    def run_virtual(self,fan=0,scenario='stable',controller=None,limited=True,reference=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        folder=Path(temp.name);sensor=folder/'28-000000000001/w1_slave'
        sensor.parent.mkdir();sensor.touch()
        if fan==0 and reference is None:
            reference=dict(heat_sample_temperature_c=25.,lamp_pct=50,requested_heat_s=30,
                           sensors=['28-000000000001'],source_sha256='SYNTHETIC_REFERENCE')
        clock=Clock();policy=controller or trial.WarmFanTrial(fan,reference=reference)
        class Worker(FakeWorker):
            def advance(self):
                super().advance()
                if clock.now>=25 and not self.fired:
                    if scenario=='hot_heat':
                        self.messages.put(core.Reading(clock.now,35.));self.fired=True
                    elif scenario=='crc_heat':
                        self.messages.put(core.Reading(clock.now,None,'synthetic CRC'));self.fired=True
                    elif scenario=='stale_heat':
                        self.scenario='stale';self.fired=True
        def make_worker(path):return Worker(path,clock,'hot_start' if scenario=='hot_start' else 'normal' if scenario=='drift' else 'stable')
        args=['giu','--bong','0','--quat','0','--giay','115','--ngat-nhiet','35',
              '--csv',str(folder/'du_lieu.csv'),'--khong-oled']
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()), \
             patch.object(core.time,'monotonic',clock.monotonic),patch.object(core.time,'sleep',clock.sleep), \
             patch.object(core,'find_sensor',return_value=sensor),patch.object(core,'Outputs',FakeOutputs), \
             patch.object(core,'SensorWorker',make_worker),patch.object(core,'COOLDOWN_SECONDS',.1):
            code=core.main(args,control_policy=policy,
                fan_off_trial_limits=core.FanOffTrialLimits() if limited else None)
        outputs=FakeOutputs.instances[-1]
        self.assertEqual((outputs.lamp.value,outputs.fan.value),(0,0))
        self.assertTrue(outputs.lamp.closed and outputs.fan.closed)
        if controller is None:
            (folder/'cau_hinh.json').write_text(json.dumps(dict(profile=policy.metadata(),hardware_program_exit_code=code)),encoding='utf-8')
        return code,outputs,policy,folder

    def test_existing_modes_still_reject_heater_without_fan(self):
        with self.assertRaises(ValueError):core.AutoDecision('normal',50,0)
        o=FakeOutputs(True);o.open()
        with self.assertRaises(ValueError):o.command(50,0,0)
        o.shutdown()
        policy=lambda now,r:core.AutoDecision('unscoped',50,0,fan_off_trial=True)
        code,outputs,_,_=self.run_virtual(controller=policy,limited=False)
        self.assertEqual(code,1);self.assertFalse(outputs.had_heat)

    def test_both_trials_complete_and_have_equal_applied_heater_dose(self):
        results=[]
        for fan in (0,75):
            code,outputs,p,folder=self.run_virtual(fan)
            self.assertEqual(code,0);self.assertTrue(p.completed)
            r=trial.summarize(folder/'du_lieu.csv');results.append(r)
            self.assertEqual(r['status'],'COMPLETED_SHORT_TRANSIENT')
            self.assertAlmostEqual(r['actual_heat_s'],30,delta=.1)
            self.assertAlmostEqual(r['mean_applied_lamp_pct'],50)
            self.assertAlmostEqual(r['mean_applied_fan_pct'],fan)
            self.assertTrue(all(h<=50 for h,f in outputs.trace))
        self.assertAlmostEqual(results[0]['actual_heat_s'],results[1]['actual_heat_s'],delta=.1)

    def test_hot_crc_or_stale_reading_during_heat_stops_outputs(self):
        for scenario in ('hot_heat','crc_heat','stale_heat'):
            code,outputs,p,_=self.run_virtual(scenario=scenario)
            self.assertEqual(code,1);self.assertTrue(outputs.had_heat)
            self.assertFalse(p.completed)

    def test_hot_initial_reading_never_heats(self):
        code,outputs,_,_=self.run_virtual(scenario='hot_start')
        self.assertEqual(code,1);self.assertFalse(outputs.had_heat)

    def test_budget_stops_even_a_policy_that_never_stops_heating(self):
        policy=lambda now,r:core.AutoDecision('bad_policy',50,0,fan_off_trial=True)
        code,outputs,_,_=self.run_virtual(controller=policy)
        self.assertEqual(code,1)
        self.assertGreaterEqual(outputs.fan_off_heating_s,30)
        self.assertLess(outputs.fan_off_heating_s,30.1)

    def test_budget_is_cumulative_across_fan_and_phase_changes(self):
        o=FakeOutputs(True,fan_off_trial_limits=core.FanOffTrialLimits(max_total_fan_off_s=3))
        o.open();o.command(50,0,0);o.tick(1);o.command(0,75,1);o.command(50,0,2)
        with self.assertRaises(core.StopRun):o.tick(4)
        self.assertEqual(o.lamp.value,0);self.assertAlmostEqual(o.fan_off_heating_s,3)
        with self.assertRaises(ValueError):o.command(75,75,5)
        o.shutdown()

    def test_invalid_scope_cannot_open_hardware(self):
        normal=['giu','--bong','0','--quat','0','--giay','112','--ngat-nhiet','35','--dry-run']
        for args,policy in ((normal,None),
                            (['giu','--bong','0','--quat','0','--giay','121','--ngat-nhiet','35','--dry-run'],lambda n,r:None),
                            (['giu','--bong','0','--quat','0','--giay','112','--ngat-nhiet','40','--dry-run'],lambda n,r:None)):
            with patch.object(core,'Outputs') as output,contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):core.main(args,control_policy=policy,fan_off_trial_limits=core.FanOffTrialLimits())
                output.assert_not_called()
        with self.assertRaises(ValueError):core.FanOffTrialLimits(max_total_fan_off_s=31)
        with self.assertRaises(ValueError):core.FanOffTrialLimits(max_lamp_pct=51)

    def test_policy_switches_early_at_33_and_uses_same_mixing_pulse(self):
        p=trial.WarmFanTrial(0,reference=dict(heat_sample_temperature_c=26.,lamp_pct=50,requested_heat_s=30,
                                          sensors=['28-000000000001'],source_sha256='SYNTHETIC'))
        for t in range(23):self.assertEqual(p(t,core.Reading(t,26)).lamp,0)
        self.assertEqual(p(23,core.Reading(23,26)).lamp,50)
        d=p(28,core.Reading(28,33))
        self.assertEqual((d.lamp,d.fan),(0,100));self.assertTrue(p.shortened)
        self.assertEqual(p(29,core.Reading(29,32)).fan,75)
        self.assertIsNone(p(88,core.Reading(88,27)))

    def test_dry_run_never_calls_core_or_creates_output(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'main',side_effect=AssertionError('hardware')),contextlib.redirect_stdout(io.StringIO()):
            out=Path(tmp)/'not_created'
            self.assertEqual(trial.main(['do','--quat','0','--dry-run','--out',str(out),
                                         '--moc-so-sanh',str(Path(tmp)/'no_reference.json')]),0)
            self.assertFalse(out.exists())

    def test_comparison_rejects_duplicate_and_wrong_fan_trials(self):
        _,_,_,folder75=self.run_virtual(75)
        r75=trial.summarize(folder75/'du_lieu.csv')
        ref=trial.save_reference(folder75/'moc.json',folder75/'du_lieu.csv',r75)
        _,_,_,folder0=self.run_virtual(0,reference=ref)
        out=folder75/'comparison'
        result=trial.compare(folder75/'du_lieu.csv',folder0/'du_lieu.csv',out)
        self.assertEqual(result['warnings'],[])
        self.assertTrue(result['comparison_conditions_accepted'])
        self.assertEqual(result['initial_temperature_difference_c'],0)
        with self.assertRaises(ValueError):trial.compare(folder75/'du_lieu.csv',folder75/'du_lieu.csv',folder75/'bad')

    def test_missing_reference_blocks_fan0_before_hardware(self):
        with self.assertRaises(ValueError):trial.WarmFanTrial(0)
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'main') as hardware,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):trial.main(['do','--quat','0','--moc-so-sanh',str(Path(tmp)/'missing.json')])
            hardware.assert_not_called()

    def test_start_temperature_and_drift_are_checked_before_heating(self):
        bad=dict(heat_sample_temperature_c=25.125,lamp_pct=50,requested_heat_s=30,
                 sensors=['28-000000000001'],source_sha256='SYNTHETIC')
        code,outputs,p,_=self.run_virtual(0,reference=bad)
        self.assertEqual(code,1);self.assertFalse(outputs.had_heat);self.assertIsNone(p.heat_started)
        close=dict(bad,heat_sample_temperature_c=25.062)
        code,outputs,p,_=self.run_virtual(0,reference=close)
        self.assertEqual(code,0);self.assertTrue(outputs.had_heat)
        code,outputs,p,_=self.run_virtual(75,scenario='drift')
        self.assertEqual(code,1);self.assertFalse(outputs.had_heat);self.assertFalse(p.baseline_stable)

    def test_reference_uses_valid_source_and_cannot_be_silently_overwritten(self):
        _,_,_,folder=self.run_virtual(75)
        log=folder/'du_lieu.csv';path=folder/'moc.json'
        ref=trial.save_reference(path,log,trial.summarize(log))
        self.assertEqual(trial.load_reference(path),ref)
        original=path.read_bytes()
        with self.assertRaises(FileExistsError):trial.save_reference(path,log,trial.summarize(log))
        self.assertEqual(path.read_bytes(),original)
        ref['heat_sample_temperature_c']+=1
        path.write_text(json.dumps(ref),encoding='utf-8')
        with self.assertRaises(ValueError):trial.load_reference(path)


if __name__=='__main__':unittest.main()
