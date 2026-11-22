import copy
import json
import unittest
from auditforge.env import Session
from auditforge.generator import generate, TYPES
from auditforge.matcher import oracle
from auditforge.policies import run_policy
from auditforge.proof import proof_suite, explain_completed, public_story, transform_for_proof
from auditforge.verify import transform


class ProofTests(unittest.TestCase):
    def test_six_matcher_cases_are_computed_and_distinguish_attacks(self):
        result = proof_suite(482901)
        cases = {r['id']: r for r in result['matcher_cases']}
        self.assertEqual(len(cases), 6)
        self.assertTrue(all(r['passed'] for r in cases.values()))
        self.assertEqual(cases['correct']['report']['tp'], 1)
        self.assertEqual(cases['missing_evidence']['report']['tp'], 0)
        self.assertEqual(cases['wrong_amount']['report']['tp'], 0)
        self.assertEqual(cases['duplicate_finding']['report']['fp'], 1)
        self.assertEqual(cases['false_positive']['report']['fp'], 1)
        self.assertEqual(cases['clean_silence']['report']['f1'], 1)
        self.assertTrue(result['reproducibility']['observations_equal'])
        self.assertTrue(result['reproducibility']['renaming']['report_equal'])
        self.assertEqual(result['historical_ci']['commit'], 'bd202ffc8d4e2a43d9a6c2d2b8ed5d98956c7d03')

    def test_explainer_requires_explicit_demo_and_terminal(self):
        session = Session()
        session.reset(12031, {'invoices':40}, 'train')
        with self.assertRaises(ValueError):
            explain_completed(session, demo=True)
        session.step({'tool':'submit','findings':oracle(session.episode)})
        for flag in (False, 1, 'true', None):
            with self.assertRaises(ValueError):
                explain_completed(session, demo=flag)
        session.mode='evaluation'
        with self.assertRaises(ValueError):
            explain_completed(session,demo=True)
        session.mode='train'
        result = explain_completed(session, demo=True)
        self.assertEqual(len(result['issues']), 4)
        self.assertTrue(all(r['calculation']['matches_declared_discrepancy'] for r in result['issues']))
        self.assertTrue(all(r['matched'] for r in result['issues']))

    def test_explanations_measure_interacting_changes_and_evidence(self):
        for interaction in (0,1,2):
            session = Session()
            initial,_ = session.reset(601849+interaction, {'invoices':40,'interaction':interaction}, 'train')
            run_policy(session,initial,'reconciliation')
            result = explain_completed(session, demo=True)
            self.assertTrue(all(r['calculation']['matches_declared_discrepancy'] for r in result['issues']))
            self.assertTrue(all(r['evidence_records'] for r in result['issues']))
            for issue in result['issues']:
                self.assertEqual(set(issue['affected_ids']),set(r['row_id'] for r in issue['current_rows']))

    def test_public_story_uses_actual_records_and_contains_no_private_branch(self):
        ep = generate(193184, {'invoices':40,'interaction':1})
        before = copy.deepcopy(ep['public'])
        result = public_story(ep['public'])
        self.assertEqual(before, ep['public'])
        self.assertEqual(result['summary']['invoices'], 40)
        self.assertEqual(len(result['chains']), 3)
        raw=json.dumps(result)
        for forbidden in ('"truth"','"provenance"','"expected_amount_minor"','"issue_id"'):
            self.assertNotIn(forbidden, raw)
        for chain in result['chains']:
            self.assertIn(chain['invoice'], ep['public']['invoices'])
            self.assertTrue(all(p in ep['public']['payments'] for p in chain['payments']))

    def test_portable_transform_matches_existing_native_transform(self):
        episode=generate(4159, {'invoices':40})
        for seed in (0,817):
            self.assertEqual(transform_for_proof(episode,seed,return_mapping=True),transform(episode,seed,return_mapping=True))

    def test_invalid_seed_is_rejected_and_proof_is_deterministic(self):
        for seed in (True,'23',None):
            with self.assertRaises(ValueError):
                proof_suite(seed)
        self.assertEqual(proof_suite(19381),proof_suite(19381))

if __name__ == '__main__': unittest.main()
