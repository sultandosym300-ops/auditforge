"""Exercise the same Python interface shipped to the real browser worker."""
import copy
from pathlib import Path
import unittest


class DocumentBridgeTests(unittest.TestCase):
    def test_new_world_training_import_validation_and_document_trace(self):
        scope = {}
        exec((Path(__file__).resolve().parents[1] / 'web/public/python-bridge.py').read_text(encoding='utf8'), scope)
        request = scope['request']
        cp = request('training_create', dict(world_profile='investigation_v2', seed=220022,
                     budget=20, algorithm='actor_critic', architecture='linear', family='service_milestone'))
        self.assertEqual(cp['format'], 'auditforge-document-policy')
        request('training_step', {})
        cp = request('training_checkpoint', {})
        self.assertEqual(cp['episodes'], 1)
        self.assertEqual(request('training_import', {'checkpoint': cp}), cp)
        frozen = copy.deepcopy(cp)
        evaluation = request('training_evaluate', {'count': 1, 'seed': 220023})
        self.assertEqual(request('training_checkpoint', {}), frozen)
        self.assertTrue({'generator_blind', 'oracle_knowledge', 'learned'} <=
                        {row['category'] for row in evaluation['results']})
        demo = request('training_demo', {})
        self.assertTrue(demo['runs'])
        for run in demo['runs']:
            self.assertLessEqual(run['steps'], 20)
            self.assertTrue(run['trajectory'][-1]['terminated'])
            for event in run['trajectory']:
                result = event['observation'].get('result', {})
                self.assertNotEqual(result.get('kind'), 'department_source_packet')


if __name__ == '__main__':
    unittest.main()
