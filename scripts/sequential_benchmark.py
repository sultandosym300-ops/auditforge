"""Predeclared validation selection, paired company-cluster test and raw traces.

python -m scripts.sequential_benchmark --output work/sequential-study
Never selects a checkpoint, generator configuration or seed using test results.
"""
import argparse
import copy
import hashlib
import json
import random
import statistics
import time
from pathlib import Path

from auditforge.env import Session
from auditforge.generator import generate
from auditforge.sequential_policy import investigate, SequentialTrainer
from auditforge.training import episode_seed
from scripts.final_policy_study import immutable_fixture

ROOT=Path(__file__).resolve().parents[1]
POLICIES=('learned','untrained','random_weights','fixed_source','random_valid',
          'reconciliation','budget_aware','greedy','heuristic_search','zero_features',
          'no_financial_rules','no_source_selection')


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')


def summarize(rows):
    return dict(runs=len(rows),independent_companies=len({r['company'] for r in rows}),
                **{key:statistics.mean(r[key] for r in rows) for key in ('reward','f1','steps','precision','recall')},
                fp=sum(r['fp'] for r in rows),fn=sum(r['fn'] for r in rows))


def paired(rows,budget,left,right,replicates):
    groups={}
    for row in rows:
        if row['budget']==budget and row['policy'] in (left,right):
            groups.setdefault(row['company'],{}).setdefault(row['policy'],[]).append(row['reward'])
    differences=[statistics.mean(group[left])-statistics.mean(group[right]) for group in groups.values()]
    rng=random.Random(episode_seed(8127601,'company-bootstrap',budget))
    samples=sorted(statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(replicates))
    return dict(budget=budget,left=left,right=right,companies=len(differences),
                difference=statistics.mean(differences),bootstrap_95=[samples[int(.025*replicates)],samples[int(.975*replicates)-1]],
                unit='independent synthetic company; checkpoint variation averaged within company')


def run_panel(spec,models,root,count,family,output):
    rows=[];fixtures=[]
    for index in range(count):
        seed=episode_seed(root,'frozen-company',index)
        config=SequentialTrainer.config(index,family)
        episode=generate(seed,config)
        digest=hashlib.sha256(json.dumps(episode,sort_keys=True).encode()).hexdigest()
        fixtures.append(dict(company=index,seed=seed,config=config,sha256=digest,truth_count=len(episode['truth'])))
        for checkpoint,model in enumerate(models):
            for budget in spec['budgets']:
                for policy in POLICIES:
                    session,initial=immutable_fixture(episode)
                    start=time.perf_counter()
                    result=investigate(session.step,initial,policy=policy,budget=budget,weights=model.weights)
                    if session.steps>budget or not session.done or 'error' in session.report:
                        raise AssertionError('Invalid benchmark run')
                    rows.append(dict(company=index,checkpoint=checkpoint,training_seed=model.seed,budget=budget,policy=policy,
                                     clean=not episode['truth'],steps=session.steps,seconds=time.perf_counter()-start,**session.report))
        assert hashlib.sha256(json.dumps(episode,sort_keys=True).encode()).hexdigest()==digest
        print(f'PANEL {family} {index+1}/{count}',flush=True)
    summary={str(b):{p:summarize([r for r in rows if r['budget']==b and r['policy']==p]) for p in POLICIES} for b in spec['budgets']}
    comparisons=[]
    for budget in spec['budgets']:
        # Each named comparison is retained, including negative differences.
        for baseline in ('budget_aware','greedy','heuristic_search','fixed_source','untrained','reconciliation'):
            comparisons.append(paired(rows,budget,'learned',baseline,spec['bootstrap_replicates']))
    save(output,dict(family=family,fixtures=fixtures,rows=rows,summary=summary,paired=comparisons,
                     note='Repeated checkpoints are not independent companies. CIs are conditional on this synthetic company panel.'))
    return dict(summary=summary,paired=comparisons,independent_companies=count,runs=len(rows))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'work/sequential-study')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    protocol=(ROOT/'configs/sequential-study.json').read_bytes();spec=json.loads(protocol)
    save(args.output/'protocol.json',dict(specification=spec,sha256=hashlib.sha256(protocol).hexdigest()))
    candidates=[];all_models=[]
    for candidate_id,settings in enumerate(spec['candidates']):
        models=[];validation=[]
        for seed in spec['training_seeds']:
            model=SequentialTrainer(seed,spec['training_budget'],**settings)
            for i in range(spec['training_episodes']):
                model.train_episode()
                if (i+1)%50==0:print(f'TRAIN candidate={candidate_id} seed={seed} episodes={i+1}',flush=True)
            result=model.evaluate(spec['validation_companies'],spec['validation_root'],policies=('learned',))
            validation.append(result['results'][0]['reward']);models.append(model)
            save(args.output/f'candidate-{candidate_id}-seed-{seed}.json',dict(checkpoint=model.checkpoint(),validation=result))
        candidates.append(dict(candidate=candidate_id,settings=settings,validation_reward=statistics.mean(validation),per_seed=validation))
        all_models.append(models)
    chosen=max(range(len(candidates)),key=lambda i:candidates[i]['validation_reward'])
    # This immutable-in-run selection is written BEFORE opening test fixtures.
    save(args.output/'selection.json',dict(chosen=chosen,candidates=candidates,criterion=spec['selection']))
    models=all_models[chosen]
    test=run_panel(spec,models,spec['test_root'],spec['test_companies'],'procurement',args.output/'test-raw.json')
    transfer=run_panel(spec,models,spec['transfer_root'],spec['transfer_companies'],'closing_transfer',args.output/'transfer-raw.json')
    save(args.output/'summary.json',dict(protocol_sha256=hashlib.sha256(protocol).hexdigest(),selection=candidates[chosen],test=test,transfer=transfer))
    for i,model in enumerate(models):save(args.output/f'selected-{i}.json',model.checkpoint())


if __name__=='__main__':main()
