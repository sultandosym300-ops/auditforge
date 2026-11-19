import json,secrets,time
from pathlib import Path
from auditforge.generator import generate,TYPES
from auditforge.reconcile import validate
from auditforge.verify import transform,check_transitions
seeds=[secrets.randbelow(2**32) for _ in range(64)]
rows=[];start=time.perf_counter()
for i,seed in enumerate(seeds):
 config=dict(invoices=[40,41,50,84,100,200][i%6],clean=i%8==0,interaction=i%3,counts={t:(i+j)%4 for j,t in enumerate(TYPES)},timezone=['+05:00','-00:30','+09:30','-04:00'][i%4])
 e=generate(seed,config);validate(e);assert e==generate(seed,config)
 renamed=transform(e,seed+1);validate(renamed);check_transitions(e,renamed)
 rows.append(dict(seed=seed,config=config,episode_id=e['public']['manifest']['episode_id'],issues=len(e['truth']),valid=True,replay_and_renaming=True))
result=dict(version='1.1.0',scope='Additional local fresh-seed sweep, not organizer grading',passed=len(rows),elapsed_seconds=time.perf_counter()-start,cases=rows)
Path('reports/strict-sweep.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
