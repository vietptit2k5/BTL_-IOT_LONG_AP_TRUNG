"""Virtual fixed-operating-point tests only; no hardware access."""
import contextlib
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import do_nhiet_hop as core
import kiem_tra_giu_nhiet as hold


class OperatingPointTests(unittest.TestCase):
    def test_two_stage_approach_then_constant_duty_for_whole_hold(self):
        p=hold.HoldPolicy(mode='co-dinh',seconds=60,warm_timeout=60,hold_start_c=37.5)
        self.assertEqual((p(0,core.Reading(0,26)).lamp,p(0,core.Reading(0,26)).fan),(75,100))
        for t,temp in ((10,37),(20,37.3)):
            d=p(t,core.Reading(t,temp))
            self.assertEqual((d.lamp,d.fan),(50,75))
            self.assertIsNone(p.hold_started)
        self.assertEqual(p(30,core.Reading(30,37.5)).lamp,50)
        self.assertEqual(p.hold_started,30)
        self.assertEqual(p(89,core.Reading(89,37.6)).lamp,50)
        self.assertIsNone(p(90,core.Reading(90,37.5)))
        self.assertTrue(p.completed)

    def test_does_not_claim_hold_when_fixed_level_cannot_reach_target(self):
        p=hold.HoldPolicy(seconds=60,warm_timeout=60,hold_start_c=37.5)
        p(0,core.Reading(0,26))
        p(50,core.Reading(50,37.3))
        with self.assertRaises(hold.WarmupTimeout):p(60,core.Reading(60,37.3))
        self.assertFalse(p.completed)
        self.assertIsNone(p.hold_started)

    def test_protection_still_overrides_constant_levels(self):
        p=hold.HoldPolicy(seconds=60,warm_timeout=60,hold_start_c=37.5)
        p(0,core.Reading(0,37.5))
        d=p(1,core.Reading(1,38))
        self.assertEqual((d.lamp,d.fan),(0,100))
        self.assertEqual(p(30,core.Reading(30,37.5)).lamp,0)
        self.assertEqual(p(40,core.Reading(40,37)).lamp,50)
        self.assertIsNone(p(60,core.Reading(60,37.5)))

    def test_cannot_change_rl_or_reference_protocol_with_new_threshold(self):
        for mode in ('doi-chung','thu-rl'):
            with self.assertRaises(ValueError):hold.HoldPolicy(mode=mode,hold_start_c=37.5)
        for threshold in (36.9,37.6,float('nan')):
            with self.assertRaises(ValueError):hold.HoldPolicy(hold_start_c=threshold)

    def test_lower_warmup_fan_is_explicit_and_protection_still_uses_full_fan(self):
        p=hold.HoldPolicy(mode='co-dinh',seconds=60,warm_timeout=60,hold_start_c=37.5,warm_fan=75)
        d=p(0,core.Reading(0,26))
        self.assertEqual((d.lamp,d.fan),(75,75))
        d=p(10,core.Reading(10,37.2))
        self.assertEqual((d.lamp,d.fan),(50,75))
        d=p(20,core.Reading(20,38))
        self.assertEqual((d.lamp,d.fan),(0,100))
        self.assertEqual(p.metadata()['warm_fan_pct'],75)
        for mode in ('doi-chung','thu-rl'):
            with self.assertRaises(ValueError):hold.HoldPolicy(mode=mode,warm_fan=75)
        for fan in (0,50,101,float('nan')):
            with self.assertRaises(ValueError):hold.HoldPolicy(warm_fan=fan)

    def test_new_dry_run_does_not_access_hardware_or_write_data(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'main',side_effect=AssertionError('GPIO')),contextlib.redirect_stdout(io.StringIO()):
            out=Path(tmp)/'not_created'
            result=hold.main(['do','--bo-dieu-khien','co-dinh','--bat-dau-giu','37.5','--dry-run','--out',str(out)])
            self.assertEqual(result,0)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
