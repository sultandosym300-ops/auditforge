"""Run real matcher fixtures, replay invariants and completed-demo arithmetic offline."""
import argparse
import json
from pathlib import Path
import time

from auditforge.env import Session
from auditforge.proof import proof_suite, explain_completed
from auditforge.policies import run_policy


def run(seed=2026112204,count=20):
    started=time.perf_counter()
    rows=[]
    first_suite=None
    for index in range(count):
        current_seed=seed+index*7919
        suite=proof_suite(current_seed)
        if first_suite is None:first_suite=suite
        cases=suite['matcher_cases']
        reproduction=suite['reproducibility']
        for interaction in (0,1,2):
            session=Session()
            initial,_=session.reset(current_seed,dict(invoices=(40,50,84,120,200)[index%5],interaction=interaction),'train')
            run_policy(session,initial,'reconciliation')
            explanation=explain_completed(session,demo=True)
            calculations=[dict(type=i['type'],affected_ids=i['affected_ids'],currency=i['currency'],
                               calculated=i['calculation']['calculated_discrepancy_minor'],
                               declared=i['expected_amount_minor'],passed=i['calculation']['matches_declared_discrepancy']) for i in explanation['issues']]
            rows.append(dict(seed=current_seed,interaction=interaction,invoices=(40,50,84,120,200)[index%5],
                             report=session.report,calculations=calculations,
                             passed=all(c['passed'] for c in calculations) and session.report['f1']==1))
        passed=all(c['passed'] for c in cases) and suite['financial']['valid'] and reproduction['first_hash']==reproduction['second_hash'] and reproduction['renaming']['report_equal']
        if not passed:raise AssertionError(f'Proof fixture failed for seed {current_seed}')
    return dict(format='auditforge-v4-proof-check',version=1,seed=seed,company_seeds=count,
                matcher_cases=6*count,replay_pairs=count,renaming_pairs=count,
                completed_company_runs=len(rows),causal_calculations=sum(len(r['calculations']) for r in rows),
                passed=all(r['passed'] for r in rows),rows=rows,example_suite=first_suite,
                seconds=time.perf_counter()-started,
                scope='Native Python checks on fresh local synthetic fixtures. Docker isolation is a separate run; official jury score is unknown.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=2026112204)
    parser.add_argument('--count',type=int,default=20)
    parser.add_argument('--output',type=Path,default=Path('reports/v4-proof-check.json'))
    args=parser.parse_args()
    if not 1<=args.count<=200:parser.error('count must be 1..200')
    result=run(args.seed,args.count)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('example_suite','rows')}))
    return int(not result['passed'])


if __name__=='__main__':raise SystemExit(main())
