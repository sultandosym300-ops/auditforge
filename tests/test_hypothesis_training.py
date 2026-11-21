import copy
import unittest

from auditforge.efficient_training import decode
from auditforge.env import Session
from auditforge.hypothesis_training import HypothesisTrainer, hypotheses


class HypothesisTrainingTests(unittest.TestCase):
    def test_public_proposals_include_clean_near_misses_and_exact_proofs(self):
        session = Session()
        session.reset(71824, dict(invoices=40, interaction=1), 'train')
        public = session.episode['public']
        candidates = hypotheses(public)
        self.assertTrue(any(x[1] == 0 for _, _, x in candidates))
        actual = {(f['type'], tuple(f['affected_ids']), f['claimed_amount_minor']) for f in decode(public)}
        positive = {(f['type'], tuple(f['affected_ids']), f['claimed_amount_minor']) for _, f, x in candidates if x[1]}
        self.assertEqual(actual, positive)

    def test_acceptance_parameters_change_from_terminal_reward(self):
        model = HypothesisTrainer(acquisition_weights=[20.] * 21)
        for _ in range(10):
            model.train_episode()
        self.assertNotEqual(model.weights, [0.] * 12)
        self.assertEqual(model.checkpoint()['status'], 'experimental-not-production')

    def test_missing_acquisition_never_creates_source_proofs(self):
        model = HypothesisTrainer(acquisition_weights=[-20.] * 21)
        session = Session()
        initial, _ = session.reset(5671, dict(invoices=40), 'test')
        _, decisions = model.run(session, initial)
        self.assertEqual(decisions, [])
        self.assertEqual(session.final['findings'], [])

    def test_invalid_frozen_weights_rejected(self):
        for weights in (None, [], [float('nan')] * 21):
            with self.assertRaises(ValueError):
                HypothesisTrainer(acquisition_weights=weights)

    def test_financial_features_control_real_acceptance_and_evaluation_is_frozen(self):
        model = HypothesisTrainer(acquisition_weights=[20.] * 21)
        model.weights = [-10., 20., 0.] * 4
        before = model.checkpoint()
        for ablation, expected_f1 in ((None, 1.), ('zero_features', 0.)):
            session = Session()
            initial, _ = session.reset(791481, dict(invoices=40, interaction=1), 'evaluation')
            _, decisions = model.run(session, initial, ablation=ablation)
            self.assertEqual(session.report['f1'], expected_f1)
            if ablation is None:
                self.assertTrue(any(d[2] == 0 for d in decisions))
                self.assertTrue(any(d[2] == 1 for d in decisions))
        self.assertEqual(model.checkpoint(), before)

    def test_training_reward_changes_acceptance_parameters(self):
        model = HypothesisTrainer(acquisition_weights=[20.] * 21)
        before = list(model.weights)
        for _ in range(5):
            model.train_episode()
        self.assertNotEqual(model.weights, before)

    def test_checkpoint_roundtrip_rejects_corruption(self):
        model = HypothesisTrainer(acquisition_weights=[20.] * 21)
        model.train_episode()
        checkpoint = model.checkpoint()
        self.assertEqual(HypothesisTrainer.from_checkpoint(checkpoint).checkpoint(), checkpoint)
        for key, value in (('weights', [float('inf')] * 12), ('baseline', float('nan')),
                           ('kinds', None), ('episodes', True), ('version', True)):
            broken = copy.deepcopy(checkpoint)
            broken[key] = value
            with self.assertRaises(ValueError):
                HypothesisTrainer.from_checkpoint(broken)

    def test_explicit_experimental_checkpoint_roundtrip(self):
        model = HypothesisTrainer(acquisition_weights=[20.] * 21)
        model.train_episode()
        restored = HypothesisTrainer.from_checkpoint(model.checkpoint())
        self.assertEqual(restored.checkpoint(), model.checkpoint())
        broken = model.checkpoint()
        broken['weights'][0] = float('inf')
        with self.assertRaises(ValueError):
            HypothesisTrainer.from_checkpoint(broken)
