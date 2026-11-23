import copy
import unittest

from auditforge.sequential_training import SequentialTrainer
from scripts.sequential_adversarial import audit


class SequentialAuditScriptTests(unittest.TestCase):
    def test_small_audit_has_real_counts_and_disclosed_minimum_scope(self):
        report = audit(seed=913710, count=1, cases=4, budgets=(5, 100))
        self.assertEqual(report['independent_companies'], 4)
        self.assertTrue(report['checks']['full_solve'])
        self.assertTrue(report['checks']['zero_false_positives'])
        self.assertTrue(report['checks']['no_private_fields'])
        self.assertTrue(report['checks']['evaluation_reward_hidden'])
        self.assertTrue(report['checks']['acquired_evidence_only'])
        self.assertTrue(report['checks']['metadata_only_zero_tp'])
        self.assertEqual(report['metamorphic']['companies'], 4)
        self.assertEqual(report['metamorphic']['full_budget_f1_changes'], 0)
        self.assertIn('not a global minimum', report['action_cost_scope'])
        self.assertTrue(report['rows'])
        for fixture in report['fixtures']:
            self.assertGreaterEqual(fixture['minimum_route_witness_actions'], 1)
            self.assertLessEqual(fixture['minimum_route_witness_actions'], fixture['complete_route_actions'])
            self.assertLessEqual(fixture['complete_route_actions'], 19)
        for row in report['rows']:
            self.assertLessEqual(row['steps'], row['budget'])
            if row['budget'] == 100:
                self.assertEqual(row['f1'], 1)

    def test_audit_rejects_invalid_settings_and_does_not_train(self):
        for settings in (dict(count=0), dict(count=True), dict(cases=7), dict(budgets=(1,)), dict(seed=True)):
            with self.assertRaises(ValueError):
                audit(**settings)
        model = SequentialTrainer(seed=51, budget=8)
        before = copy.deepcopy(model.checkpoint())
        audit(seed=5718, count=1, cases=4, budgets=(100,))
        self.assertEqual(model.checkpoint(), before)


if __name__ == '__main__':
    unittest.main()
