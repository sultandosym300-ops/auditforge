"""Reproduce public-action discovery and honest source-corroboration ablations."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from auditforge.agent_only import run_agent_only
from auditforge.env import Session
from auditforge.policies import run_policy
from auditforge.realistic import BUSINESS_TYPES
from auditforge.realistic_audit import audit_realistic


def run(seed=945731806221):
 started=time.perf_counter();rows=[];controls=[]
 for index,business in enumerate(BUSINESS_TYPES):
  for size in (40,200):
   for clean in (False,True):
    company_seed=int.from_bytes(hashlib.sha256(f'agent-only-final:{seed}:{business}:{size}:{clean}'.encode()).digest()[:8],'big')
    config=dict(profile='realistic_v1',business_type=business,invoices=size,clean=clean,interaction=index%3,
                timezone=('+05:45','-03:30','+14:00')[index%3],period_month=('2040-02','2000-01','2099-12')[index%3])
    session=Session();initial,_=session.reset(company_seed,config,'evaluation');log=[]
    def official_step(action):
     assert action['tool'] in ('list_records','get_record','get_document','calculator','submit')
     return session.step(action)
    result=run_agent_only(official_step,initial,log=log)
    assert session.report['f1']==1 and session.steps<=100
    assert audit_realistic(session.episode)['valid']
    assert all(not any(k in json.dumps(r['observation']) for k in ('"truth"','"provenance"','"expected_amount_minor"')) for r in log)
    rows.append(dict(seed=company_seed,config=config,steps=session.steps,source_requests=result['requested_source_documents'],
                     context_types=result['discovered_context_types'],findings=len(result['findings']),report=session.report,
                     example_trajectory=log if not rows else None))
 for intervention in ('withhold','inconsistent'):
  session=Session();config=dict(profile='realistic_v1',business_type='manufacturing',invoices=40)
  initial,_=session.reset(seed,config,'evaluation')
  def intervention_step(action):
   result=session.step(action)
   if action['tool']=='get_document':
    doc=result[0].get('result')
    if intervention=='withhold':return dict(error='invalid_request',steps_remaining=result[0]['steps_remaining']),*result[1:]
    if isinstance(doc,dict) and doc.get('type') in ('bank_statement','service_acceptance'):doc['amount_minor']+=1
   return result
  output=run_agent_only(intervention_step,initial)
  assert session.report['f1']==0 and session.report['fp']==0 and len(output['declined'])==4
  baseline=Session();first,_=baseline.reset(seed,config,'evaluation');run_policy(baseline,first,'reconciliation')
  assert baseline.report['f1']==1
  controls.append(dict(intervention=intervention,corroborating_report=session.report,declined=output['declined'],
                       unchanged_reconciliation_report=baseline.report,
                       interpretation='Additional sources affect the corroborating policy, not the official matcher minimum. The original baseline remains fully effective.'))
 root=Path(__file__).resolve().parents[1]
 return dict(study='official-actions-only-source-discovery',root_seed=seed,companies=len(rows),independent_dirty_companies=sum(not r['config']['clean'] for r in rows),
             mean_f1=sum(r['report']['f1'] for r in rows)/len(rows),false_positives=sum(r['report']['fp'] for r in rows),
             maximum_steps=max(r['steps'] for r in rows),source_requests=sum(r['source_requests'] for r in rows),
             rows=rows,negative_controls=controls,seconds=time.perf_counter()-started,
             source_sha256={name:hashlib.sha256((root/'auditforge'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in ('agent_only.py','realistic.py','realistic_audit.py','env.py','matcher.py')},
             limitations=['Deterministic corroborating policy, not an RL or neural improvement.',
                          'The four official anomaly classes remain procurement scope. Other module roots are now discoverable through official get_document, but no new anomaly classes are claimed.',
                          'Additional sources are sufficient corroboration, not mandatory evidence for the unchanged official matcher or existing reconciliation baseline.',
                          'The 20 companies come from one procedural generator family. No external real-world competence is established.'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=945731806221);p.add_argument('--output',type=Path,default=Path('reports/final-agent-only.json'));a=p.parse_args()
 result=run(a.seed);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps({k:v for k,v in result.items() if k not in ('rows','negative_controls')},indent=2))
