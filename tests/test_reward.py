import copy
import unittest
from auditforge.generator import generate
from auditforge.matcher import evaluate, oracle
from auditforge.env import Session


class RewardTests(unittest.TestCase):
    def setUp(self):
        self.e=generate(3498,{}); self.answer=oracle(self.e); self.eid=self.answer['episode_id']
    def score(self,a=None,steps=0,truth=None): return evaluate(self.eid,self.e['truth'] if truth is None else truth,self.answer if a is None else a,steps)
    def test_01_correct(self): self.assertEqual(self.score()['reward'],1)
    def test_02_silence(self): self.assertEqual(self.score(dict(episode_id=self.eid,findings=[]))['reward'],-1)
    def test_03_clean_empty(self): self.assertEqual(self.score(dict(episode_id=self.eid,findings=[]),truth=[])['f1'],1)
    def test_04_clean_false(self): self.assertEqual(self.score(truth=[])['reward'],-1)
    def test_05_duplicate(self):
        self.answer['findings']*=2; self.assertEqual(self.score()['fp'],len(self.e['truth']))
    def test_06_currency(self):
        for f in self.answer['findings']: f['currency']='USD'
        self.assertEqual(self.score()['tp'],0)
    def test_07_amount(self):
        for f in self.answer['findings']: f['claimed_amount_minor']+=1
        self.assertEqual(self.score()['tp'],0)
    def test_08_partial_evidence(self):
        for f in self.answer['findings']: f['evidence_ids']=f['evidence_ids'][:1]
        self.assertEqual(self.score()['tp'],0)
    def test_09_guessed_evidence(self):
        for f in self.answer['findings']: f['evidence_ids']=['fake']
        self.assertEqual(self.score()['tp'],0)
    def test_10_guessed_ids(self):
        for f in self.answer['findings']: f['affected_ids']=['fake']
        self.assertEqual(self.score()['tp'],0)
    def test_11_all_rows(self):
        for f in self.answer['findings']: f['affected_ids']=[r['row_id'] for r in self.e['public']['ledger']]
        self.assertEqual(self.score()['reward'],-1)
    def test_12_all_types(self):
        self.answer['findings']=[dict(f,type=t) for f in self.answer['findings'] for t in ['duplicate_invoice','payment_allocation','fx_conversion','accounting_period']]
        self.assertLess(self.score()['reward'],0)
    def test_13_wrong_episode(self):
        self.answer['episode_id']='unknown'; self.assertEqual(self.score()['error'],'invalid_submission')
    def test_14_bad_structure(self):
        for a in (None,[],{},'x',{'episode_id':self.eid,'findings':[None]}): self.assertEqual(self.score(a if a is not None else [])['reward'],-1)
    def test_15_findings_limit(self):
        self.answer['findings']=[self.answer['findings'][0]]*31; self.assertIn('error',self.score())
    def test_16_evidence_limit(self):
        self.answer['findings'][0]['evidence_ids']=list(map(str,range(11))); self.assertIn('error',self.score())
    def test_17_explanation_limit(self):
        self.answer['findings'][0]['explanation']='x'*1001; self.assertIn('error',self.score())
    def test_18_repeat_submit(self):
        s=Session(); s.reset(3498,{},'train'); s.step(dict(tool='submit',findings=self.answer)); self.assertEqual(s.step(dict(tool='submit',findings=self.answer))[1],0)
    def test_19_step_cost(self): self.assertAlmostEqual(self.score(steps=10)['reward']-self.score(steps=11)['reward'],.002)
    def test_20_text_irrelevant(self):
        for f in self.answer['findings']: f['explanation']=''
        self.assertEqual(self.score()['reward'],1)
