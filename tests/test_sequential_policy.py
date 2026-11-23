import copy
import unittest
from unittest.mock import patch

from auditforge.env import Session
from auditforge.sequential_policy import POLICIES, investigate, SequentialTrainer


class SequentialPolicyTests(unittest.TestCase):
    def test_self_critical_baseline_uses_a_second_frozen_public_rollout(self):
        from auditforge import sequential_policy
        calls=[]
        original=sequential_policy.investigate
        def record(step, initial, **options):
            calls.append((copy.deepcopy(initial),copy.deepcopy(options.get('weights'))))
            return original(step,initial,**options)
        with patch.object(sequential_policy,'investigate',side_effect=record):
            SequentialTrainer(seed=81,budget=8).train_episode()
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0],calls[1])

    def test_equal_budget_and_no_unsupported_claims(self):
        for policy in POLICIES:
            session = Session()
            initial, _ = session.reset(7013, dict(profile='investigation_v1', cases=4), 'train')
            result = investigate(session.step, initial, policy=policy, budget=8)
            self.assertTrue(session.done, policy)
            self.assertLessEqual(session.steps, 8)
            self.assertNotIn('error', session.report)
            self.assertEqual(session.report['fp'], 0)
            self.assertEqual(len(result['trajectory']), session.steps)

    def test_all_documents_recover_all_issues_and_clean_cases(self):
        for clean in (True, False):
            session = Session()
            initial, _ = session.reset(139, dict(profile='investigation_v1', clean=clean), 'train')
            investigate(session.step, initial, policy='budget_aware', budget=100)
            self.assertEqual(session.report['f1'], 1)
            self.assertLessEqual(session.steps, 20)

    def test_training_updates_parameters_and_evaluation_is_frozen(self):
        model = SequentialTrainer(seed=33, budget=8)
        before = list(model.weights)
        for _ in range(5):
            model.train_episode()
        self.assertNotEqual(model.weights, before)
        checkpoint = copy.deepcopy(model.checkpoint())
        result = model.evaluate(count=2, seed=701)
        self.assertTrue(result['episodes'])
        self.assertEqual(checkpoint, model.checkpoint())
        restored = SequentialTrainer.from_checkpoint(checkpoint)
        self.assertEqual(restored.checkpoint(), checkpoint)

    def test_checkpoint_rejects_code_nonfinite_and_invalid_metadata(self):
        model = SequentialTrainer()
        for field, value in [('weights', [float('nan')]*len(model.weights)),
                             ('algorithm', '__import__("os").system("bad")'),
                             ('budget', True), ('episodes', -1), ('critic', [1])]:
            checkpoint = model.checkpoint()
            checkpoint[field] = value
            with self.assertRaises(ValueError):
                SequentialTrainer.from_checkpoint(checkpoint)


if __name__ == '__main__':
    unittest.main()
