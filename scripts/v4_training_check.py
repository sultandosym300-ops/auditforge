"""Frozen five-seed evaluation of source acquisition in realistic_v1 worlds."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import time
from auditforge.env import Session
from auditforge.efficient_training import EfficientTrainer, INITIAL_WEIGHTS, investigate
from auditforge.policies import run_policy
from auditforge.realistic import BUSINESS_TYPES
from auditforge.training import episode_seed
from auditforge.proof import _session_for

TRAIN_SEEDS=(314159,271828,161803,141421,173205)
HOLDOUT_ROOT=837501942683
SCENARIOS=('period','duplicate','allocation','fx','mixed','clean')

def summary(rows):
    steps=sorted(r['steps'] for r in rows)
    return dict(episodes=len(rows),
        **{k:statistics.mean(r[k] for r in rows) for k in ('precision','recall','f1','reward','steps','inspection_steps','cpu_seconds','wall_seconds')},
        median_steps=statistics.median(steps),p90_steps=steps[int(.9*(len(steps)-1))],
        false_positives=sum(r['fp'] for r in rows),false_negatives=sum(r['fn'] for r in rows),
        minimum_f1=min(r['f1'] for r in rows))

def run(episodes=300,count=2):
    rows=[];training=[];cache={}
    source_hashes={name:hashlib.sha256((Path(__file__).resolve().parents[1]/'auditforge'/name).read_bytes()).hexdigest() for name in ('realistic.py','realistic_audit.py','efficient_training.py','generator.py','proof.py')}
    for train_seed in TRAIN_SEEDS:
        model=EfficientTrainer(train_seed,'mixed',world_profile='realistic_v1',business_type='logistics')
        started=time.perf_counter();cpu=time.process_time()
        for _ in range(episodes):model.train_episode()
        frozen=copy.deepcopy(model.checkpoint())
        training.append(dict(seed=train_seed,episodes=episodes,wall_seconds=time.perf_counter()-started,
                             cpu_seconds=time.process_time()-cpu,weight_change=model.history[-1]['weight_change']))
        for scenario in SCENARIOS:
            config_model=EfficientTrainer(0,scenario)
            for business in BUSINESS_TYPES:
                for size in (40,84,200):
                    for index in range(count):
                        config=dict(config_model.config(index+1),profile='realistic_v1',business_type=business,invoices=size)
                        seed=episode_seed(HOLDOUT_ROOT,scenario,index)
                        for policy in ('untrained','trained','random','reconciliation'):
                            key=json.dumps([seed,config],sort_keys=True)
                            if key not in cache:
                                actual=Session();actual.reset(seed,config,'evaluation');cache[key]=actual.episode
                            session,initial=_session_for(cache[key])
                            started=time.perf_counter();cpu=time.process_time()
                            if policy=='trained':model.run(session,initial)
                            elif policy=='untrained':investigate(session.step,initial,INITIAL_WEIGHTS)
                            else:run_policy(session,initial,policy)
                            assert session.done and session.steps<=100
                            rows.append(dict(training_seed=train_seed,scenario=scenario,business_type=business,size=size,index=index,
                                seed=seed,policy=policy,steps=session.steps,inspection_steps=session.steps-int(session.done_flags[0]),
                                cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-started,
                                **{k:session.report[k] for k in ('precision','recall','f1','reward','fp','fn')}))
        assert model.checkpoint()==frozen
    result=dict(format='auditforge-realistic-training-holdout',version=1,source_sha256=source_hashes,unique_holdout_companies=len(cache),training_seeds=list(TRAIN_SEEDS),
        holdout_root=HOLDOUT_ROOT,training=training,training_episodes=episodes,companies_per_cell=count,
        scenarios=list(SCENARIOS),business_types=list(BUSINESS_TYPES),sizes=[40,84,200],
        summary={p:summary([r for r in rows if r['policy']==p]) for p in ('untrained','trained','random','reconciliation')},
        per_type={s:summary([r for r in rows if r['policy']=='trained' and r['scenario']==s]) for s in SCENARIOS},
        per_seed={str(seed):summary([r for r in rows if r['policy']=='trained' and r['training_seed']==seed]) for seed in TRAIN_SEEDS},
        per_business={s:summary([r for r in rows if r['policy']=='trained' and r['business_type']==s]) for s in BUSINESS_TYPES},
        rows=rows,checkpoint_unchanged=True,
        limitations=['Same frozen holdout company panel is reused across five checkpoints; policy runs are not independent companies. Each company is generated with the real reset API once, then evaluator-only snapshots are copied into identical Session fixtures for all policies.',
            'Training and evaluation use realistic_v1, but only the procurement projection contains official four-type audit tasks.',
            'Other financial modules are genuine accounting context; this experiment does not establish learned audit skills for payroll, inventory or tax.',
            'No hyperparameter selection on this holdout. Default v3 learning rate and 300-episode budget were fixed before this run.',
            'P/R averages include the official zero convention for empty predictions; mean episode F1 includes correct clean answers.',
            'CPU timing resolution and machine load limit portability; browser latency is a separate measurement.'])
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--episodes',type=int,default=300);parser.add_argument('--count',type=int,default=2);parser.add_argument('--output',type=Path,default=Path('reports/v4-training-check.json'));args=parser.parse_args()
    if not 1<=args.count<=20 or not 1<=args.episodes<=10000:parser.error('count or episodes out of range')
    result=run(args.episodes,args.count);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(summary=result['summary'],per_type=result['per_type']),indent=2))
