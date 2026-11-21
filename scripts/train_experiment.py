"""Reproducible CPU training experiment, with frozen held-out comparisons."""
import argparse
import json
from pathlib import Path
import time
import tracemalloc

from auditforge.env import Session
from auditforge.training import Trainer, episode_seed
from auditforge.policies import run_policy


def run(seed=314159,episodes=300,count=40):
    trainer=Trainer(seed,'period')
    tracemalloc.start()
    started=time.perf_counter()
    for _ in range(episodes):
        trainer.train_episode()
    elapsed=time.perf_counter()-started
    peak=tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    comparison=trainer.evaluate(count,70193)
    confirmation=trainer.evaluate(count,904621)
    ordinary=[]
    for i in range(20):
        config=dict(clean=i<5,interaction=1+i%2 if 5<=i<10 else 0)
        seed=episode_seed(904621,'ordinary-evaluation',i)
        for name in ('trained','reconciliation'):
            session=Session()
            initial,_=session.reset(seed,config,'evaluation')
            if name=='trained':
                trainer.run(session,initial)
            else:
                run_policy(session,initial)
            ordinary.append(dict(policy=name,index=i,steps=session.steps,
                                 **{key:session.report[key] for key in ('precision','recall','f1','reward')}))
    return dict(seed=trainer.seed,training_episodes=episodes,training_seconds=elapsed,
                peak_python_allocated_bytes=peak,checkpoint=trainer.checkpoint(),
                holdout=comparison,confirmation=confirmation,ordinary_mixed=ordinary,
                limitation='Learns query/skip for invoice recognition documents. It cannot detect payment allocation or FX errors. The learned greedy policy may query every invoice, trading recall for higher step cost than fixed reconciliation.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=314159)
    parser.add_argument('--episodes',type=int,default=300)
    parser.add_argument('--output',type=Path,default=Path('reports/real-training.json'))
    args=parser.parse_args()
    if not 1<=args.episodes<=5000:
        parser.error('episodes must be 1..5000')
    result=run(args.seed,args.episodes)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({key:result[key] for key in ('training_episodes','training_seconds','peak_python_allocated_bytes')}))
    print(json.dumps(result['holdout']['results']))
