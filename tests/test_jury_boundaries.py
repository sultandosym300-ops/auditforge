import unittest

from auditforge.env import AuditEnv, Session


class JuryBoundaries(unittest.TestCase):
    def test_invalid_falsy_configs_are_not_replaced_with_defaults(self):
        with AuditEnv('evaluation') as env:
            for config in (False, 0, '', []):
                with self.subTest(config=config), self.assertRaises(ValueError):
                    env.reset(731, config)
            observation, info = env.reset(731)
            self.assertEqual((observation['steps_remaining'], info), (100, {}))

    def test_ledger_lookup_requires_an_unambiguous_row_id(self):
        session = Session()
        session.reset(731, {}, 'evaluation')
        row = session.public['ledger'][0]
        for field in ('invoice_id', 'payment_id'):
            with self.subTest(field=field):
                observation, *_ = session.step({
                    'tool': 'get_record', 'table': 'ledger', 'id': row[field],
                })
                self.assertEqual(observation['error'], 'invalid_request')
        observation, *_ = session.step({
            'tool': 'get_record', 'table': 'ledger', 'id': row['row_id'],
        })
        self.assertEqual(observation['result'], row)

    def test_reset_observation_cannot_mutate_evaluator_public_state(self):
        session = Session()
        initial, _ = session.reset(731, {}, 'evaluation')
        source_id = initial['manifest']['episode_id']
        initial['manifest']['episode_id'] = 'changed'
        initial['policy']['amount_tolerance_minor'] = 42
        self.assertEqual(session.public['manifest']['episode_id'], source_id)
        self.assertEqual(session.public['policy']['amount_tolerance_minor'], 0)

    def test_invalid_last_action_truncates_until_reset(self):
        session = Session()
        session.reset(731, {}, 'evaluation')
        for _ in range(99):
            self.assertEqual(session.step({'tool': 'calculator', 'expression': '1'})[1:], (0, False, False, {}))
        observation, reward, terminated, truncated, info = session.step(None)
        self.assertEqual(observation, {'error': 'invalid_request', 'findings': [], 'steps_remaining': 0})
        self.assertEqual((reward, terminated, truncated, info), (0, False, True, {}))
        self.assertEqual(session.step({'tool': 'submit'})[1:], (0, False, True, {}))
        initial, _ = session.reset(732, {}, 'evaluation')
        self.assertEqual(initial['steps_remaining'], 100)
        self.assertIsNone(session.report)
