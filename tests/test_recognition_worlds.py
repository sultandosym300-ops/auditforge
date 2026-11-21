import unittest
from collections import Counter
from datetime import datetime, timedelta

from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.generator import generate
from auditforge.reconcile import validate


class RecognitionWorlds(unittest.TestCase):
    def test_world_views_and_accounting(self):
        configs = [
            dict(shuffle=False, invoices=40, period_month='2028-02', timezone='+05:45'),
            dict(shuffle=True, invoices=80, period_month='2099-12', timezone='-03:30'),
        ]
        for seed, config in enumerate(configs, start=85021):
            episodes = [generate(seed, dict(config, recognition_world=w)) for w in range(4)]
            self.assertEqual([len(ep['truth']) for ep in episodes], [0, 2, 2, 0])
            self.assertEqual(len({ep['public']['manifest']['episode_id'] for ep in episodes}), 4)
            books = [ep['public'] for ep in episodes]
            for i, j in ((0, 2), (1, 3)):
                self.assertEqual(books[i]['ledger'], books[j]['ledger'])
            for i, j in ((0, 1), (2, 3)):
                self.assertEqual(books[i]['invoices'], books[j]['invoices'])
            for case, ep in enumerate(episodes):
                with self.subTest(seed=seed, world=case):
                    result = audit_episode(ep)
                    self.assertTrue(result['valid'], result['errors'])
                    self.assertTrue(validate(ep))
                    for invoice in books[case]['invoices']:
                        self.assertEqual(datetime.fromisoformat(invoice['due_at']) -
                                         datetime.fromisoformat(invoice['issued_at']), timedelta(days=30))
                    self.assertEqual(books[0]['payments'], books[case]['payments'])
                    self.assertEqual(books[0]['fx'], books[case]['fx'])
                    self.assertEqual(books[0]['policy'], books[case]['policy'])
                    original = books[0]['manifest'].copy()
                    original['episode_id'] = books[case]['manifest']['episode_id']
                    self.assertEqual(original, books[case]['manifest'])
                    if ep['truth']:
                        self.assertEqual(len({r['expected_amount_minor'] for r in ep['truth']}), 1)
                        self.assertEqual(len({r['affected_ids'][0] for r in ep['truth']}), 2)
            # Aggregating across tables without identifying obligations cannot expose
            # either direction, even if all timestamps and monetary amounts are retained.
            for book in books[1:]:
                for name, keys in [('invoices', ('issued_at','total_minor')),
                                   ('ledger', ('timestamp','account','debit_minor','credit_minor'))]:
                    def histogram(b):
                        return Counter(tuple(r[k] for k in keys) for r in b[name])
                    self.assertEqual(histogram(books[0]), histogram(book))

    def test_invalid_or_contradictory_world_configuration(self):
        for invalid in (True, 1.0, -1, 4, '1', '', {}, [], None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                generate(123, {'recognition_world': invalid})
        for key, value in [('counts', {}), ('interaction', 0), ('clean', False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                generate(123, {'recognition_world': 1, key: value})

    def test_blind_assignment_is_an_exact_replay_of_one_world(self):
        labels = set()
        totals = set()
        for seed in range(7908134, 7908141):
            candidate = generate(seed, {'recognition_world': 'blind'})
            quartet = [generate(seed, {'recognition_world': i}) for i in range(4)]
            self.assertEqual(sum(candidate == item for item in quartet), 1)
            self.assertEqual(candidate, generate(seed, {'recognition_world': 'blind'}))
            labels.add(len(candidate['truth']))
            totals.add(quartet[1]['truth'][0]['expected_amount_minor'])
        self.assertEqual(labels, {0, 2})
        self.assertGreater(len(totals), 4)

    def test_episode_identifiers_and_step_interface(self):
        session = Session()
        initial, info = session.reset(9273541, {'recognition_world': 'blind'}, 'evaluation')
        self.assertEqual(info, {})
        self.assertEqual(initial['steps_remaining'], 100)
        self.assertNotIn('recognition_world', initial['manifest'])
        self.assertNotIn('recognition_world', initial['policy'])
        observation, reward, done, truncated, info = session.step(
            dict(tool='list_records', table='invoices', limit=1))
        self.assertIn('records', observation['result'])
        self.assertEqual((reward, done, truncated, info), (0,False,False,{}))
