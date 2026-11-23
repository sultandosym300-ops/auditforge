import copy
import unittest

from auditforge.efficient_training import EfficientTrainer,load_trainer


class LegacyCheckpointCounterTests(unittest.TestCase):
    def test_boolean_history_counters_are_rejected_in_existing_format(self):
        model=EfficientTrainer(seed=11)
        model.train_episode()
        for field in ('episode','optimizer_steps'):
            with self.subTest(field=field):
                value=copy.deepcopy(model.checkpoint())
                value['history'][0][field]=True
                with self.assertRaises(ValueError):load_trainer(value)


if __name__=='__main__':unittest.main()
