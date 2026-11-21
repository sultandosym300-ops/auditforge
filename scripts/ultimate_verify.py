"""One-command independent invariant audit and published-rubric reconstruction."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from auditforge.generator import generate
from auditforge.verify import transform, check_transitions
from scripts import ultimate_contract, ultimate_evidence, ultimate_matrix

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=801973140685)
    args=parser.parse_args()
    if not __debug__:
        parser.error("assertions must be enabled")
    started=time.perf_counter()
    out=ROOT/"work/ultimate-legacy"
    subprocess.run([sys.executable,"-m","scripts.jury_gauntlet","--seed",str(args.seed),
                    "--report-dir",str(out)],check=True,cwd=ROOT)
    contract=ultimate_contract.run()
    data=ultimate_matrix.jury(args.seed+1)
    rewards=ultimate_evidence.fixed_reward_cases(args.seed+2)
    pairs=[]
    for row in data:
        ep=generate(row["seed"],row["config"])
        changed=transform(ep,row["seed"]+19)
        check_transitions(ep,changed)
        pairs.append(dict(seed=row["seed"],config=row["config"],exact_actions_and_renamed=True,passed=True))
    matrix=ultimate_matrix.run(args.seed+3)
    evidence=ultimate_evidence.run(args.seed+4)
    subprocess.run([sys.executable,"-m","scripts.ultimate_adaptive"],check=True,cwd=ROOT)
    legacy=json.loads((out/"JURY_GAUNTLET_RESULTS.json").read_text(encoding="utf8"))
    engineering=legacy["engineering"]
    rubric={"Contract & Isolation":25*sum(r["passed"] for r in contract["contract_checks"])/20,
            "Data & Truth":25*sum(r["passed"] for r in data)/20,
            "Reward Robustness":25*sum(r["passed"] for r in rewards)/20,
            "Reproducibility & Generalization":15*sum(r["passed"] for r in pairs)/20,
            "Engineering & Explanation":2*sum(engineering.values())}
    result=dict(core_version="2.0.1",root=args.seed,official_score=None,rubric=rubric,
                contract=contract,data=data,reward_checks=rewards,pairs=pairs,
                matrix=matrix,evidence=evidence,engineering=engineering,
                seconds=time.perf_counter()-started,
                passed=all(r["passed"] for r in data+rewards+pairs) and
                       matrix["passed"] and evidence["passed"] and
                       all(c["passed"] for c in legacy["checks"]))
    (ROOT/"reports/ultimate-jury.json").write_text(json.dumps(result,indent=2),encoding="utf8")
    print(json.dumps(dict(rubric=rubric,passed=result["passed"],seconds=result["seconds"])))
    return int(not result["passed"])


if __name__=="__main__":
    raise SystemExit(main())
