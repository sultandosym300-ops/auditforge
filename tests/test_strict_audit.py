import copy
import subprocess
import sys
import time
import unittest

from auditforge.agent_runner import send_line
from auditforge.env import Session
from auditforge.generator import generate, TYPES
from auditforge.reconcile import validate
from auditforge.verify import transform, check_transitions


class StrictAuditTests(unittest.TestCase):
    def test_corrupt_source_payment_is_rejected(self):
        episode = generate(123, {'clean': True})
        for branch in ('public', 'pristine'):
            episode[branch]['payments'][0]['amount_minor'] += 100000000
        with self.assertRaises(AssertionError):
            validate(episode)

    def test_balanced_but_wrong_accounting_is_rejected(self):
        episode = generate(123, {'clean': True})
        for branch in ('public', 'pristine'):
            for row in episode[branch]['ledger']:
                if row['account'] == 'cash':
                    row['account'] = 'unrelated_asset'
        with self.assertRaises(AssertionError):
            validate(episode)

    def test_existing_but_unrelated_evidence_is_rejected(self):
        episode = generate(123)
        for issue in episode['truth']:
            issue['evidence_sets'] = [[episode['public']['invoices'][0]['doc_id']]]
        with self.assertRaises(AssertionError):
            validate(episode)

    def test_null_or_absent_get_record_id_consumes_step(self):
        session = Session()
        session.reset(1, {}, 'evaluation')
        for record_id in (None, '', 42, False):
            result = session.step({'tool': 'get_record', 'table': 'ledger', 'id': record_id})
            self.assertEqual(result[0]['error'], 'invalid_request')
        self.assertEqual(session.steps, 4)

    def test_invalid_generator_config_is_rejected(self):
        for config in ({'clean': 'false'}, {'shuffle': 0}, {'interaction': True},
                       {'timezone': '+05:99'}, {'timezone': '+24:00'}, {'timezone': 5}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                generate(1, config)

    def test_generation_does_not_share_mutable_exponents(self):
        episode = generate(123)
        before = copy.deepcopy(episode)
        episode['public']['manifest']['currency_exponents']['KZT'] = 99
        self.assertEqual(generate(123), before)

    def test_alternate_configs_and_renamed_evidence(self):
        for seed in range(8):
            config = {'invoices': 40+seed, 'interaction': seed % 3,
                      'timezone': ['+05:30', '-03:30'][seed % 2],
                      'counts': {kind: 3 for kind in TYPES}}
            episode = generate(seed, config)
            self.assertTrue(validate(episode))
            self.assertTrue(validate(transform(episode, seed+100)))
            self.assertTrue(check_transitions(episode, transform(episode, seed+100)))

    def test_missing_mirror_provenance_is_rejected(self):
        episode = generate(123)
        episode['provenance'][0]['after'].pop()
        with self.assertRaises(AssertionError):
            validate(episode)

    def test_second_interaction_contains_two_error_types_on_same_obligation(self):
        episode = generate(123, {'interaction': 2})
        duplicate = next(t for t in episode['truth'] if t['type'] == 'duplicate_invoice')
        period = next(t for t in episode['truth'] if t['type'] == 'accounting_period')
        self.assertTrue(set(duplicate['affected_ids']) & set(period['affected_ids']))
        self.assertTrue(validate(episode))

    def test_policy_backpressure_has_deadline(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'],
                                   stdin=subprocess.PIPE, text=True)
        started = time.monotonic()
        try:
            with self.assertRaises(TimeoutError):
                send_line(process, {'observation': 'x' * 1000000}, started+.1)
            self.assertLess(time.monotonic()-started, 2)
        finally:
            process.kill()
            process.wait(timeout=3)
            process.stdin.close()

