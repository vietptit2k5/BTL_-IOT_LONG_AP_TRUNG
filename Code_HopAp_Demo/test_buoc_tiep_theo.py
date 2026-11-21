"""Synthetic and virtual tests only: no GPIO or measured-performance claims."""
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chinh_sach_nhiet as rules
import do_nhiet_hop as core
import kiem_tra_giu_nhiet as hold
import toi_uu_rl_offline as rl


class SyntheticModel:
    low,high,noise_sd = 30.,39.,0.
    def step(self,t,d,m,h,f,noise=0):
        delta=.3*h-.12+noise
        return t+delta,delta,h


def synthetic_hold(path,ended=True,drop=False,error=False):
    rows=[]
    for t in range(91):
        if t==20:
            rows.append(dict(elapsed_s=t,event='COMMAND',phase='kiem_tra_giu_nhiet'))
        if t==80:
            rows.append(dict(elapsed_s=t,event='STOP',phase='kiem_tra_giu_nhiet'))
        if drop and 31<=t<=40:
            continue
        temp=30 if t<20 or t>=80 else 38.5 if 40<=t<60 else 37.5
        rows.append(dict(elapsed_s=t,event='MEASUREMENT',phase='kiem_tra_bao_ve' if 40<=t<60 else 'other',
                         temperature_c=temp,temperature_age_s=0))
    if error:
        rows.append(dict(elapsed_s=91,event='ERROR',phase='end',note='SYNTHETIC_ERROR'))
    if ended:
        rows.append(dict(elapsed_s=92,event='END',phase='end'))
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=['elapsed_s','event','phase','temperature_c','temperature_age_s','note'])
        w.writeheader();w.writerows(rows)
    (path.parent/'cau_hinh.json').write_text(json.dumps(dict(bo_dieu_khien='SYNTHETIC',
        profile=dict(completed=True,requested_hold_seconds=60,soft_guard_count=1),hardware_program_exit_code=0)),encoding='utf-8')


class NextStepTests(unittest.TestCase):
    def test_soft_guard_hysteresis_and_nonfinite(self):
        g=rules.SoftGuard()
        self.assertFalse(g.update(37.9))
        self.assertTrue(g.update(38))
        self.assertTrue(g.update(37.5))
        self.assertFalse(g.update(37))
        self.assertEqual(g.count,1)
        with self.assertRaises(ValueError):g.update(math.nan)

    def test_state_indexes_include_guard_and_stay_in_table(self):
        for t in (20,36,37.5,39,50):
            for d in (-1,0,1):
                for m in (0,.5,1):
                    off=rl.state(t,d,m,False,37.5,.5,1)
                    on=rl.state(t,d,m,True,37.5,.5,1)
                    self.assertEqual(on,off+1)
                    self.assertTrue(0<=off<on<rl.STATE_COUNT)

    def test_expected_sarsa_expectation_and_forced_action(self):
        self.assertAlmostEqual(rl.expected_value([2.,6.],[0,1],.2),5.6)
        self.assertEqual(rl.expected_value([999.,-5.],[1],.8),-5.)

    def test_training_checkpoint_is_reproducible(self):
        model=SyntheticModel()
        actions=[(0.,.75),(0.,1.),(.5,.75),(1.,.75)]
        rows=[dict(temperature=37.2,previous_delta=0,memory_before=.5)]
        for algorithm in ('q-learning','expected-sarsa'):
            first=next(rl.train_checkpoints(model,rows,actions,37.5,.5,algorithm,dict(hot=3,duty=0),11,[10]))
            second=next(rl.train_checkpoints(model,rows,actions,37.5,.5,algorithm,dict(hot=3,duty=0),11,[10,20]))
            self.assertEqual(first,second)
            self.assertEqual(len(first[1]),162)
        with self.assertRaises(ValueError):
            next(rl.train_checkpoints(model,rows,actions,37.5,.5,'wrong',{},11,[10]))

    def test_simulation_guard_forces_heater_off(self):
        actions=[(0.,1.),(.5,.75),(1.,.75)]
        q=[[0,0,10] for _ in range(162)];visits=[[1]*3 for _ in q]
        case=dict(initial=dict(temperature=37.95,previous_delta=0,memory_before=1,h=1,f=.75),noise=[0.]*120)
        met,trace=rl.rollout(SyntheticModel(),actions,case,37.5,.5,q=q,visits=visits,trace=True)
        self.assertGreater(met['guard_count'],0)
        guarded=[r for r in trace if r['soft_guard']]
        self.assertTrue(guarded)
        self.assertTrue(all(r['lamp_pct']==0 and r['fan_pct']==100 for r in guarded))

    def test_rank_uses_eligibility_before_tiny_hot_difference(self):
        good=dict(eligible=True,invalid_fraction=0,in_band_pct=95,worst_seed_in_band_pct=94,
                  guard_rate=0,fallback_rate=0,mae_c=.2,mean_duty_proxy=.7,hot_area_c_min=.001)
        bad=dict(good,eligible=False,in_band_pct=70,hot_area_c_min=0,mae_c=.1)
        self.assertLess(rl.rank(good,.5),rl.rank(bad,.5))

    def test_live_guard_and_duration_include_protected_time(self):
        p=hold.HoldPolicy(seconds=60,warm_timeout=30)
        self.assertEqual(p(0,core.Reading(0,37.5)).lamp,50)
        self.assertEqual(p(1,core.Reading(1,38)).lamp,0)
        self.assertEqual(p(40,core.Reading(40,37.5)).lamp,0)
        self.assertIsNone(p(60,core.Reading(60,37.5)))
        self.assertTrue(p.completed)
        self.assertEqual(p.guard.count,1)

    def test_warm_timeout_and_hot_start(self):
        p=hold.HoldPolicy(seconds=60,warm_timeout=30)
        self.assertEqual(p(0,core.Reading(0,30)).lamp,75)
        with self.assertRaises(hold.WarmupTimeout):p(30,core.Reading(30,36))
        p=hold.HoldPolicy(seconds=60,warm_timeout=30)
        d=p(0,core.Reading(0,38.2))
        self.assertEqual((d.lamp,d.fan),(0,100))
        self.assertIsNone(p.hold_started)
        self.assertEqual(p(10,core.Reading(10,37)).lamp,50)
        self.assertEqual(p.hold_started,10)

    def test_invalid_fixed_levels_and_rl_mode_rejected(self):
        for kwargs in (dict(lamp=100),dict(fan=50),dict(mode='rl')):
            with self.assertRaises(ValueError):hold.HoldPolicy(**kwargs)

    def test_dry_run_does_not_call_hardware_or_create_folder(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'main',side_effect=AssertionError('GPIO')),contextlib.redirect_stdout(io.StringIO()):
            out=Path(tmp)/'must_not_exist'
            self.assertEqual(hold.main(['do','--bo-dieu-khien','co-dinh','--dry-run','--out',str(out)]),0)
            self.assertFalse(out.exists())

    def test_hold_metrics_include_guard_but_exclude_warm_and_postcool(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.csv';synthetic_hold(path)
            r=hold.summarize(path)
            self.assertEqual(r['status'],'COMPLETED_HARDWARE_HOLD_TEST')
            self.assertEqual(r['covered_s'],60)
            self.assertAlmostEqual(r['mae_c'],1/3)
            self.assertAlmostEqual(r['in_band_pct'],200/3)
            self.assertEqual((r['min_c'],r['max_c']),(37.5,38.5))
            self.assertEqual(r['above_band_s'],20)

    def test_missing_end_missing_samples_or_error_never_marked_complete(self):
        for flags in (dict(ended=False),dict(drop=True),dict(error=True)):
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'data.csv';synthetic_hold(path,**flags)
                self.assertEqual(hold.summarize(path)['status'],'INCOMPLETE_HOLD_TEST')

    def test_reference_rejects_qtable_or_mismatched_hardware(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json'
            p.write_text(json.dumps(dict(deploy_allowed=False)),encoding='utf-8')
            with self.assertRaises(ValueError):hold.read_reference(p)
            p.write_text(json.dumps(dict(purpose='REFERENCE_CONTROLLER_ONLY',target_c=38,band_c=.5,fan_pwm_hz=100)),encoding='utf-8')
            with self.assertRaises(ValueError):hold.read_reference(p)


if __name__=='__main__':unittest.main()
