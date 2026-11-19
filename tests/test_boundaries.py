import unittest
from auditforge.env import Session


class BoundaryTests(unittest.TestCase):
    def test_timeout_has_terminal_reward_and_frozen_flags(self):
        s=Session(); s.reset(22,{'clean':True},'train'); s.started-=61
        result=s.step({'tool':'calculator','expression':'1'})
        self.assertTrue(result[3]); self.assertEqual(result[1],s.report['reward'])
        self.assertGreater(result[1],0)
        again=s.step({'tool':'submit','findings':{}})
        self.assertEqual(again[2:4],(False,True)); self.assertEqual(again[1],0)

    def test_invalid_export_for_many_seeds(self):
        from auditforge.generator import generate
        from auditforge.export import export_episode
        import tempfile
        for seed in range(10):
            with tempfile.TemporaryDirectory() as directory: export_episode(generate(seed),directory)
