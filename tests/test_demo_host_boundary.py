"""Demonstration access stays on the trusted host, outside policy actions."""
import json
import unittest

from auditforge.env import AuditEnv
from auditforge.policies import run_policy


class DemoHostBoundaryTests(unittest.TestCase):
    def test_public_payment_scenario_propagates_without_mutating_the_episode(self):
        with AuditEnv(mode='train') as env:
            initial, _ = env.reset(771983, {'profile':'realistic_v1','business_type':'trade','clean':True})
            before = env.evaluator_story()
            event = next(e for e in before['business']['events'] if e['type']=='customer_receipt')
            result = env.evaluator_receipt_scenario(event['event_id'], event['amount_minor']-100)
            self.assertEqual(result['after']['cash_minor']-result['before']['cash_minor'], -100)
            self.assertEqual(result['after']['receivable_minor']-result['before']['receivable_minor'], 100)
            self.assertEqual(env.evaluator_story(), before)
            self.assertIsNone(env.evaluator_report())
            source = before['business']['source_documents'][0]
            observation, _, _, _, _ = env.step({'tool':'get_document','doc_id':source['doc_id']})
            self.assertEqual(observation['result'], source)
            self.assertEqual(observation['steps_remaining'], 99)
            observation, _, _, _, _ = env.step({'tool':'world_counterfactual','event_id':event['event_id'],'amount_minor':1})
            self.assertEqual(observation['error'], 'invalid_request')

    def test_host_explanation_requires_terminal_open_demo(self):
        with AuditEnv(mode='train') as env:
            initial, _ = env.reset(771983)
            story = env.evaluator_story()
            self.assertEqual(story['manifest']['episode_id'], initial['manifest']['episode_id'])
            for field in ('"truth"', '"provenance"', '"expected_amount_minor"'):
                self.assertNotIn(field, json.dumps(story))
            with self.assertRaises(ValueError):
                env.evaluator_demo(demo=True)
            observation, _, terminated, _, _ = env.step({'tool': 'host_demo', 'demo': True})
            self.assertEqual(observation['error'], 'invalid_request')
            self.assertFalse(terminated)
            run_policy(env, initial, 'reconciliation')
            with self.assertRaises(ValueError):
                env.evaluator_demo()
            explanation = env.evaluator_demo(demo=True)
            self.assertEqual(len(explanation['issues']), 4)
            self.assertTrue(all(i['calculation']['matches_declared_discrepancy'] for i in explanation['issues']))

    def test_closed_evaluation_cannot_use_demonstration_after_submission(self):
        with AuditEnv(mode='evaluation') as env:
            initial, _ = env.reset(771983, {'clean': True})
            run_policy(env, initial, 'reconciliation')
            self.assertEqual(env.evaluator_report()['f1'], 1)
            with self.assertRaises(ValueError):
                env.evaluator_demo(demo=True)


if __name__ == '__main__':
    unittest.main()
