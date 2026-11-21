import copy
import json
import unittest

from auditforge.env import Session
from auditforge.training import Trainer, INITIAL_WEIGHTS, episode_seed, investigate


class TrainingTests(unittest.TestCase):
    def test_reward_learning_improves_frozen_document_acquisition_holdout(self):
        trainer=Trainer(314159)
        for _ in range(100):
            trainer.train_episode()
        before=trainer.checkpoint()
        result=trainer.evaluate(8,904621)
        metrics={row['policy']:row for row in result['results']}
        self.assertGreater(metrics['trained']['f1'],metrics['untrained']['f1'])
        self.assertGreater(metrics['trained']['reward'],metrics['untrained']['reward'])
        self.assertEqual(trainer.checkpoint(),before)

    def test_terminal_rewards_really_update_weights_and_repeat(self):
        first,second = Trainer(314159),Trainer(314159)
        for _ in range(12):
            a,b=first.train_episode(),second.train_episode()
            self.assertEqual({k:v for k,v in a.items() if k!='seconds'},
                             {k:v for k,v in b.items() if k!='seconds'})
        self.assertNotEqual(first.weights,INITIAL_WEIGHTS)
        self.assertEqual(first.weights,second.weights)
        self.assertEqual(first.optimizer_steps,12)

    def test_json_checkpoint_resumes_identical_update(self):
        original=Trainer(80719,'duplicate')
        for _ in range(8):
            original.train_episode()
        checkpoint=json.loads(json.dumps(original.checkpoint()))
        restored=Trainer.from_checkpoint(checkpoint)
        self.assertEqual(original.weights,restored.weights)
        original.train_episode()
        restored.train_episode()
        self.assertEqual(original.weights,restored.weights)
        self.assertEqual(original.baseline,restored.baseline)
        checkpoint['weights'][0]=999
        self.assertNotEqual(restored.weights[0],999)

    def test_holdout_uses_fresh_namespace_and_does_not_update(self):
        trainer=Trainer(729)
        trainer.train_episode()
        before=trainer.checkpoint()
        result=trainer.evaluate(4,729)
        self.assertEqual(trainer.checkpoint(),before)
        self.assertNotEqual(episode_seed(729,'train',0),episode_seed(729,'holdout',0))
        self.assertEqual(result['results'][0]['policy'],'untrained')
        for row in result['episodes']:
            self.assertLessEqual(row['steps'],100)

    def test_policy_only_receives_public_step_and_all_evidence_observed(self):
        session=Session()
        initial,_=session.reset(681037,{'counts':{'accounting_period':2}},'evaluation')
        seen=set()
        def public_step(action):
            if action['tool']=='submit':
                for finding in action['findings']['findings']:
                    self.assertTrue(set(finding['evidence_ids']+finding['affected_ids'])<=seen)
            result=session.step(action)
            self.assertEqual(result[1],0)
            if action['tool']=='list_records':
                for row in result[0]['result']['records']:
                    seen.add(row['row_id'])
            if action['tool']=='get_record':
                seen.add(result[0]['result']['doc_id'])
            return result
        terminal,_=investigate(public_step,initial,[10,0,0,0,0])
        self.assertTrue(terminal[2])
        self.assertEqual(session.report['f1'],1)

    def test_incompatible_or_nonfinite_checkpoint_rejected(self):
        pristine=Trainer().checkpoint()
        for key,value in [('environment','unknown'),('weights',[float('nan')]*5),
                          ('algorithm','PPO'),('episodes',True),('baseline',float('inf'))]:
            data=copy.deepcopy(pristine)
            data[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                Trainer.from_checkpoint(data)
