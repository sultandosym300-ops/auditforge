"""Offline verification, actual trajectories and diagnostic benchmark. Not official judging."""
import copy
import json
import platform
import random
import subprocess
import sys
import time
import tracemalloc
import unittest
from pathlib import Path
from .generator import generate, TYPES
from .reconcile import validate, reconcile
from .matcher import oracle, evaluate
from .env import AuditEnv
from .policies import run_policy
from .export import export_episode, write_json

ROOT = Path(__file__).resolve().parents[1]


def transform(episode, seed):
    rng = random.Random(seed)
    ids = set()
    def collect(value, key=''):
        if isinstance(value, dict):
            for k,v in value.items(): collect(v,k)
        elif isinstance(value,list):
            for v in value: collect(v,key)
        elif isinstance(value,str) and (key.endswith('_id') or key.endswith('_ids') or key=='evidence_sets'):
            ids.add(value)
    collect(episode)
    mapping={v:'mapped-'+format(rng.getrandbits(96),'024x') for v in sorted(ids)}
    def replace(value):
        if isinstance(value,dict): return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list): return [replace(v) for v in value]
        if isinstance(value,str): return mapping.get(value,value)
        return value
    transformed=replace(episode)
    for branch in ('public','pristine'):
        transformed[branch]['manifest']['company']='Renamed Fictional Company'
        for table in ('ledger','invoices','payments','fx'): rng.shuffle(transformed[branch][table])
    return transformed


def main():
    started=time.perf_counter()
    test_count=unittest.defaultTestLoader.discover(str(ROOT/'tests')).countTestCases()
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT)
    if tests.returncode: raise SystemExit(tests.returncode)
    configs=[]
    for i in range(20):
        config=dict(clean=i<5,interaction=(1+i%2) if 5<=i<10 else 0)
        if i>=10: config['counts']={t: (i+j)%3+1 for j,t in enumerate(TYPES)}
        configs.append(config)
    holdout_seeds=[int.from_bytes(__import__('hashlib').sha256(('auditforge-holdout-v1-'+str(i)).encode()).digest()[:4],'big') for i in range(20)]
    data=[]; pairs=[]; results=[]; trajectories=[]
    tracemalloc.start()
    for i,(seed,config) in enumerate(zip(holdout_seeds,configs)):
        tick=time.perf_counter()
        e=generate(seed,config); validate(e)
        data.append(dict(episode_id=e['public']['manifest']['episode_id'],clean=config['clean'],interaction=config['interaction'],issues=len(e['truth']),records=len(e['public']['ledger']),valid=True,generation_validation_seconds=time.perf_counter()-tick))
        assert e==generate(seed,config)
        transformed=transform(e,seed+1); validate(transformed)
        a=evaluate(e['public']['manifest']['episode_id'],e['truth'],oracle(e),10)
        b=evaluate(transformed['public']['manifest']['episode_id'],transformed['truth'],oracle(transformed),10)
        assert a==b
        pairs.append(dict(episode_id=e['public']['manifest']['episode_id'],repeat_exact=True,renamed_shuffled_equivalent=True))
        for name in ('random','reconciliation','mark_all','oracle'):
            tick=time.perf_counter()
            log=[]
            with AuditEnv(mode='evaluation') as env:
                initial,_=env.reset(seed,config)
                if name=='oracle':
                    # Evaluator-only adapter; submit only after independently checking evidence.
                    answer=oracle(e)
                    for finding in answer['findings']:
                        for evidence_id in finding['evidence_ids']:
                            table=next(table for table in ('ledger','invoices','payments','fx') if any(evidence_id==r.get('row_id',r.get('doc_id')) for r in e['public'][table]))
                            action=dict(tool='get_record',table=table,id=evidence_id)
                            result=env.step(action)
                            assert 'error' not in result[0]
                            log.append(dict(episode_id=initial['manifest']['episode_id'],step=len(log)+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
                    action=dict(tool='submit',findings=answer); result=env.step(action)
                    log.append(dict(episode_id=initial['manifest']['episode_id'],step=len(log)+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
                else:
                    run_policy(env,initial,name,log)
                report=env.evaluator_report()
                assert report is not None
                if name in ('oracle','reconciliation'): assert report['f1']==1, (seed,name,report)
                results.append(dict(episode_id=initial['manifest']['episode_id'],policy=name,steps=len(log),seconds=time.perf_counter()-tick,**report))
            if name!='oracle': trajectories.extend(dict(policy=name,**row) for row in log)
    memory=tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
    for split,offset in [('train',0),('dev',1000)]:
        write_json(ROOT/'configs'/(split+'.json'),dict(version='1.0',seeds=list(range(offset,offset+10)),config={'invoices':50}))
        for i in range(10): export_episode(generate(offset+i,dict(clean=i<2,interaction=i%3)),ROOT/'datasets'/split)
    (ROOT/'trajectories').mkdir(exist_ok=True)
    (ROOT/'trajectories'/'trajectories.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in trajectories),encoding='utf-8')
    report=dict(version='1.0.0',tests_passed=test_count,official_result=None,scope='Local approximation of published checks; hidden organizer tests unavailable.',python=platform.python_version(),platform=platform.platform(),contract_checks=20,reward_checks=20,data=data,metamorphic_pairs=pairs,benchmark=results,peak_python_tracemalloc_bytes=memory,wall_seconds=time.perf_counter()-started,limitations=['CPU/RAM isolation requires Docker; tracemalloc is not process RSS.','No model weights trained; no learning improvement claimed.','Oracle is evaluator-only; its inspection strategy is not optimized.'])
    write_json(ROOT/'reports'/'verification.json',report)
    write_json(ROOT/'web'/'public'/'verification-summary.json',dict(local=True,official_result=None,contract_passed=20,reward_passed=20,valid_episodes=len(data),metamorphic_pairs=len(pairs),wall_seconds=report['wall_seconds'],benchmark=results))
    print(json.dumps(dict(status='PASS',tests=test_count,data_episodes=20,pairs=20,policy_runs=len(results),seconds=report['wall_seconds'],peak_python_bytes=memory,official_result=None)))

if __name__=='__main__': main()
