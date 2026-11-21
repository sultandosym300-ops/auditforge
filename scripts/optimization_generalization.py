"""Challenge frozen optimized policies on unseen size/date/offset combinations."""
import hashlib
import json
from pathlib import Path
import time

from auditforge.efficient_training import EfficientTrainer
from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.generator import TYPES
from auditforge.verify import transform
from scripts.optimization_benchmark import PublicBoundary

ROOT=Path(__file__).resolve().parents[1]


def run():
    benchmark=json.loads((ROOT/"reports/optimization-benchmark.json").read_text(encoding="utf8"))
    rows=[]
    for model in benchmark["training"]:
        learner=EfficientTrainer.from_checkpoint(model["candidate_checkpoint"])
        before=learner.checkpoint()
        for i in range(24):
            seed=int.from_bytes(hashlib.sha256(f'optimization-generalization-v1:{model["seed"]}:{model["scenario"]}:{i}'.encode()).digest()[:16],'big')
            config=dict(invoices=(41,50,84,200)[i%4],timezone=('-00:30','+13:45','-09:30')[i%3],
                        period_month=('2000-01','2099-12','2040-02')[i%3],boundary_payments=bool(i%2))
            if model["scenario"]=="period":
                config["recognition_world"]=i%4
            else:
                config.update(clean=i%6==0,interaction=i%3,counts={kind:(i+j)%3+1 for j,kind in enumerate(TYPES)})
            session=Session()
            initial,_=session.reset(seed,config,'evaluation')
            if i%2:
                session.episode=transform(session.episode,seed+1)
                session.public=session.episode['public']
                initial.update(manifest=session.public['manifest'],policy=session.public['policy'])
            financial=audit_episode(session.episode)
            assert financial["valid"], financial
            access=PublicBoundary(session.step,100,initial["manifest"]["episode_id"])
            started=time.perf_counter()
            terminal=learner.run(access,initial)
            report=session.report
            rows.append(dict(training_seed=model["seed"],training_scenario=model["scenario"],
                             seed=seed,config=config,renamed_shuffled=bool(i%2),
                             steps=access.steps,seconds=time.perf_counter()-started,
                             financial_valid=financial["valid"],evidence_errors=access.errors,
                             passed=bool(terminal[2] and not terminal[3] and report['f1']==1 and not access.errors),
                             **{k:report[k] for k in ('precision','recall','f1','reward','tp','fp','fn')}))
        assert learner.checkpoint()==before
    return dict(root_namespace="optimization-generalization-v1",cases=rows,
                passed=all(r["passed"] for r in rows),count=len(rows),
                max_steps=max(r["steps"] for r in rows))


if __name__=="__main__":
    result=run()
    (ROOT/"reports/optimization-generalization.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k!="cases"}))
    raise SystemExit(not result["passed"])
