import unittest
import giu_hanh_dong_rl as app


class TimingTests(unittest.TestCase):
    def test_in_band_action_is_nominal_30_seconds(self):
        self.assertEqual(app.action_steps(37.5,37.5,.2,False)*app.DT_S,30)
        self.assertEqual(app.action_steps(37.1,37.5,.2,False)*app.DT_S,10)
        self.assertEqual(app.action_steps(37.5,37.5,.2,True)*app.DT_S,5)

    def test_hold_inside_and_interrupt_for_band_transition_or_guard(self):
        self.assertFalse(app.interrupt_action(37.5,37.6,37.5,.2,False))
        self.assertTrue(app.interrupt_action(37.6,37.75,37.5,.2,False))
        self.assertTrue(app.interrupt_action(37.2,37.4,37.5,.2,False))
        self.assertTrue(app.interrupt_action(37.5,37.6,37.5,.2,True))


if __name__=='__main__':unittest.main()
