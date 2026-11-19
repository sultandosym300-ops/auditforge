import copy
import json
import unittest
import tempfile
from pathlib import Path
from auditforge.export import export_episode
from auditforge.generator import generate
from auditforge.matcher import evaluate, oracle
from auditforge.env import AuditEnv
from auditforge.reconcile import reconcile, validate


class CoreTests(unittest.TestCase):
    def test_export_heterogeneous_ledger_fields(self):
        e = generate(12)
        with tempfile.TemporaryDirectory() as folder:
            export_episode(e, folder)
            self.assertIn('allocation_source_minor', next(Path(folder).rglob('ledger.csv')).read_text())
    def test_deterministic_and_independently_recoverable(self):
        for seed in range(20):
            config = {'clean': seed < 5, 'interaction': 1 + seed % 2 if 5 <= seed < 10 else 0}
            a = generate(seed, config)
            self.assertEqual(a, generate(seed, config))
            validate(a)
            report = evaluate(a['public']['manifest']['episode_id'], a['truth'], {'episode_id': a['public']['manifest']['episode_id'], 'findings': reconcile(a['public'])}, 0)
            self.assertEqual(report['f1'], 1, (seed, report))

    def test_evidence_and_duplicate_penalty(self):
        a = generate(918, {})
        eid = a['public']['manifest']['episode_id']
        answer = oracle(a)
        self.assertEqual(evaluate(eid, a['truth'], answer, 0)['reward'], 1)
        answer['findings'].append(copy.deepcopy(answer['findings'][0]))
        self.assertLess(evaluate(eid, a['truth'], answer, 0)['reward'], 1)
        answer = oracle(a)
        for f in answer['findings']:
            f['evidence_ids'] = []
        self.assertEqual(evaluate(eid, a['truth'], answer, 0)['tp'], 0)

    def test_clean(self):
        a = generate(312, {'clean': True})
        self.assertEqual(a['truth'], [])
        self.assertEqual(reconcile(a['public']), [])
        eid = a['public']['manifest']['episode_id']
        self.assertEqual(evaluate(eid, [], {'episode_id': eid, 'findings': []}, 3)['reward'], .994)

    def test_process_contract(self):
        with AuditEnv() as env:
            obs, info = env.reset(123, {})
            self.assertEqual(obs['steps_remaining'], 100)
            self.assertNotIn('seed', json.dumps(obs))
            obs, reward, terminated, truncated, info = env.step({'tool': 'list_records', 'table': 'ledger', 'limit': 50})
            self.assertEqual(len(obs['result']['records']), 50)
            self.assertEqual(reward, 0)
            for _ in range(99):
                obs, reward, terminated, truncated, info = env.step({'tool': 'unknown'})
            self.assertTrue(truncated)
            self.assertEqual(obs['findings'], [])
            self.assertEqual(env.step({'tool': 'submit', 'findings': {}})[1], 0)

if __name__ == '__main__':
    unittest.main()
