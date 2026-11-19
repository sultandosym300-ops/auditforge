from datetime import datetime, timedelta
import unittest

from auditforge.generator import generate
from auditforge.reconcile import reconcile, validate


class JuryPeriodTests(unittest.TestCase):
    def test_legitimate_payments_either_side_of_close(self):
        for month, following in (('2028-02', '2028-03'), ('2026-12', '2027-01')):
            with self.subTest(month=month):
                episode = generate(93812, {
                    'clean': True, 'period_month': month,
                    'timezone': '-03:30', 'boundary_payments': True,
                })
                public = episode['public']
                manifest = public['manifest']
                self.assertEqual(manifest['period_start'], month + '-01T00:00:00-03:30')
                self.assertEqual(manifest['period_end'], following + '-01T00:00:00-03:30')
                end = datetime.fromisoformat(manifest['period_end'])
                timestamps = {datetime.fromisoformat(p['timestamp']) for p in public['payments']}
                self.assertTrue({end - timedelta(seconds=1), end + timedelta(seconds=1)} <= timestamps)
                self.assertEqual(reconcile(public), [])
                self.assertTrue(validate(episode))

    def test_period_month_rejects_invalid_dates(self):
        for month in ('2028-00', '2028-13', '2028-2', '2100-01', 202811, None):
            with self.subTest(month=month), self.assertRaises(ValueError):
                generate(1, {'period_month': month})
