import copy
import unittest

from auditforge.counterfactual import challenge, diagnostics, make_pair, surface_audit
from auditforge.efficient_training import EfficientTrainer
from auditforge.financial_audit import audit_episode
from auditforge.matcher import oracle


class CounterfactualTests(unittest.TestCase):
    def test_pairs_are_financially_valid_with_exact_controls(self):
        for index in range(25):
            metadata, clean, dirty = make_pair(index, 712945)
            self.assertTrue(audit_episode(clean)['valid'])
            self.assertTrue(audit_episode(dirty)['valid'])
            self.assertEqual(clean['truth'], [])
            self.assertTrue(dirty['truth'])
            if metadata['type'] == 'recognition':
                self.assertEqual(clean['public']['ledger'], dirty['public']['ledger'])
                self.assertEqual(len(metadata['controls']['changed_document_ids']), 2)
            else:
                self.assertTrue(metadata['controls']['same_sources'])
                self.assertTrue(metadata['controls']['changed_row_ids'])

    def test_challenge_freezes_checkpoint_and_separates_weak_baseline(self):
        model = EfficientTrainer(314159, 'mixed')
        for _ in range(300):
            model.train_episode()
        before = copy.deepcopy(model.checkpoint())
        result = challenge(model, 5, 819345)
        self.assertEqual(before, model.checkpoint())
        self.assertEqual(result['data_validation'], {'passed': 10, 'failed': 0})
        scores = {p['name']:p for p in result['policies']}
        self.assertEqual(scores['reconciliation']['pair_consistency'], 1)
        self.assertEqual(scores['trained']['metrics']['f1'], 1)
        self.assertEqual(scores['random']['pair_consistency'], 0)
        self.assertEqual(scores['random']['metrics']['f1'], 0)
        for policy in result['policies']:
            self.assertEqual(len(policy['by_type']), 5)
            self.assertTrue(all(r['terminated'] for p in policy['pairs'] for r in (p['clean'], p['dirty'])))
            for pair in policy['pairs']:
                for run in (pair['clean'], pair['dirty']):
                    self.assertEqual(len(run['trajectory']), run['metrics']['steps'])
                    self.assertTrue(run['trajectory'][-1]['terminated'])
                    self.assertTrue(all(step['reward'] == 0 for step in run['trajectory']))
                    text = __import__('json').dumps(run['trajectory'])
                    for forbidden in ('expected_amount_minor', 'evidence_sets', 'issue_id', 'provenance'):
                        self.assertNotIn('"' + forbidden + '"', text)

    def test_diagnostics_identify_amount_evidence_and_missing(self):
        _, _, ep = make_pair(2, 123541)
        findings = oracle(ep)['findings']
        self.assertEqual(diagnostics(ep['truth'], findings), [])
        changed = copy.deepcopy(findings)
        changed[0]['claimed_amount_minor'] += 1
        self.assertEqual(diagnostics(ep['truth'], changed)[0]['reason'], 'amount_mismatch')
        changed = copy.deepcopy(findings)
        changed[0]['evidence_ids'] = []
        self.assertEqual(diagnostics(ep['truth'], changed)[0]['reason'], 'insufficient_evidence')
        self.assertEqual(diagnostics(ep['truth'], [])[0]['reason'], 'missing_finding')
        self.assertEqual(diagnostics(ep['truth'], findings + findings)[0]['reason'], 'duplicate_finding')

    def test_deterministic_public_report_and_input_validation(self):
        model = EfficientTrainer(13, 'mixed')
        a, b = challenge(model, 5, 175, False), challenge(model, 5, 175, False)
        self.assertEqual(a, b)
        for count in (True, 0, 101):
            with self.assertRaises(ValueError):
                challenge(model, count)

    def test_surface_screen_preserves_recognition_histograms(self):
        screen = surface_audit(5, 412178)
        recognition = next(p for p in screen['pairs'] if p['type'] == 'recognition')
        self.assertTrue(all(recognition['equal_features'].values()))
        duplicate = next(p for p in screen['pairs'] if p['type'] == 'duplicate_invoice')
        self.assertFalse(duplicate['equal_features']['counts'])


if __name__ == '__main__':
    unittest.main()
