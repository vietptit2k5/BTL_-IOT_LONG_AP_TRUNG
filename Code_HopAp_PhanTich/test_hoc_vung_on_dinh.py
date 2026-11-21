"""Compiled simulation must agree with pure runtime math. No GPIO."""
import sys
from pathlib import Path
import unittest
import numpy as np
import hoc_vung_on_dinh as app

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Code_HopAp_Demo'))
import rl_vung_on_dinh as pure
import phan_tich_reward as old


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.p=np.array([-.1653616355,-.02058371984,-.1422966921,.38099842575,
                         -.13249781187,.07633251368,35.9314679416,.875,25.,31.25,38.375,.0362221162])
        self.actions=np.array([(h,f) for h in (0.,.25,.5,.75,1.) for f in (.75,1.) if (h,f)!=(1.,1.)])

    def test_compiled_model_matches_existing_model(self):
        model=old.ThermalModel(self.p[:6].tolist(),*self.p[6:])
        for t in (36.7,37.3,37.5,37.7):
            for h,f in self.actions:
                np.testing.assert_allclose(app.step(t,.02,.45,h,f,self.p,.01),model.step(t,.02,.45,h,f,.01))

    def test_encoders_match_original_and_pure(self):
        for t in np.arange(36.5,38.25,.0625):
            for d in (-.1,0.,.1):
                for m in (.1,.5,.9):
                    expected=2*old.state_id(t,d,m,0,37.5,.5,1.,1)
                    self.assertEqual(app.old_state(t,d,m,False),expected)
                    self.assertEqual(app.encode(t,d,m,4,False),pure.state_id(t,d,m,4,False))

    def test_reproducible_training_and_immutable_rollout(self):
        pool=np.array([[37.5,0.,.5,4],[37.1,.02,.6,6]])
        q,v,_=app.train(self.p,self.actions,pool,500,11,.5,4.)
        q2,v2,_=app.train(self.p,self.actions,pool,500,11,.5,4.)
        np.testing.assert_array_equal(q,q2);np.testing.assert_array_equal(v,v2)
        before=q.copy()
        app.rollout(self.p,self.actions,pool[0],np.zeros(120),np.zeros(120),0,q,v)
        np.testing.assert_array_equal(q,before)

    def test_guard_overrides_favored_high_heater_and_unseen_is_counted(self):
        q=np.zeros((pure.STATE_COUNT,9));q[:,8]=100
        visits=np.ones_like(q,dtype=np.int64)
        m,trace=app.rollout(self.p,self.actions,np.array([38.1,0.,.8,8.]),np.zeros(120),np.zeros(120),0,q,visits)
        self.assertEqual(trace[0,2],0)
        self.assertEqual(trace[0,3],100)
        self.assertGreater(m[8],0)
        visits[:]=0
        m,_=app.rollout(self.p,self.actions,np.array([37.5,0.,.5,4.]),np.zeros(120),np.zeros(120),0,q,visits)
        self.assertGreater(m[7],0)


if __name__=='__main__':unittest.main()
