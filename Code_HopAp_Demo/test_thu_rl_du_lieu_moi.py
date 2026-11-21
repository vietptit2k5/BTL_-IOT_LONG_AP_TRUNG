"""Contract checks for the new physical pilot, without GPIO."""
import copy
import csv
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import thu_rl_du_lieu_moi as pilot


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(pilot.__file__).with_name('goi_rl_moi_20261120.json')
        cls.package=pilot.read_package(cls.path)

    def make(self):
        p=pilot.NewPilot(copy.deepcopy(self.package))
        p.bind_sensor('28-000000ca6c1f')
        p.observe_output(0.,0.,0.)
        return p

    def holding(self):
        p=self.make()
        p(0.,SimpleNamespace(temperature=26.,at=0.))
        p.observe_output(0.,75,100);p.observe_output(300.,75,100)
        decision=p(300.,SimpleNamespace(temperature=37.,at=300.))
        p.observe_output(300.,decision.lamp,decision.fan)
        return p

    def test_reject_modified_package(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'q.json';path.write_bytes(self.path.read_bytes()+b' ')
            with self.assertRaises(ValueError):pilot.read_package(path)

    def test_wrong_sensor(self):
        p=pilot.NewPilot(self.package)
        with self.assertRaises(pilot.core.SensorError):p.bind_sensor('28-wrong')

    def test_hot_initial_rejected(self):
        with self.assertRaises(ValueError):self.make()(0.,SimpleNamespace(temperature=30.1,at=0.))

    def test_stale_and_nan_rejected(self):
        for t,at,now in ((26.,0.,3.),(float('nan'),0.,0.)):
            with self.assertRaises(pilot.core.SensorError):self.make()(now,SimpleNamespace(temperature=t,at=at))

    def test_memory_uses_previous_applied_output(self):
        p=self.make();p.observe_output(0.,75.,100.);p.observe_output(25.,0.,100.)
        self.assertAlmostEqual(p.memory,.75*(1-__import__('math').exp(-1)))
        p.observe_output(50.,0.,100.)
        self.assertAlmostEqual(p.memory,.75*(1-__import__('math').exp(-1))*__import__('math').exp(-1))

    def test_warm_hold_guard_end_and_frozen_q(self):
        p=self.make();before=copy.deepcopy(p.package['policy'])
        warm=p(0.,SimpleNamespace(temperature=26.,at=0.))
        self.assertEqual((warm.lamp,warm.fan),(75,100))
        p.observe_output(0.,75.,100.);p.observe_output(300.,75.,100.)
        hold=p(300.,SimpleNamespace(temperature=37.,at=300.))
        self.assertEqual(hold.phase,'kiem_tra_rl_moi')
        p.observe_output(300.,hold.lamp,hold.fan)
        again=p(301.,SimpleNamespace(temperature=37.062,at=301.))
        self.assertIs(hold,again);self.assertEqual(p.decisions,1)
        guard=p(302.,SimpleNamespace(temperature=38.,at=302.))
        self.assertEqual((guard.lamp,guard.fan),(0,100))
        self.assertIsNone(p(900.,SimpleNamespace(temperature=37.5,at=900.)))
        self.assertTrue(p.completed);self.assertEqual(before,p.package['policy'])

    def test_unknown_state_stops(self):
        p=self.make();p(0.,SimpleNamespace(temperature=26.,at=0.))
        p.observe_output(0.,75,100);p.observe_output(300.,75,100)
        p.package['policy']['visits']=[[0]*9 for _ in range(2430)]
        with self.assertRaisesRegex(ValueError,'chưa học'):p(300.,SimpleNamespace(temperature=37.,at=300.))

    def test_cold_outside_model_recovers_before_next_q_decision(self):
        p=self.holding();decisions=p.decisions;memory=p.memory
        recovery=p(301.,SimpleNamespace(temperature=28.,at=301.))
        self.assertEqual((recovery.lamp,recovery.fan),(75,100))
        self.assertEqual(recovery.phase,'kiem_tra_rl_moi_phuc_hoi')
        self.assertEqual(p.decisions,decisions);self.assertEqual(p.memory,memory)
        self.assertEqual(p.hold_started,300.);self.assertEqual(p.recovery_count,1)

    def test_recovery_hysteresis_handover_and_unchanged_q(self):
        p=self.holding();before=copy.deepcopy(p.package['policy'])
        p.observe_output(301.,75.,100.)
        p(301.,SimpleNamespace(temperature=28.,at=301.))
        p.observe_output(306.,75.,100.)
        still=p(306.,SimpleNamespace(temperature=36.9,at=306.))
        self.assertEqual(still.phase,'kiem_tra_rl_moi_phuc_hoi')
        p.observe_output(311.,75.,100.)
        resumed=p(311.,SimpleNamespace(temperature=37.,at=311.))
        self.assertEqual(resumed.phase,'kiem_tra_rl_moi')
        self.assertIsNone(p.recovery_started)
        self.assertAlmostEqual(p.recovery_total_s,10.)
        self.assertGreater(p.memory,0)
        self.assertEqual(p.package['policy'],before)

    def test_recovery_timeout(self):
        p=self.holding();p(301.,SimpleNamespace(temperature=28.,at=301.))
        with self.assertRaisesRegex(ValueError,'450s'):
            p(751.,SimpleNamespace(temperature=36.,at=751.))

    def test_recovery_does_not_extend_ten_minute_hold(self):
        p=self.holding();p(600.,SimpleNamespace(temperature=28.,at=600.))
        self.assertIsNone(p(900.,SimpleNamespace(temperature=30.,at=900.)))
        self.assertTrue(p.completed)
        self.assertEqual(p.recovery_total_s,300.)

    def test_safety_overrides_recovery(self):
        p=self.holding();p(301.,SimpleNamespace(temperature=28.,at=301.))
        for t,at in ((28.,299.),(float('nan'),302.)):
            with self.assertRaises(pilot.core.SensorError):p(302.,SimpleNamespace(temperature=t,at=at))
        guarded=p(302.,SimpleNamespace(temperature=38.,at=302.))
        self.assertEqual((guarded.lamp,guarded.fan),(0,100))
        self.assertEqual(guarded.phase,'kiem_tra_rl_moi_bao_ve')

    def test_unseen_cold_state_recovers_but_unseen_target_state_stops(self):
        p=self.holding()
        p.package['policy']['visits']=[[0]*9 for _ in range(2430)]
        recovery=p(305.,SimpleNamespace(temperature=36.9,at=305.))
        self.assertEqual(recovery.phase,'kiem_tra_rl_moi_phuc_hoi')
        with self.assertRaisesRegex(ValueError,'chưa học'):
            p(310.,SimpleNamespace(temperature=37.,at=310.))

    def test_upper_handover_approaches_then_runs_same_q(self):
        p=pilot.NewPilot(copy.deepcopy(self.package),37.65,1200)
        p.bind_sensor('28-000000ca6c1f');p.observe_output(0.,0.,0.)
        p(0.,SimpleNamespace(temperature=26.,at=0.));p.observe_output(0.,75,100)
        p.observe_output(300.,75,100)
        approach=p(300.,SimpleNamespace(temperature=37.,at=300.))
        self.assertEqual((approach.lamp,approach.fan),(50,75))
        self.assertIsNone(p.hold_started);self.assertEqual(p.decisions,0)
        p.observe_output(300.,50,75);p.observe_output(390.,50,75)
        p(390.,SimpleNamespace(temperature=37.625,at=390.))
        self.assertIsNone(p.hold_started)
        p.observe_output(420.,50,75)
        decision=p(420.,SimpleNamespace(temperature=37.687,at=420.))
        self.assertEqual(decision.phase,'kiem_tra_rl_moi')
        self.assertEqual(p.hold_started,420.)
        self.assertEqual(p.metadata()['handover_temperature_c'],37.687)
        self.assertEqual(p.metadata()['requested_hold_seconds'],1200)
        self.assertIsNone(p(1620.,SimpleNamespace(temperature=37.5,at=1620.)))
        self.assertTrue(p.completed)

    def test_upper_approach_timeout_and_soft_guard(self):
        p=pilot.NewPilot(copy.deepcopy(self.package),37.65,1200)
        p.bind_sensor('28-000000ca6c1f');p.observe_output(0.,0.,0.)
        p(0.,SimpleNamespace(temperature=26.,at=0.))
        guarded=p(400.,SimpleNamespace(temperature=38.,at=400.))
        self.assertEqual((guarded.lamp,guarded.fan),(0,100));self.assertIsNone(p.hold_started)
        with self.assertRaises(ValueError):p(900.,SimpleNamespace(temperature=37.5,at=900.))

    def test_unsupported_handover_and_duration_rejected(self):
        for t,seconds in ((37.7,600),(37.65,1800)):
            with self.assertRaises(ValueError):pilot.NewPilot(self.package,t,seconds)

    def test_summary_separates_transition_from_later_drift(self):
        fields=['event','phase','elapsed_s','temperature_c','temperature_age_s','gpio_control','lamp_command_pct','fan_command_pct','note']
        raw=[dict(event='COMMAND',phase='kiem_tra_rl_moi',elapsed_s=0,gpio_control=1,lamp_command_pct=50,fan_command_pct=100)]
        for t in range(601):
            raw.append(dict(event='MEASUREMENT',phase='kiem_tra_rl_moi',elapsed_s=t,
                temperature_c=37.6 if t<120 else 37.4 if t<300 else 37.2,temperature_age_s=0))
        raw.extend([dict(event='STOP',elapsed_s=600),dict(event='END',elapsed_s=610)])
        config=dict(profile=dict(completed=True,requested_hold_seconds=600,soft_guard_count=0),hardware_program_exit_code=0)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'x.csv'
            with path.open('w',newline='',encoding='utf8') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(raw)
            result=pilot.summarize(path,config)
        self.assertAlmostEqual(result['first_120s']['in_band_pct'],100)
        self.assertAlmostEqual(result['after_120s']['in_band_pct'],37.5)
        self.assertAlmostEqual(result['covered_s'],600)
        self.assertAlmostEqual(result['first_exit_after_band_entry']['after_entry_s'],300)


if __name__=='__main__':unittest.main()
