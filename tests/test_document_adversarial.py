"""Independent attacks on the document-level financial extension."""
import copy
import unittest

from auditforge.generator import generate
from scripts.document_adversarial import audit, check_documents, matcher_attacks


class DocumentAdversarialTests(unittest.TestCase):
    def test_independent_auditor_rejects_balanced_but_false_evidence(self):
        episode = generate(44102, dict(profile='investigation_v2', cases=2))
        self.assertTrue(check_documents(episode)['valid'])
        changed = copy.deepcopy(episode)
        docs = changed['public']['business']['source_documents']
        document = next(d for d in docs if d.get('records', {}).get('invoices'))
        document['records']['invoices'][0]['total_minor'] += 1
        report = check_documents(changed)
        self.assertFalse(report['valid'])
        self.assertTrue(report['errors'])

    def test_malformed_timestamp_and_boolean_money_are_rejected(self):
        episode = generate(71819, dict(profile='investigation_v2', cases=2))
        for table, field, value in [('payments', 'timestamp', '2026-13-99'),
                                    ('invoices', 'total_minor', True)]:
            changed = copy.deepcopy(episode)
            changed['public'][table][0][field] = value
            self.assertFalse(check_documents(changed)['valid'])

    def test_reference_judge_rejects_foreign_partial_and_duplicated_claims(self):
        config = dict(profile='investigation_v2', cases=2)
        episode = generate(7712, config)
        foreign = generate(8812, config)
        report = matcher_attacks(episode, foreign)
        self.assertTrue(report['differential_match'])
        self.assertTrue(report['attacks_do_not_inflate'])
        self.assertGreaterEqual(len(report['variants']), 9)

    def test_small_independent_audit_exercises_full_acquisition_and_replay(self):
        report = audit(seed=837917, count=1)
        self.assertEqual(report['independent_companies'], 4)
        self.assertTrue(all(report['checks'].values()), report['checks'])
        self.assertEqual(report['metamorphic']['comparisons'], 4)
        self.assertEqual(report['metamorphic']['full_budget_f1_changes'], 0)
        self.assertTrue(all(row['steps'] <= 100 for row in report['fixtures']))

    def test_audit_rejects_unbounded_or_noninteger_configuration(self):
        for settings in (dict(count=True), dict(count=0), dict(count=1001), dict(seed=True)):
            with self.assertRaises(ValueError):
                audit(**settings)


if __name__ == '__main__':
    unittest.main()
