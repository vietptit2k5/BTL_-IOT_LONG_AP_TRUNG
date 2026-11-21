import unittest
import numpy as np
import hoc_ba_giai_doan as app


class StageLearningTests(unittest.TestCase):
    def setUp(self):
        self.p=np.array([-.1653616355,-.02058371984,-.1422966921,.38099842575,
                         -.13249781187,.07633251368,35.9314679416,.875,25.,31.25,38.375,.0362221162])
        self.actions=np.array([(h,f) for h in (0.,.25,.5,.75,1.) for f in (.75,1.) if (h,f)!=(1.,1.)])
        self.goals=np.array([[37.8,.2],[37.5,.2],[37.2,.2]])

    def test_goal_relative_encoding_and_reward(self):
        for target in (37.8,37.5,37.2):
            self.assertEqual(app.goal_state(target,0.,.5,4,False,target,.2),app.encode(37.5,0.,.5,4,False))
            self.assertAlmostEqual(app.goal_reward(target,target,.5,.75,.5,.75,.25,2.,False,target,.2),1.)
            self.assertLess(app.goal_reward(target,target+.4,.5,.75,.5,.75,.25,2.,False,target,.2),0)

    def test_training_reproducible(self):
        pool=np.array([[37.5,0.,.5,4.],[37.,.02,.6,6.]])
        a,b=app.train(self.p,self.actions,pool,37.2,.2,500,11,.25,2.)
        c,d=app.train(self.p,self.actions,pool,37.2,.2,500,11,.25,2.)
        np.testing.assert_array_equal(a,c);np.testing.assert_array_equal(b,d)
        self.assertEqual(a.shape,(2430,9))

    def test_guard_override_and_no_mutation(self):
        q=np.zeros((3,2430,9));q[:,:,8]=100
        v=np.ones_like(q,dtype=np.int64);saved=q.copy()
        met,trace=app.rollout(self.p,self.actions,self.goals,np.zeros(20,dtype=np.int64),
            np.array([38.1,0.,.8,8.]),np.zeros(20),np.zeros(20),0,q,v)
        self.assertEqual(trace[0,5],0)
        self.assertEqual(trace[0,6],100)
        self.assertGreater(met[8],0)
        np.testing.assert_array_equal(q,saved)

    def test_stage_change_retains_thermal_memory(self):
        q=np.zeros((3,2430,9));v=np.ones_like(q,dtype=np.int64)
        schedule=np.array([0,1,2],np.int64)
        _,trace=app.rollout(self.p,self.actions,self.goals,schedule,np.array([37.5,0.,.6,4.]),
                           np.zeros(3),np.zeros(3),2,q,v)
        self.assertEqual(trace[:,2].tolist(),[37.8,37.5,37.2])
        # Fixed50/75 mode: stage switches do not zero the physical-memory observer.
        expected=.6
        for row in trace:
            expected+=(.5-expected)*(1-np.exp(-5/25))
            self.assertAlmostEqual(row[8],expected)


if __name__=='__main__':unittest.main()
