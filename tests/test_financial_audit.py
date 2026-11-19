import copy
import unittest
from fractions import Fraction
from unittest.mock import patch

from auditforge.generator import generate
from auditforge.financial_audit import audit_episode, round_half_even, run_mass_audit
from auditforge.reconcile import validate


class FinancialAuditTests(unittest.TestCase):
    def test_signed_half_even_is_exact(self):
        self.assertEqual([round_half_even(Fraction(n, 2)) for n in range(-7, 8)],
                         [-4, -3, -2, -2, -2, -1, 0, 0, 0, 1, 2, 2, 2, 3, 4])

    def test_both_interactions_and_clean_without_policy_detector(self):
        with patch('auditforge.reconcile.reconcile', side_effect=RuntimeError('forbidden')):
            for config in ({'clean': True}, {'interaction': 1}, {'interaction': 2}):
                report = audit_episode(generate(187123, config))
                self.assertTrue(report['valid'], report['errors'])

    def test_rejects_internally_wrong_source_lines(self):
        episode = generate(123, {'clean': True})
        for branch in ('public', 'pristine'):
            for invoice in episode[branch]['invoices']:
                invoice['line_items'][0]['quantity'] = 2
        self.assertFalse(audit_episode(episode)['valid'])
        with self.assertRaises(AssertionError):
            validate(episode)

    def test_rejects_unrelated_credit_document(self):
        episode = generate(123, {'interaction': 2})
        old = next(i['related_credit_doc_id'] for i in episode['public']['invoices'] if 'related_credit_doc_id' in i)
        new = next(p['doc_id'] for p in episode['public']['payments'] if p['kind'] == 'settlement')
        for branch in ('public', 'pristine'):
            inv = next(i for i in episode[branch]['invoices'] if 'related_credit_doc_id' in i)
            inv['related_credit_doc_id'] = new
        for issue in episode['truth']:
            issue['evidence_sets'] = [[new if item == old else item for item in ids] for ids in issue['evidence_sets']]
        self.assertFalse(audit_episode(episode)['valid'])
        with self.assertRaises(AssertionError):
            validate(episode)

    def test_rejects_wrong_evidence_and_causal_mirror(self):
        episode = generate(187123)
        wrong = copy.deepcopy(episode)
        wrong['truth'][0]['evidence_sets'] = [[episode['public']['invoices'][0]['doc_id']]]
        self.assertFalse(audit_episode(wrong)['valid'])
        wrong = copy.deepcopy(episode)
        wrong['provenance'][0]['after'].pop()
        self.assertFalse(audit_episode(wrong)['valid'])

    def test_mass_manifest_is_reproducible(self):
        first = run_mass_audit(8, 571203)
        second = run_mass_audit(8, 571203)
        self.assertEqual(first, second)
        self.assertEqual(first['checked'], 8)
        self.assertEqual(first['failed'], 0, first['failures'])
