import unittest
import numpy as np
import hoc_action_keo_dai as app


class MacroTests(unittest.TestCase):
    def setUp(self):
        self.actions=np.array([(h,f) for h in (0.,.25,.5,.75,1.) for f in (.75,1.) if (h,f)!=(1.,1.)])
        # Deterministic constant-temperature plant isolates decision-time behavior.
        self.p=np.array([0.,0.,0.,0.,0.,0.,35.,.875,25.,31.,39.,0.])

    def test_macro_holds_full_window_and_discounts_by_elapsed_steps(self):
        result=app.macro(self.p,self.actions,37.5,0.,.5,4,False,4,37.5,.2,.25,4.,np.zeros(120),np.zeros(120),0)
        self.assertEqual(result[6],6)
        self.assertAlmostEqual(result[5],.99**6)
        self.assertAlmostEqual(result[4],sum(.99**j for j in range(6)))
        outside=app.macro(self.p,self.actions,37.1,0.,.5,4,False,4,37.5,.2,.25,4.,np.zeros(120),np.zeros(120),0)
        self.assertEqual(outside[6],2)

    def test_guard_interrupts_before_scheduled_end(self):
        self.p[0]=.3
        result=app.macro(self.p,self.actions,37.8,0.,.5,4,False,6,37.8,.2,.25,4.,np.zeros(120),np.zeros(120),0)
        self.assertEqual(result[6],1)
        self.assertTrue(result[3])

    def test_stable_temperature_needs_only_twenty_decisions_in_ten_minutes(self):
        q=np.zeros((2430,9));q[:,4]=100
        v=np.ones_like(q,dtype=np.int64)
        met,trace=app.rollout(self.p,self.actions,np.array([37.5,0.,.5,4.]),np.zeros(120),np.zeros(120),37.5,.2,q,v)
        self.assertEqual(met[5],20)
        self.assertEqual(met[2],0)
        self.assertEqual(met[3],0)
        self.assertEqual(np.count_nonzero(trace[:,5]),20)
        np.testing.assert_array_equal(trace[:,2],np.full(120,50.))


if __name__=='__main__':unittest.main()
