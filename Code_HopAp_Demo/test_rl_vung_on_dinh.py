"""Tests of band objective, not hardware effectiveness."""
import unittest
import rl_vung_on_dinh as app


class BandTests(unittest.TestCase):
    def test_previous_action_is_part_of_state(self):
        self.assertNotEqual(app.state_id(37.5,0,.5,4,False),app.state_id(37.5,0,.5,6,False))

    def test_all_state_indices_are_unique_and_in_range(self):
        states={app.state_id(t,d,m,a,g) for t in (36.8,37.,37.25,37.35,37.5,37.65,37.75,37.9,38.2)
                for d in (-.1,0,.1) for m in (.1,.35,.5,.65,.9) for a in range(9) for g in (False,True)}
        self.assertEqual(len(states),app.STATE_COUNT)
        self.assertEqual(min(states),0)
        self.assertEqual(max(states),app.STATE_COUNT-1)

    def r(self,before,after,h=.5,old=.5):
        return app.reward(before,after,h,.75,old,.75,2.,4.,False)

    def test_keep_level_near_center_preferred_over_unneeded_switch(self):
        self.assertGreater(self.r(37.5,37.5),self.r(37.5,37.5,.75))
        self.assertGreater(self.r(37.5,37.5),self.r(37.5,37.69))

    def test_recovery_improves_reward_and_outside_switch_cost_reduced(self):
        self.assertGreater(self.r(37.9,37.75),self.r(37.9,37.95))
        self.assertGreater(self.r(37.1,37.25),self.r(37.1,37.05))
        inside_cost=self.r(37.5,37.5)-self.r(37.5,37.5,.75)
        outside_cost=self.r(37.9,37.9)-self.r(37.9,37.9,.75)
        self.assertGreater(inside_cost,outside_cost)

    def test_guard_trigger_is_penalized(self):
        args=(37.9,38.,.5,.75,.5,.75,2.,4.)
        self.assertLess(app.reward(*args,True),app.reward(*args,False))


if __name__=='__main__':unittest.main()
