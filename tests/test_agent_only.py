import copy,json,unittest
from auditforge.agent_only import run_agent_only
from auditforge.env import Session
from auditforge.generator import generate,TYPES
from auditforge.policies import run_policy
from auditforge.realistic_audit import audit_realistic

class AgentOnlyTests(unittest.TestCase):
 def test_all_four_errors_and_context_are_discovered_with_official_actions_only(self):
  allowed={'list_records','get_record','get_document','calculator','submit'}
  for business in ('logistics','trade','manufacturing','it','services'):
   session=Session();initial,_=session.reset(710943,dict(profile='realistic_v1',business_type=business,invoices=200,counts={kind:3 for kind in TYPES}),'evaluation')
   initial_copy=copy.deepcopy(initial);log=[]
   def step(action):
    self.assertIn(action['tool'],allowed)
    return session.step(action)
   result=run_agent_only(step,initial,log=log)
   self.assertEqual(initial,initial_copy)
   self.assertEqual(session.report['f1'],1)
   self.assertEqual({f['type'] for f in result['findings']},set(TYPES))
   self.assertLessEqual(session.steps,100)
   self.assertTrue(result['discovered_context_types'])
   self.assertGreater(result['requested_source_documents'],0)
   seen={r['observation'].get('result',{}).get('doc_id') for r in log if r['action']['tool']=='get_document'}
   for finding in result['findings']:
    self.assertTrue(set(finding['evidence_ids']) & seen)
   for row in log:
    for field in ('"truth"','"provenance"','"expected_amount_minor"'):
     self.assertNotIn(field,json.dumps(row['observation']))
   self.assertTrue(audit_realistic(session.episode)['valid'])

 def test_missing_context_sources_are_detected_without_fabricating_proofs(self):
  session=Session();initial,_=session.reset(710943,dict(profile='realistic_v1',business_type='manufacturing',invoices=40),'evaluation')
  hidden={d['doc_id'] for d in session.public['business']['source_documents']}
  def withholding_step(action):
   result=session.step(action)
   if action['tool']=='get_document' and action['doc_id'] in hidden:
    observation=dict(steps_remaining=result[0]['steps_remaining'],error='invalid_request')
    return observation,result[1],result[2],result[3],result[4]
   return result
  result=run_agent_only(withholding_step,initial)
  self.assertEqual(result['findings'],[])
  self.assertEqual(len(result['declined']),4)
  self.assertEqual(session.report['f1'],0)
  control=Session();first,_=control.reset(710943,dict(profile='realistic_v1',business_type='manufacturing',invoices=40),'evaluation')
  run_policy(control,first,'reconciliation')
  self.assertEqual(control.report['f1'],1)

 def test_inconsistent_bank_amount_and_acceptance_are_declined(self):
  session=Session();initial,_=session.reset(710943,dict(profile='realistic_v1',business_type='trade',invoices=40),'evaluation')
  def corrupting_step(action):
   result=session.step(action)
   if action['tool']=='get_document' and isinstance(result[0].get('result'),dict):
    doc=result[0]['result']
    if doc.get('type') in ('bank_statement','service_acceptance'):doc['amount_minor']+=1
   return result
  result=run_agent_only(corrupting_step,initial)
  self.assertEqual(result['findings'],[])
  self.assertEqual(len(result['declined']),4)
  self.assertEqual(session.report['fp'],0)

 def test_public_discovery_graph_rejects_broken_link(self):
  episode=generate(710943,dict(profile='realistic_v1',business_type='trade',invoices=40))
  self.assertTrue(audit_realistic(episode)['valid'])
  episode['public']['invoices'][0]['related_document_ids'].append('unavailable-document')
  self.assertFalse(audit_realistic(episode)['valid'])

if __name__=='__main__':unittest.main()
