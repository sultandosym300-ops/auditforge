import json
import unittest
from auditforge.env import Session, calculator


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.initial, _ = self.s.reset(1244, {}, 'evaluation')

    def call(self, **action): return self.s.step(action)
    def test_01_reset(self): self.assertEqual(self.initial['steps_remaining'],100)
    def test_02_json(self): json.dumps(self.initial,allow_nan=False)
    def test_03_step_tuple(self): self.assertEqual(len(self.call(tool='calculator',expression='1+2')),5)
    def test_04_pagination(self): self.assertEqual(len(self.call(tool='list_records',table='ledger',limit=50)[0]['result']['records']),50)
    def test_05_limit(self): self.assertIn('error',self.call(tool='list_records',table='ledger',limit=51)[0])
    def test_06_cursor(self):
        a=self.call(tool='list_records',table='ledger',cursor='50')[0]['result']; b=self.call(tool='list_records',table='ledger',cursor='50')[0]['result']; self.assertEqual(a,b)
    def test_07_get_record(self):
        row=self.s.public['ledger'][0]; self.assertEqual(self.call(tool='get_record',table='ledger',id=row['row_id'])[0]['result'],row)
    def test_08_document(self):
        row=self.s.public['invoices'][0]; self.assertEqual(self.call(tool='get_document',doc_id=row['doc_id'])[0]['result'],row)
    def test_09_unknown_id(self): self.assertIn('error',self.call(tool='get_document',doc_id='missing')[0])
    def test_10_unknown_tool(self): self.assertEqual(self.call(tool='shell')[0]['steps_remaining'],99)
    def test_11_decimal(self): self.assertEqual(calculator('0.1+0.2'),'0.3')
    def test_12_no_code(self):
        for s in ["__import__('os')",'x.y','[1]','2**900000','1/0']:
            with self.assertRaises(Exception): calculator(s)
    def test_13_private_table(self): self.assertIn('error',self.call(tool='list_records',table='truth')[0])
    def test_14_no_leak(self):
        content=json.dumps(self.initial)
        for key in ('truth','provenance','seed','expected_amount_minor','issue_id'): self.assertNotIn(key,content)
    def test_15_read_only(self):
        result=self.call(tool='get_record',table='ledger',id=self.s.public['ledger'][0]['row_id'])[0]['result']; result['debit_minor']=999
        self.assertNotEqual(result,self.s.public['ledger'][0])
    def test_16_reset_isolated(self):
        self.call(tool='calculator',expression='1'); self.s.reset(1,{},'evaluation'); self.assertEqual(self.s.steps,0)
    def test_17_submit_at_100(self):
        for _ in range(99): self.call(tool='calculator',expression='1')
        result=self.call(tool='submit',findings=dict(episode_id=self.initial['manifest']['episode_id'],findings=[])); self.assertTrue(result[2]); self.assertFalse(result[3])
    def test_18_truncate(self):
        for _ in range(100): result=self.call(tool='calculator',expression='1')
        self.assertTrue(result[3]); self.assertEqual(result[0]['findings'],[])
    def test_19_timeout(self):
        self.s.started-=61; result=self.call(tool='calculator',expression='1'); self.assertTrue(result[3])
    def test_20_hidden_reward(self):
        result=self.call(tool='submit',findings={}); self.assertEqual(result[1],0); self.assertEqual(result[4],{}); self.assertEqual(self.s.report['reward'],-1)
