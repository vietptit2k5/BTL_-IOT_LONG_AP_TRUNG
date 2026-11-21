"""Independent arithmetic checks on synthetic records only."""
import copy
import unittest
import so_sanh_giu_nhiet as compare


class ComparisonTests(unittest.TestCase):
    def test_time_weighting_and_clipping_exclude_warm_and_postcool(self):
        samples=[dict(t=t,temperature=v) for t,v in [(0,30),(1,37.5),(2,38.5),(3,30)]]
        m=compare.temperature_metrics(samples,1,3)
        self.assertAlmostEqual(m['mae_c'],.5)
        self.assertEqual(m['in_band_015_pct'],50)
        self.assertEqual(m['mean_c'],38)
        self.assertEqual(m['std_c'],.5)
        self.assertEqual((m['min_c'],m['max_c']),(37.5,38.5))
        m=compare.temperature_metrics(samples,1,2.5)
        self.assertAlmostEqual(m['mae_c'],1/3)

    def test_long_gaps_do_not_become_held_temperature(self):
        samples=[dict(t=t,temperature=v) for t,v in [(0,37.5),(1,37.5),(10,38),(11,38)]]
        m=compare.temperature_metrics(samples,0,11)
        self.assertEqual(m['covered_s'],2)
        self.assertEqual(m['mae_c'],.25)

    def test_command_changes_are_not_sample_count_or_initial_command(self):
        commands=[(0,.75,1),(10,.5,.75),(15,.25,1),(20,.25,1),(25,0,1)]
        m=compare.command_metrics(commands,10,25)
        self.assertEqual(m['setpoint_changes'],1)
        self.assertEqual(m['lamp_setpoint_changes'],1)
        self.assertEqual(m['fan_setpoint_changes'],1)
        self.assertAlmostEqual(m['mean_lamp_duty_pct'],100/3)
        self.assertEqual(m['total_lamp_variation_percentage_points'],25)
        self.assertEqual(m['action_seconds'],{'50/75':5,'25/100':10})

    def test_pair_checks_reject_duplicates_and_different_protection(self):
        base=dict(controller='doi-chung',sha256='a',sensors=['28-test'],frequencies=[100],
            profile=dict(control_period_s=5,soft_guard_off_c=38,soft_guard_resume_c=37,hard_cutoff_c=40),
            temperature=dict(mae_c=.1,std_c=.2,in_band_015_pct=50),
            commands=dict(mean_lamp_duty_pct=60,mean_fan_duty_pct=90,setpoint_changes=10))
        rl=copy.deepcopy(base);rl.update(controller='thu-rl',sha256='b')
        rl['temperature'].update(mae_c=.05,std_c=.1,in_band_015_pct=75)
        self.assertEqual(compare.compare(base,rl)['mae_reduction_pct'],50)
        rl['sha256']='a'
        with self.assertRaises(ValueError):compare.compare(base,rl)
        rl['sha256']='b';rl['profile']['soft_guard_off_c']=39
        with self.assertRaises(ValueError):compare.compare(base,rl)


if __name__=='__main__':unittest.main()
