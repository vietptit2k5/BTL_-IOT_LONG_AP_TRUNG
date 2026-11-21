import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import ke_hoach_do_day_du as app
import do_nhiet_hop as core


class PlanTests(unittest.TestCase):
    def test_complete_unique_matrix_and_bounded_batches(self):
        batches=app.build_plan()
        triples=[(b['target_c'],b['lamp_pct'],f) for b in batches for f in b['fan_order']]
        expected={(t,h,f) for t in (37.2,37.5,37.8) for h in (0,25,50,75,100) for f in (75,100)}
        self.assertEqual(set(triples),expected)
        self.assertEqual(len(triples),30)
        self.assertEqual(len(batches),15)
        self.assertTrue(all(b['limit_s']<=core.MAX_SURVEY_SECONDS for b in batches))
        self.assertTrue(all(not b['executed'] for b in batches))

    def test_repeated_order_is_reversed(self):
        batches=app.build_plan(2)
        self.assertEqual(len(batches),30)
        for a,b in zip(batches[:15],reversed(batches[15:])):
            self.assertEqual((a['stage'],a['lamp_pct']),(b['stage'],b['lamp_pct']))
            self.assertEqual(a['fan_order'],b['fan_order'][::-1])

    def test_generation_never_opens_gpio(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'plan'
            with patch.object(core,'main',side_effect=AssertionError('GPIO')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(app.main(['--out',str(folder)]),0)
            result=json.loads((folder/'ke_hoach.json').read_text(encoding='utf-8'))
            self.assertEqual(result['purpose'],'PLAN_ONLY_NOT_MEASURED_DATA')
            self.assertEqual(result['total_combinations'],30)
        with self.assertRaises(ValueError):app.build_plan(0)


if __name__=='__main__':unittest.main()
