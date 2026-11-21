import unittest

from auditforge.generator import generate
from auditforge.reconcile import reconcile, validate


class AllocationRoundingTests(unittest.TestCase):
    def setUp(self):
        self.episode = generate(0, {'counts': {
            'duplicate_invoice': 0, 'payment_allocation': 3,
            'fx_conversion': 0, 'accounting_period': 0,
        }})
        self.mutation = next(
            change for change in self.episode['provenance']
            if change['before'][0]['debit_minor'] == 250217
        )
        self.issue = next(
            issue for issue in self.episode['truth']
            if issue['issue_id'] == self.mutation['issue_id']
        )

    def test_truth_and_public_recovery_match_posting_delta(self):
        before, after = self.mutation['before'][0], self.mutation['after'][0]
        self.assertEqual(after['debit_minor'], 225458)
        self.assertEqual(before['debit_minor'] - after['debit_minor'], 24759)
        self.assertEqual(self.issue['expected_amount_minor'], 24759)
        finding = next(result for result in reconcile(self.episode['public'])
                       if result['affected_ids'] == self.issue['affected_ids'])
        self.assertEqual(finding['claimed_amount_minor'], 24759)
        self.assertTrue(validate(self.episode))

    def test_validator_rejects_old_amount(self):
        self.issue['expected_amount_minor'] = 24758
        with self.assertRaisesRegex(AssertionError, 'Truth differs from'):
            validate(self.episode)

    def test_foreign_allocation_requires_published_fx_evidence(self):
        fx_ids = {rate['row_id'] for rate in self.episode['public']['fx']}
        evidence = self.issue['evidence_sets'][0]
        self.assertEqual(len(fx_ids.intersection(evidence)), 1)
        self.issue['evidence_sets'][0] = [item for item in evidence if item not in fx_ids]
        with self.assertRaisesRegex(AssertionError, 'Evidence set does not substantiate'):
            validate(self.episode)
