"""Synthetic policy/virtual GPIO tests. No physical measurements are created."""
import copy
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chinh_sach_rl as pilot
import do_nhiet_hop as core
import kiem_tra_giu_nhiet as hold


def synthetic_package():
    actions=[[h,f] for h in (0,.25,.5,.75,1.) for f in (.75,1.) if (h,f)!=(1.,1.)]
    policy=dict(seed=11,q=[[float(j) for j in range(9)] for _ in range(162)],
                visits=[[1]*9 for _ in range(162)])
    return dict(purpose='SUPERVISED_EMPTY_BOX_PILOT_ONLY',version=1,supervised_pilot_allowed=True,
        automatic_deploy_allowed=False,original_candidate_deploy_allowed=False,target_c=37.5,band_c=.5,
        state_encoder='9e_3d_3m_guard_v2',state_count=162,dt_s=5,fan_pwm_hz=100,max_initial_temperature_c=30,
        sensor_id='28-000000000001',model=dict(low=31.25,high=38.375,tau=25),actions=actions,policy=policy,
        policy_sha256=pilot.policy_digest(policy),independent_validation=dict(status='PASS_SHORT_HORIZON_ONLY'))


class PilotTests(unittest.TestCase):
    def test_humidity_forwarded_without_changing_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'policy.json'
            package = synthetic_package()
            path.write_text(json.dumps(package), encoding='utf-8')
            original = path.read_bytes()
            for enabled in (False, True):
                folder = Path(tmp)/str(enabled)
                def run_core(command, control_policy, max_session_seconds):
                    self.assertEqual('--dht11' in command, enabled)
                    self.assertEqual(control_policy.mode, 'thu-rl')
                    self.assertEqual(control_policy.pilot.metadata()['q_updates'], 0)
                    control_policy.completed = True
                    return 0
                options = ['do', '--bo-dieu-khien', 'thu-rl', '--goi-thu-rl', str(path), '--out', str(folder)]
                if enabled:
                    options.append('--dht11')
                with patch.object(core, 'main', side_effect=run_core), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(hold.main(options), 0)
                config = json.loads((folder/'cau_hinh.json').read_text(encoding='utf-8'))
                self.assertEqual(config['dht11'], enabled)
                self.assertEqual(path.read_bytes(), original)

    def test_package_requires_explicit_supervised_purpose_and_unchanged_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'package.json'
            valid=synthetic_package()
            path.write_text(json.dumps(valid),encoding='utf-8')
            self.assertEqual(pilot.read_pilot(path)['policy']['seed'],11)
            variants=[]
            for key,value in (('purpose','SIMULATION_ONLY'),('automatic_deploy_allowed',True),('state_count',729)):
                v=copy.deepcopy(valid);v[key]=value;variants.append(v)
            v=copy.deepcopy(valid);v['policy']['q'][0][0]+=1;variants.append(v)
            v=copy.deepcopy(valid);v['actions'][0]=[1.,1.];variants.append(v)
            for v in variants:
                path.write_text(json.dumps(v),encoding='utf-8')
                with self.assertRaises(ValueError):pilot.read_pilot(path)

    def test_infinite_q_is_rejected_even_when_checksum_matches(self):
        v=synthetic_package();v['policy']['q'][0][0]=math.inf
        with self.assertRaises(ValueError):pilot.policy_digest(v['policy'])

    def test_sensor_binding_and_observer_are_required(self):
        p=pilot.FrozenPilot(synthetic_package())
        with self.assertRaises(pilot.PilotError):p.bind_sensor('28-different')
        with self.assertRaises(pilot.PilotError):p.select(37.5,0)
        p.bind_sensor('28-000000000001')
        with self.assertRaises(pilot.PilotError):p.select(37.5,0)
        p.observe_output(0,0,0)
        self.assertEqual(p.select(37.5,0)[0],8)

    def test_memory_tracks_applied_pwm_including_initial_off_period(self):
        p=pilot.FrozenPilot(synthetic_package())
        p.observe_output(0,0,0)
        p.observe_output(1,75,100)
        self.assertEqual(p.memory,0)
        p.observe_output(26,0,100)
        self.assertAlmostEqual(p.memory,.75*(1-math.exp(-1)))
        p.observe_output(51,0,100)
        self.assertAlmostEqual(p.memory,.75*(1-math.exp(-1))*math.exp(-1))
        with self.assertRaises(pilot.PilotError):p.observe_output(50,0,100)

    def test_unknown_or_outside_state_stops_without_learning(self):
        data=synthetic_package();p=pilot.FrozenPilot(data)
        p.bind_sensor(data['sensor_id']);p.observe_output(0,0,0)
        with self.assertRaises(pilot.PilotError):p.select(30,0)
        data['policy']['visits']=[[0]*9 for _ in range(162)]
        before=pilot.policy_digest(data['policy'])
        with self.assertRaises(pilot.PilotError):p.select(37.5,0)
        self.assertEqual(pilot.policy_digest(data['policy']),before)

    def test_initial_hot_box_is_rejected_and_soft_guard_overrides_q(self):
        data=synthetic_package()
        p=hold.HoldPolicy(mode='thu-rl',pilot=data)
        p.bind_sensor(data['sensor_id']);p.observe_output(0,0,0)
        with self.assertRaises(pilot.PilotError):p(0,core.Reading(0,31))
        p=hold.HoldPolicy(mode='thu-rl',pilot=data)
        p.bind_sensor(data['sensor_id']);p.observe_output(0,0,0)
        self.assertEqual(p(0,core.Reading(0,26)).lamp,75)
        p.observe_output(1,75,100);p.observe_output(326,75,100)
        self.assertEqual(p(326,core.Reading(326,37)).lamp,100)
        before=pilot.policy_digest(data['policy'])
        d=p(327,core.Reading(327,38))
        self.assertEqual((d.lamp,d.fan),(0,100))
        self.assertIsNone(p(926,core.Reading(926,37.5)))
        self.assertTrue(p.completed)
        self.assertEqual(pilot.policy_digest(data['policy']),before)
        self.assertEqual(p.metadata()['pilot']['q_updates'],0)

    def test_pilot_dry_run_never_opens_gpio_or_creates_output_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'policy.json';path.write_text(json.dumps(synthetic_package()),encoding='utf-8')
            folder=Path(tmp)/'output'
            with patch.object(core,'main',side_effect=AssertionError('GPIO')),contextlib.redirect_stdout(io.StringIO()):
                result=hold.main(['do','--bo-dieu-khien','thu-rl','--goi-thu-rl',str(path),'--dry-run','--out',str(folder)])
            self.assertEqual(result,0);self.assertFalse(folder.exists())
        with self.assertRaises(ValueError):hold.HoldPolicy(mode='thu-rl',seconds=120,pilot=synthetic_package())


if __name__=='__main__':unittest.main()
