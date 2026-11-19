"""Offline verification, actual trajectories and diagnostic benchmark. Not official judging."""
import copy
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
import tracemalloc
import unittest
from pathlib import Path
from .generator import generate, TYPES, GENERATOR_VERSION
from .reconcile import validate, reconcile
from .matcher import oracle, evaluate
from .env import AuditEnv, Session
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


def check_transitions(episode, transformed):
    """Exercise tools and terminal scoring, rather than comparing two truth oracles."""
    def session_for(value):
        session = Session()
        initial, _ = session.reset(0, {}, 'evaluation')
        session.episode = copy.deepcopy(value)
        session.public = session.episode['public']
        initial.update(manifest=session.public['manifest'], policy=session.public['policy'])
        return session, initial
    session, initial = session_for(episode)
    log = []
    run_policy(session, initial, 'reconciliation', log)
    assert session.report['f1'] == 1
    repeated, _ = session_for(episode)
    for row in log:
        observation, reward, terminated, truncated, _ = repeated.step(row['action'])
        assert (observation, reward, terminated, truncated) == (row['observation'], row['reward'], row['terminated'], row['truncated'])
    assert repeated.report == session.report
    renamed, initial = session_for(transformed)
    renamed_log = []
    run_policy(renamed, initial, 'reconciliation', renamed_log)
    assert renamed.report == session.report
    assert len(renamed_log) == len(log)
    oracle_reports = []
    for value in (episode, transformed):
        oracle_session, _ = session_for(value)
        _, reward, terminated, truncated, info = oracle_session.step(
            dict(tool='submit', findings=oracle(value))
        )
        assert terminated and not truncated and reward == 0 and info == {}
        assert oracle_session.report['f1'] == 1
        oracle_reports.append(oracle_session.report)
    assert oracle_reports[0] == oracle_reports[1]
    return True


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
    holdout_seeds=[int.from_bytes(hashlib.sha256(('auditforge-holdout-v2-'+str(i)).encode()).digest()[:8],'big') for i in range(20)]
    data=[]; pairs=[]; results=[]; trajectories=[]
    tracemalloc.start()
    for i,(seed,config) in enumerate(zip(holdout_seeds,configs)):
        tick=time.perf_counter()
        e=generate(seed,config); validate(e)
        data.append(dict(episode_id=e['public']['manifest']['episode_id'],clean=config['clean'],interaction=config['interaction'],issues=len(e['truth']),records=len(e['public']['ledger']),valid=True,generation_validation_seconds=time.perf_counter()-tick))
        assert e==generate(seed,config)
        transformed=transform(e,seed+1); validate(transformed)
        check_transitions(e, transformed)
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
    memory=tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
    for split,offset in [('train',0),('dev',1000)]:
        specifications=[]
        for i in range(10):
            configuration=dict(clean=i<2,interaction=i%3)
            episode=generate(offset+i,configuration)
            validate(episode)
            export_episode(episode,ROOT/'datasets'/split)
            if split == 'train':
                for name in ('random', 'reconciliation', 'mark_all'):
                    session = Session()
                    initial, _ = session.reset(offset+i, configuration, 'train')
                    log = []
                    run_policy(session, initial, name, log)
                    assert session.report is not None
                    if name == 'reconciliation':
                        assert session.report['f1'] == 1
                    trajectories.extend(dict(policy=name, **row) for row in log)
            specifications.append(dict(seed=offset+i,config=configuration,episode_id=episode['public']['manifest']['episode_id']))
        write_json(ROOT/'configs'/(split+'.json'),dict(version='1.1',generator_version=GENERATOR_VERSION,episodes=specifications))
    (ROOT/'trajectories').mkdir(exist_ok=True)
    (ROOT/'trajectories'/'trajectories.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in trajectories),encoding='utf-8')
    report=dict(version=GENERATOR_VERSION,tests_passed=test_count,official_result=None,scope='Local approximation of published checks; hidden organizer tests unavailable.',python=platform.python_version(),platform=platform.platform(),contract_checks=20,reward_checks=20,data=data,metamorphic_pairs=pairs,benchmark=results,peak_python_tracemalloc_bytes=memory,wall_seconds=time.perf_counter()-started,limitations=['CPU/RAM isolation requires Docker; tracemalloc is not process RSS.','No model weights trained; no learning improvement claimed.','Oracle is evaluator-only; its inspection strategy is not optimized.'])
    write_json(ROOT/'reports'/'verification.json',report)
    write_json(ROOT/'web'/'public'/'verification-summary.json',dict(local=True,official_result=None,contract_passed=20,reward_passed=20,valid_episodes=len(data),metamorphic_pairs=len(pairs),wall_seconds=report['wall_seconds'],benchmark=results))
    print(json.dumps(dict(status='PASS',tests=test_count,data_episodes=20,pairs=20,policy_runs=len(results),seconds=report['wall_seconds'],peak_python_bytes=memory,official_result=None)))

if __name__=='__main__': main()
