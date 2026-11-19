import json,time,tracemalloc
from auditforge.generator import generate,TYPES
from auditforge.reconcile import validate
from auditforge.env import AuditEnv
from auditforge.policies import run_policy
from auditforge.export import write_json

def main():
 rows=[]
 for label,config in [('small',{'invoices':40}),('typical',{'invoices':50}),('large',{'invoices':200,'counts':dict.fromkeys(TYPES,3)}),('clean',{'clean':True}),('interaction_fx',{'interaction':1}),('interaction_refund',{'interaction':2})]:
  tracemalloc.start();tick=time.perf_counter();e=generate(782396,config);gen=time.perf_counter()-tick;validate(e)
  tick=time.perf_counter()
  with AuditEnv('evaluation') as env:
   initial,_=env.reset(782396,config);reset=time.perf_counter()-tick;tick=time.perf_counter();logs=[];run_policy(env,initial,'reconciliation',logs);duration=time.perf_counter()-tick;r=env.evaluator_report()
  peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop()
  assert r['f1']==1 and duration<60 and len(logs)<=100
  rows.append(dict(case=label,records=len(e['public']['ledger']),documents=e['public']['manifest']['documents'],generation_seconds=gen,reset_seconds=reset,policy_seconds=duration,steps=len(logs),peak_tracemalloc_bytes=peak,**r))
 write_json('reports/resources.json',{'enforced_container_limits':False,'host':'Windows Python 3.11','cases':rows});print(json.dumps(rows))
if __name__=='__main__':main()
