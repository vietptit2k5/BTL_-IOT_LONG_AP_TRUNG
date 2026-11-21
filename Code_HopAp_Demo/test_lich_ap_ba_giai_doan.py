import contextlib
from datetime import datetime,timedelta,timezone
import io
import unittest
import lich_ap_ba_giai_doan as app


class ScheduleTests(unittest.TestCase):
    def test_day_boundaries(self):
        for day,expected in ((1,0),(10,0),(11,1),(17,1),(18,2),(21,2)):
            self.assertEqual(app.stage_for_day(day)['id'],expected)
        for day in (0,22,-1,1.5,True):
            with self.assertRaises(ValueError):app.stage_for_day(day)

    def test_elapsed_calendar_and_restart_does_not_reset_day(self):
        start=datetime.fromisoformat('2026-11-20T08:00:00+07:00')
        for elapsed,day,stage in ((0,1,0),(10*86400-1,10,0),(10*86400,11,1),(17*86400,18,2)):
            got,setting=app.stage_at(start,start+timedelta(seconds=elapsed))
            self.assertEqual((got,setting['id']),(day,stage))
        self.assertEqual(app.stage_at(start,start.astimezone(timezone.utc))[0],1)
        with self.assertRaises(ValueError):app.stage_at(start,start-timedelta(seconds=1))
        with self.assertRaises(ValueError):app.stage_at(start,start+timedelta(days=21))
        with self.assertRaises(ValueError):app.stage_at(start.replace(tzinfo=None),start)

    def test_config_is_explicitly_experimental_and_copies_are_independent(self):
        self.assertFalse(app.PROFILE['deploy_allowed'])
        self.assertFalse(app.PROFILE['biological_tolerance_validated'])
        first=app.stage_for_day(1)
        self.assertTrue(first['guard_overlap'])
        self.assertEqual((first['lower_c'],first['upper_c']),(37.6,38.))
        first['days'][0]=0
        self.assertEqual(app.stage_for_day(1)['days'][0],1)

    def test_cli_is_read_only_calendar(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(app.main(['--ngay','18']),0)
        self.assertIn('37.2',output.getvalue())


if __name__=='__main__':unittest.main()
