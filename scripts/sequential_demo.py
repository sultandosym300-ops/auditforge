"""Fixed, predeclared company. Show wins and losses without seed selection."""
import argparse
import json
from pathlib import Path

from auditforge.env import Session
from auditforge.efficient_training import load_trainer
from auditforge.sequential_policy import investigate

ROOT=Path(__file__).resolve().parents[1]


def demo(checkpoint, budget=None):
    model=load_trainer(checkpoint)
    budget=model.budget if budget is None else budget
    rows=[]
    for policy in ('random_valid','reconciliation','budget_aware','learned'):
        session=Session()
        initial,_=session.reset(202611230017,dict(profile='investigation_v1'),'evaluation')
        result=investigate(session.step,initial,policy=policy,budget=budget,weights=model.weights)
        # Independently replay exactly the same public actions and compare every response.
        replay=Session();replay.reset(202611230017,dict(profile='investigation_v1'),'evaluation')
        for entry in result['trajectory']:
            observation,reward,terminated,truncated,info=replay.step(entry['action'])
            assert (observation,reward,terminated,truncated)==(entry['observation'],entry['reward'],entry['terminated'],entry['truncated'])
        assert replay.report==session.report
        rows.append(dict(policy=policy,steps=session.steps,report=session.report,trajectory=result['trajectory']))
    return dict(seed=202611230017,config=dict(profile='investigation_v1'),budget=budget,
                model_seed=model.seed,algorithm=model.algorithm,runs=rows,replay_verified=True,
                limitation='Predeclared company, not a selected RL victory. Aggregate independent-company results are in the benchmark report.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',type=Path,default=ROOT/'reports/final-sequential-selected-0.json')
    parser.add_argument('--budget',type=int);parser.add_argument('--output',type=Path,default=ROOT/'work/sequential-demo.json')
    args=parser.parse_args();report=demo(json.loads(args.checkpoint.read_text(encoding='utf8')),args.budget)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps([dict(policy=row['policy'],steps=row['steps'],**row['report']) for row in report['runs']]))


if __name__=='__main__':main()
