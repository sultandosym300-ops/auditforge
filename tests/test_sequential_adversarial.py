"""Independent public-boundary and financial regression checks for v1 research."""
import copy
import json
import random
import unittest
from unittest.mock import patch

from auditforge.env import Session
from auditforge.generator import generate
from auditforge.sequential_policy import POLICIES, investigate
from auditforge.sequential_training import SequentialTrainer
from auditforge.verify import transform


def public_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from public_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from public_keys(child)


def visible_identifiers(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ('row_id', 'doc_id') and isinstance(child, str):
                yield child
            yield from visible_identifiers(child)
    elif isinstance(value, list):
        for child in value:
            yield from visible_identifiers(child)


class SequentialAdversarialTests(unittest.TestCase):
    def test_both_financial_families_fully_solvable_by_bulk_and_routed_sources(self):
        for family in ('procurement', 'closing_transfer'):
            for seed in (0, 1, 17, 20261123):
                for policy in ('reconciliation', 'budget_aware'):
                    with self.subTest(family=family, seed=seed, policy=policy):
                        session = Session()
                        initial, _ = session.reset(seed, dict(profile='investigation_v1', family=family), 'evaluation')
                        investigate(session.step, initial, policy=policy, budget=100)
                        self.assertEqual(session.report['f1'], 1)
                        self.assertEqual(session.report['fp'], 0)
                        self.assertLessEqual(session.steps, 100)

    def test_all_baselines_share_initial_observations_budget_and_acquired_evidence(self):
        frozen = None
        for policy in POLICIES:
            session = Session()
            initial, _ = session.reset(920471, dict(profile='investigation_v1'), 'evaluation')
            encoded = json.dumps(initial, sort_keys=True)
            if frozen is None:
                frozen = encoded
            self.assertEqual(encoded, frozen)
            known = set()
            calls = []
            def boundary(action):
                calls.append(copy.deepcopy(action))
                self.assertLessEqual(len(calls), 9)
                if action.get('tool') == 'submit':
                    for finding in action['findings']['findings']:
                        self.assertLessEqual(set(finding['evidence_ids']), known)
                        self.assertLessEqual(set(finding['affected_ids']), known)
                response = session.step(action)
                known.update(visible_identifiers(response[0]))
                self.assertEqual(response[1], 0, 'Evaluation reward must remain hidden')
                self.assertEqual(response[4], {})
                return response
            result = investigate(boundary, initial, policy=policy, budget=9)
            self.assertTrue(result['terminal'][2])
            self.assertEqual(calls[-1]['tool'], 'submit')
            self.assertEqual(session.report['fp'], 0)

    def test_public_initial_and_source_packets_contain_no_private_answers(self):
        for clean in (False, True):
            session = Session()
            initial, _ = session.reset(78199, dict(profile='investigation_v1', clean=clean), 'evaluation')
            observations = [initial]
            for candidate in initial['manifest']['investigations']:
                document_id = candidate['document_id']
                for _ in range(candidate['query_cost']):
                    observation, reward, terminated, truncated, info = session.step(dict(tool='get_document', doc_id=document_id))
                    observations.append(observation)
                    self.assertEqual((reward, terminated, truncated, info), (0, False, False, {}))
                    record = observation['result']
                    if 'next_document_id' in record:
                        document_id = record['next_document_id']
            leaked = set(public_keys(observations)) & {'truth', 'provenance', 'pristine', 'seed', 'expected_amount_minor', 'evidence_sets'}
            self.assertEqual(leaked, set())

    def test_full_solve_survives_identifier_renaming_and_record_permutations(self):
        for family in ('procurement', 'closing_transfer'):
            episode = generate(41871, dict(profile='investigation_v1', family=family))
            changed = transform(episode, 100572)
            random.Random(15).shuffle(changed['public']['manifest']['investigations'])
            for value in (episode, changed):
                for policy in ('budget_aware', 'reconciliation'):
                    session = Session()
                    with patch('auditforge.env.generate', return_value=copy.deepcopy(value)):
                        initial, _ = session.reset(0, {}, 'evaluation')
                    investigate(session.step, initial, policy=policy, budget=100)
                    self.assertEqual((session.report['f1'], session.report['fp']), (1, 0))

    def test_clean_companies_do_not_require_false_accusations(self):
        for policy in POLICIES:
            session = Session()
            initial, _ = session.reset(951711, dict(profile='investigation_v1', clean=True), 'evaluation')
            investigate(session.step, initial, policy=policy, budget=8)
            self.assertEqual((session.report['f1'], session.report['fp']), (1, 0), policy)

    def test_validation_never_updates_parameters_optimizer_or_training_history(self):
        model = SequentialTrainer(seed=1409, budget=8)
        model.train_episode()
        checkpoint = model.checkpoint()
        model.evaluate(count=3, seed=901219, policies=('learned', 'budget_aware'), family='closing_transfer')
        self.assertEqual(model.checkpoint(), checkpoint)

    def test_checkpoint_rejects_negative_validation_f1(self):
        model = SequentialTrainer(seed=52, budget=8)
        model.train_episode()
        checkpoint = model.checkpoint()
        checkpoint['history'][0]['validation_f1'] = -.5
        with self.assertRaises(ValueError):
            SequentialTrainer.from_checkpoint(checkpoint)

    def test_checkpoint_rejects_boolean_history_counters(self):
        model = SequentialTrainer(seed=52, budget=8)
        model.train_episode()
        for field in ('episode', 'optimizer_steps'):
            checkpoint = model.checkpoint()
            checkpoint['history'][0][field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                SequentialTrainer.from_checkpoint(checkpoint)


if __name__ == '__main__':
    unittest.main()
