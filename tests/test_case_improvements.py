import copy
import unittest

from auditforge.financial_audit import audit_episode
from auditforge.generator import TYPES, generate
from auditforge.matcher import evaluate, oracle
from auditforge.reconcile import reconcile, validate
from auditforge.shortcut import run


class CaseImprovements(unittest.TestCase):
    def test_fx_fingerprint_does_not_replace_financial_reconciliation(self):
        comparison = run(8012034097, 20)
        self.assertEqual(comparison['fx_fingerprint_mean_f1'], 0)
        self.assertEqual(comparison['reconciliation_mean_f1'], 1)

    def test_clean_boundary_companies_contain_legitimate_refund_links(self):
        for seed in range(604381, 604401):
            episode = generate(seed, {
                'clean': True, 'boundary_payments': True,
                'period_month': '2031-02', 'timezone': '-03:30',
            })
            public = episode['public']
            refunds = [wallet for wallet in public['payments'] if wallet['kind'] == 'refund']
            self.assertGreater(len(refunds), 1)
            self.assertEqual(
                {doc['related_credit_doc_id'] for doc in public['invoices'] if doc.get('related_credit_doc_id')},
                {payment['doc_id'] for payment in refunds},
            )
            self.assertTrue(audit_episode(episode)['valid'])
            self.assertEqual(reconcile(public), [])

    def test_evidence_ablation_on_asymmetric_interactions(self):
        for index in range(20):
            config = {
                'interaction': 1 + index % 2, 'invoices': 40 + (index % 5)*17,
                'timezone': ('+13:45', '-09:30')[index % 2],
                'period_month': ('2032-02', '2032-12')[index % 2],
                'boundary_payments': True,
                'counts': dict(zip(TYPES, ((2, 3, 1, 2), (3, 1, 2, 3))[index % 2])),
            }
            episode = generate(970261093117 + index, config)
            self.assertTrue(validate(episode))
            self.assertTrue(audit_episode(episode)['valid'])
            self.assertEqual(len(episode['truth']), sum(config['counts'].values()))
            answer = oracle(episode)
            score = evaluate(answer['episode_id'], episode['truth'], answer, 0)
            self.assertEqual((score['f1'], score['reward']), (1, 1))
            for finding_index, finding in enumerate(answer['findings']):
                for removed in finding['evidence_ids']:
                    incomplete = copy.deepcopy(answer)
                    incomplete['findings'][finding_index]['evidence_ids'].remove(removed)
                    score = evaluate(answer['episode_id'], episode['truth'], incomplete, 0)
                    self.assertEqual((score['tp'], score['fp'], score['fn']),
                                     (len(answer['findings'])-1, 1, 1))
