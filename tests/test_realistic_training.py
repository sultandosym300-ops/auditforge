import copy
import unittest
from auditforge.efficient_training import EfficientTrainer, load_trainer


class RealisticTrainingTests(unittest.TestCase):
    def test_legacy_checkpoint_and_compact_config_stay_unchanged(self):
        model = EfficientTrainer(31941, 'mixed')
        self.assertNotIn('profile', model.config(0))
        self.assertNotIn('world_profile', model.checkpoint())
        self.assertEqual(load_trainer(model.checkpoint()).checkpoint(), model.checkpoint())

    def test_extended_world_updates_restores_and_evaluates_without_learning(self):
        model = EfficientTrainer(314159, 'mixed', world_profile='realistic_v1', business_type='manufacturing')
        initial_weights = list(model.weights)
        for _ in range(20):
            model.train_episode()
        self.assertNotEqual(initial_weights, model.weights)
        restored = load_trainer(model.checkpoint())
        self.assertEqual(restored.config(2)['business_type'], 'manufacturing')
        self.assertEqual(restored.checkpoint(), model.checkpoint())
        model.train_episode()
        restored.train_episode()
        left, right = restored.checkpoint(), model.checkpoint()
        for cp in (left, right):
            for row in cp['history']:
                row.pop('seconds')
        self.assertEqual(left, right)
        before = copy.deepcopy(model.checkpoint())
        result = model.evaluate(3, 920741)
        self.assertEqual(before, model.checkpoint())
        self.assertEqual(len(result['results']), 4)
        for row in result['episodes']:
            self.assertEqual(row['steps'] - 1, row['inspection_steps'])

    def test_invalid_profile_metadata_is_rejected(self):
        for args in ({'world_profile':'unknown'}, {'world_profile':'realistic_v1','business_type':'unknown'},
                     {'world_profile':'realistic_v1','scenario':'recognition'}, {'business_type':'it'}):
            with self.assertRaises(ValueError):
                EfficientTrainer(381, **args)


if __name__ == '__main__':
    unittest.main()
