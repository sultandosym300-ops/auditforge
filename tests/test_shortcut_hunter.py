import unittest

from auditforge.env import Session
from auditforge.shortcut_hunter import features, metrics, public_snapshot, table_model


class ShortcutHunterTests(unittest.TestCase):
    def test_public_collection_consumes_real_pages_and_detaches_state(self):
        session = Session()
        initial, _ = session.reset(82941039, {'recognition_world': 1}, 'evaluation')
        snapshot, steps = public_snapshot(initial, session.step)
        self.assertEqual(session.steps, steps)
        self.assertEqual(snapshot['ledger'], session.public['ledger'])
        self.assertNotIn('truth', snapshot)
        feature_values = features(snapshot)
        snapshot['ledger'][0]['debit_minor'] += 1
        self.assertNotEqual(snapshot['ledger'], session.public['ledger'])
        self.assertFalse({'seed', 'truth', 'provenance'} & feature_values.keys())

    def test_metrics_distinguish_majority_accuracy_and_balanced_accuracy(self):
        result = metrics([True, False, False, False], [False]*4)
        self.assertEqual(result['accuracy'], .75)
        self.assertEqual(result['balanced_accuracy'], .5)
        self.assertEqual(result['f1'], 0)

    def test_prediction_has_no_label_access_and_handles_unseen_buckets(self):
        training = [({'amount_bucket':'a'},False), ({'amount_bucket':'b'},True)]
        predictor = table_model(training,['amount_bucket'])
        self.assertTrue(predictor({'amount_bucket':'b'}))
        self.assertFalse(predictor({'amount_bucket':'unseen'}))
        training.clear()
        self.assertTrue(predictor({'amount_bucket':'b'}))
