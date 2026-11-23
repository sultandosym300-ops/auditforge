import unittest
from auditforge.env import Session
from auditforge.document_policy import KINDS, Network, feature_vector, investigate
from auditforge.document_training import DocumentTrainer

class DocumentPolicyTests(unittest.TestCase):
 def test_all_source_kinds_have_nonzero_known_features(self):
  public={'manifest':{'base_currency':'KZT'}}
  aliases={'exchange_quote':'fx_quote','allocation_document':'allocation','fulfillment_confirmation':'fulfillment'}
  for original,canonical in aliases.items():
   x=feature_vector({'document_id':'x','kind':original,'case_id':'c'}, {},public,20,20)
   self.assertEqual(x[1+KINDS.index(canonical)],1.)
 def test_full_document_reconciliation_is_sufficient_both_families(self):
  for family in ('procurement','service_milestone'):
   for seed in range(4):
    s=Session();initial,_=s.reset(930000+seed,{'profile':'investigation_v2','family':family},'evaluation')
    result=investigate(s.step,initial,policy='reconciliation',budget=100)
    self.assertTrue(result['terminal'][2]);self.assertFalse(result['terminal'][3])
    self.assertEqual(s.report['f1'],1.,(family,seed,s.report))
    self.assertLessEqual(s.steps,100)
 def test_normalized_pending_batch_resumes_exactly(self):
  for architecture in ('linear','mlp'):
   m=DocumentTrainer(seed=91723,architecture=architecture,normalize_advantage=True,entropy=.01)
   for _ in range(3):m.train_episode()
   other=DocumentTrainer.from_checkpoint(m.checkpoint())
   m.train_episode();other.train_episode()
   self.assertEqual(m.model.parameters,other.model.parameters)
   self.assertEqual(m.optimizer_steps,1)
 def test_partial_batch_flush_records_consistent_norm(self):
  m=DocumentTrainer(seed=91,normalize_advantage=True,entropy=.01)
  for _ in range(2):m.train_episode()
  m.flush()
  self.assertAlmostEqual(m.history[-1]['weight_norm'],sum(x*x for x in m.model.parameters)**.5)
  self.assertEqual(m.history[-1]['optimizer_steps'],1)
if __name__=='__main__':unittest.main()
