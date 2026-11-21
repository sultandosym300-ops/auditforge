"""Frozen extra public-budget probe; official Session action/reward contract unchanged."""
import json
from pathlib import Path
import statistics
import time
from auditforge.env import Session
from auditforge.efficient_training import EfficientTrainer
from auditforge.training import episode_seed
from scripts.v3_benchmark import TRAIN_SEEDS


def run():
    rows, training = [], []
    for seed in TRAIN_SEEDS:
        for scenario in ('period','mixed'):
            model = EfficientTrainer(seed, scenario)
            started = time.process_time()
            for _ in range(300):
                model.train_episode()
            training.append(dict(seed=seed,scenario=scenario,cpu_seconds=time.process_time()-started))
            for size in (40,84,200):
                for index in range(4):
                    for budget in (5,6,10,20,40):
                        config = dict(model.config(index),invoices=size)
                        session = Session()
                        initial,_ = session.reset(episode_seed(631974250819,'budget-holdout',index),config,'evaluation')
                        initial['steps_remaining'] = budget
                        started = time.process_time()
                        class BudgetBoundary:
                            def step(self, action):
                                assert session.steps < budget
                                observation,reward,terminated,truncated,info = session.step(action)
                                observation = dict(observation,steps_remaining=budget-session.steps)
                                return observation,reward,terminated,truncated,info
                        model.run(BudgetBoundary(),initial)
                        elapsed = time.process_time()-started
                        assert session.done and session.steps<=budget
                        rows.append(dict(seed=seed,scenario=scenario,size=size,index=index,budget=budget,steps=session.steps,
                                         inspection_steps=session.steps-1,cpu_seconds=elapsed,**session.report))
    summary=[]
    for scenario in ('period','mixed'):
        for size in (40,84,200):
            for budget in (5,6,10,20,40):
                selected=[r for r in rows if (r['scenario'],r['size'],r['budget'])==(scenario,size,budget)]
                summary.append(dict(scenario=scenario,size=size,budget=budget,
                    **{key:statistics.mean(r[key] for r in selected) for key in ('precision','recall','f1','reward','steps','inspection_steps','cpu_seconds')},
                    false_positives=sum(r['fp'] for r in selected),minimum_f1=min(r['f1'] for r in selected)))
    return dict(training_seeds=list(TRAIN_SEEDS),holdout_root=631974250819,training=training,summary=summary,rows=rows,
        scope='Public strategy budgets only. Official environment remains 100 steps; clean cases included. Shared holdout companies across five checkpoints, no selection on these results.')

if __name__=='__main__':
    result=run()
    Path('reports/v3-budget-probe.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result['summary'],indent=2))
