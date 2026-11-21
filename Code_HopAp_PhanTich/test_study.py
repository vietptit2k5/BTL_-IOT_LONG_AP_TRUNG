"""Checks for fair/reproducible simulation comparisons, not hardware tests."""
import unittest
import numpy as np
import qtable_study as s


class StudyChecks(unittest.TestCase):
    def test_same_rollout_replays_same_noise_and_disturbances(self):
        b=s.scenario_bank(4,72)
        args=(np.zeros((81,9)),np.zeros((81,9),dtype=np.int64),2,True,0,
              np.array([.2,0.,0.]),b[0][1],b[1][1],b[2][1],b[3][1],b[4][1])
        m1,t1=s.rollout(*args)
        np.random.normal(size=200)
        m2,t2=s.rollout(*args)
        np.testing.assert_array_equal(m1,m2)
        np.testing.assert_array_equal(t1,t2)

    def test_training_has_fixed_horizon_and_finite_q(self):
        q,v,_=s.train(5,2,True,3.,.1,81)
        self.assertEqual(q.shape,(135,9))
        self.assertEqual(v.sum(),5*240)
        self.assertTrue(np.isfinite(q).all())

    def test_circulation_never_commands_fan_off(self):
        self.assertTrue(np.all(s.FAN>0))
        self.assertEqual(len(s.FAN)*len(s.HEAT),9)

    def test_heater_history_distinguishes_identical_temperature_trends(self):
        self.assertNotEqual(s.state_id(37.5,37.3,0.,2),s.state_id(37.5,37.3,1.,2))
        self.assertEqual(s.state_id(37.5,37.3,0.,1),s.state_id(37.5,37.3,1.,1))

    def test_guard_overrides_all_controllers_under_hot_start(self):
        p=np.array([120.,1100.,.7,.8,8.,8.,.3,.1])
        q=np.zeros((135,9));q[:,8]=100.
        v=np.ones((135,9),dtype=np.int64)
        m,tr=s.rollout(q,v,2,True,2,np.zeros(3),p,28.,39.,0,123)
        self.assertGreater(m[6],0)
        self.assertEqual(tr[0,7],1.)


if __name__=='__main__':
    unittest.main()
