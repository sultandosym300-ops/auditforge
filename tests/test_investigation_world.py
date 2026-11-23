import copy
import json
import unittest

from auditforge.env import Session
from auditforge.generator import generate
from auditforge.matcher import evaluate
from auditforge.reconcile import reconcile, validate


class InvestigationWorldTests(unittest.TestCase):
    def test_versioned_world_is_deterministic_and_fully_resolvable(self):
        config = dict(profile='investigation_v1', cases=4)
        episode = generate(23871, config)
        self.assertEqual(episode, generate(23871, config))
        self.assertTrue(validate(episode))
        public = episode['public']
        score = evaluate(public['manifest']['episode_id'], episode['truth'],
                         dict(episode_id=public['manifest']['episode_id'], findings=reconcile(public)), 0)
        self.assertEqual(score['f1'], 1)
        self.assertEqual(len(public['manifest']['investigations']), 4)

    def test_chains_are_public_tools_and_do_not_expose_private_labels(self):
        session = Session()
        initial, _ = session.reset(8311, dict(profile='investigation_v1', cases=4), 'train')
        serialized = json.dumps(initial)
        for key in ('truth', 'provenance', 'pristine', 'expected_amount', 'seed'):
            self.assertNotIn(key, serialized)
        candidate = initial['manifest']['investigations'][0]
        document = candidate['document_id']
        packets = 0
        for _ in range(candidate['query_cost']):
            response = session.step(dict(tool='get_document', doc_id=document))[0]['result']
            self.assertNotIn('truth', response)
            if 'records' in response:
                packets += 1
                self.assertEqual(response['case_id'], candidate['case_id'])
            else:
                document = response['next_document_id']
        self.assertEqual(packets, 1)

    def test_clean_and_transfer_worlds_remain_valid(self):
        for family in ('procurement', 'closing_transfer'):
            episode = generate(1414, dict(profile='investigation_v1', cases=4, family=family, clean=True))
            self.assertTrue(validate(episode))
            self.assertEqual(episode['truth'], [])
            self.assertEqual(reconcile(episode['public']), [])

    def test_unknown_options_and_invalid_costs_are_rejected(self):
        for change in (dict(cases=True), dict(cases=30), dict(family='unknown'), dict(clean='yes'), dict(hidden_truth=True)):
            with self.assertRaises(ValueError):
                generate(1, dict(profile='investigation_v1', **change))

    def test_copying_observation_does_not_mutate_evaluator(self):
        session = Session()
        initial, _ = session.reset(9, dict(profile='investigation_v1', cases=4), 'train')
        before = copy.deepcopy(session.public)
        initial['manifest']['investigations'].clear()
        self.assertEqual(session.public, before)


if __name__ == '__main__':
    unittest.main()
