import copy
import json
import unittest

from auditforge.env import Session
from auditforge.efficient_training import EfficientTrainer, INITIAL_WEIGHTS, investigate, load_trainer
from auditforge.training import Trainer


class EfficientTrainingTests(unittest.TestCase):
    def test_reward_updates_bulk_acquisition_and_holdout_is_frozen(self):
        model = EfficientTrainer(314159, 'period')
        for _ in range(300):
            model.train_episode()
        checkpoint = model.checkpoint()
        scores = {r['policy']:r for r in model.evaluate(16, 182630141)['results']}
        self.assertNotEqual(model.weights, INITIAL_WEIGHTS)
        self.assertEqual(model.checkpoint(), checkpoint)
        self.assertGreaterEqual(scores['trained']['f1'], .95)
        self.assertLess(scores['trained']['steps'], 10)
        self.assertGreater(scores['trained']['reward'], scores['reconciliation']['reward'])

    def test_legacy_and_source_checkpoint_dispatch_resume(self):
        legacy = Trainer(17)
        legacy.train_episode()
        self.assertIsInstance(load_trainer(legacy.checkpoint()), Trainer)
        model = EfficientTrainer(61794, 'mixed')
        for _ in range(8):
            model.train_episode()
        restored = load_trainer(json.loads(json.dumps(model.checkpoint())))
        self.assertEqual(restored.weights, model.weights)
        model.train_episode()
        restored.train_episode()
        self.assertEqual(restored.weights, model.weights)
        self.assertEqual(restored.baseline, model.baseline)

    def test_declined_sources_cannot_support_findings(self):
        session = Session()
        initial,_ = session.reset(12019, {'counts':{'accounting_period':2}}, 'evaluation')
        actions = []
        def step(action):
            actions.append(action)
            return session.step(action)
        investigate(step, initial, [-20.]*21)
        self.assertEqual(actions[-1]['findings']['findings'], [])
        self.assertTrue(all(a['tool']=='submit' or a['table']=='ledger' for a in actions))
        self.assertEqual(session.report['tp'], 0)

    def test_missing_rate_acquisition_cannot_create_fx_proofs(self):
        session = Session()
        initial,_ = session.reset(94718, {'counts':{'fx_conversion':2}}, 'evaluation')
        log = []
        terminal,_ = investigate(session.step, initial, [20.]*14+[-20.]*7, log=log)
        self.assertTrue(terminal[2])
        self.assertFalse(any(row['action'].get('table')=='fx' for row in log))
        self.assertEqual(session.report['tp'], 0)
        self.assertEqual(log[-1]['action']['findings']['findings'], [])

    def test_documentary_decoder_obeys_public_evidence_and_all_four_types(self):
        session = Session()
        initial,_ = session.reset(791481, {'interaction':1}, 'evaluation')
        observed = set()
        def step(action):
            if action['tool']=='submit':
                for finding in action['findings']['findings']:
                    self.assertTrue(set(finding['affected_ids']+finding['evidence_ids']) <= observed)
            result = session.step(action)
            if action['tool']=='list_records':
                for item in result[0]['result']['records']:
                    observed.add(item.get('row_id', item.get('doc_id')))
            return result
        terminal,_ = investigate(step, initial, [20.]*21)
        self.assertTrue(terminal[2])
        self.assertEqual(session.report['f1'], 1)
        self.assertLessEqual(session.steps, 100)

    def test_incomplete_imported_metrics_cannot_crash_the_browser_chart(self):
        for trainer in (EfficientTrainer(8123), Trainer(8123)):
            trainer.train_episode()
            checkpoint = trainer.checkpoint()
            checkpoint["history"][0] = {}
            with self.assertRaises(ValueError):
                load_trainer(checkpoint)

    def test_invalid_parameters_and_architecture_are_rejected(self):
        original = EfficientTrainer().checkpoint()
        for key,value in [('weights',[float('nan')]*21),('weights',[1.]*20),
                          ('learning_rate',float('inf')),('learning_rate',0),
                          ('version',1),('tables',['invoices']),('episodes',True),
                          ('baseline',2),('architecture','other')]:
            candidate = copy.deepcopy(original)
            candidate[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                load_trainer(candidate)

    def test_budget_respected_when_ledger_is_partially_observed(self):
        session = Session()
        initial,_ = session.reset(10419, {'invoices':200}, 'evaluation')
        for _ in range(97):
            session.step(dict(tool='calculator', expression='1'))
        initial['steps_remaining'] = 3
        terminal,_ = investigate(session.step, initial, [20.]*21)
        self.assertTrue(terminal[2])
        self.assertFalse(terminal[3])
        self.assertEqual(session.steps, 100)
