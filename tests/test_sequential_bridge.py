import copy
from pathlib import Path
import unittest


class SequentialBridgeTests(unittest.TestCase):
    def test_real_bridge_training_roundtrip_evaluation_and_demo(self):
        namespace={}
        exec((Path(__file__).resolve().parents[1]/'web/public/python-bridge.py').read_text(encoding='utf8'),namespace)
        request=namespace['request']
        checkpoint=request('training_create',dict(world_profile='investigation_v1',seed=71,budget=6))
        self.assertEqual(checkpoint['format'],'auditforge-sequential-policy')
        request('training_step',{})
        checkpoint=request('training_checkpoint',{})
        self.assertEqual(request('training_import',dict(checkpoint=checkpoint)),checkpoint)
        before=copy.deepcopy(checkpoint)
        result=request('training_evaluate',dict(count=1,seed=19))
        self.assertEqual(request('training_checkpoint',{}),before)
        self.assertEqual(len(result['results']),8)
        demo=request('training_demo',{})
        self.assertEqual(len(demo['runs']),4)
        self.assertTrue(all(run['trajectory'][-1]['terminated'] for run in demo['runs']))
        self.assertTrue(all(run['steps']<=6 for run in demo['runs']))


if __name__=='__main__':unittest.main()
