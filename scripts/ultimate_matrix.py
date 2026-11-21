"""Systematic financial and public-solvability coverage of supported configurations."""
import argparse
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import time

from auditforge.env import Session
from auditforge.financial_audit import audit_episode, _inspect_books
from auditforge.generator import TYPES, generate
from auditforge.policies import run_policy
from scripts.jury_batch import batch_company
from scripts.jury_blind import PublicActions

LEVELS = {
    "invoices": (40, 41, 84, 200),
    "timezone": ("-12:00", "+00:00", "+05:45", "+14:00"),
    "period_month": ("2000-01", "2028-02", "2029-02", "2099-12"),
    "boundary_payments": (False, True),
    "shuffle": (False, True),
    "counts_pattern": ("none", "duplicate", "allocation", "fx", "period", "one_each", "three_each", "asymmetric"),
    "interaction": (0, 1, 2),
    "clean": (False, True),
}


def obligations(row):
    return frozenset((i, row[i], j, row[j]) for i in range(len(row)) for j in range(i+1,len(row)))


def covering_array():
    """Greedy covering array with an explicit independently recounted pair obligation."""
    rows = list(itertools.product(*(range(len(values)) for values in LEVELS.values())))
    remaining = set().union(*(obligations(row) for row in rows))
    universe = len(remaining)
    selected = []
    candidate_pairs = [obligations(row) for row in rows]
    while remaining:
        best = max(range(len(rows)), key=lambda i: len(candidate_pairs[i] & remaining))
        selected.append(rows[best])
        remaining.difference_update(candidate_pairs[best])
    # Recount from selected literal factor values, not generator state.
    covered = set().union(*(obligations(row) for row in selected))
    if len(covered) != universe:
        raise AssertionError("Covering construction missed a declared pair")
    return selected, universe


def config_from_levels(row):
    config = {key:values[value] for (key,values),value in zip(LEVELS.items(),row)}
    pattern = config.pop("counts_pattern")
    counts = {
        "none": {}, "duplicate": {TYPES[0]:3}, "allocation": {TYPES[1]:3},
        "fx": {TYPES[2]:3}, "period": {TYPES[3]:3},
        "one_each": dict.fromkeys(TYPES,1), "three_each": dict.fromkeys(TYPES,3),
        "asymmetric": dict(zip(TYPES,(1,2,3,1))),
    }[pattern]
    return dict(config,counts=counts), pattern


def public_investigation(access, initial):
    """Exact rational reconstruction with only public records; independent of reconcile."""
    books = dict(manifest=initial["manifest"],policy=initial["policy"])
    for table in ("ledger","invoices","payments","fx"):
        cursor, books[table] = None, []
        while True:
            observation, _, terminated, truncated, _ = access.step(dict(tool="list_records",table=table,cursor=cursor,limit=50))
            if terminated or truncated or "error" in observation:
                raise AssertionError("Public evidence enumeration failed")
            books[table].extend(observation["result"]["records"])
            cursor = observation["result"]["next_cursor"]
            if cursor is None:
                break
    findings, _ = _inspect_books(books)
    claims = [dict(type=f["type"],affected_ids=f["affected_ids"],claimed_amount_minor=f["expected_amount_minor"],
                   currency=f["currency"],evidence_ids=f["evidence_ids"],explanation="Reconstructed from public sources with rational arithmetic.")
              for f in findings]
    return access.step(dict(tool="submit",findings=dict(episode_id=initial["manifest"]["episode_id"],findings=claims)))


def investigate(episode, independent):
    session = Session()
    initial, _ = session.reset(0, {}, "evaluation")
    session.episode = deepcopy(episode)
    session.public = session.episode["public"]
    initial.update(manifest=deepcopy(session.public["manifest"]),policy=deepcopy(session.public["policy"]))
    access = PublicActions(session.step)
    started = time.perf_counter()
    terminal = public_investigation(access,initial) if independent else run_policy(access,initial)
    elapsed = time.perf_counter()-started
    return dict(f1=session.report["f1"],steps=access.steps,seconds=elapsed,
                evidence_errors=access.errors,
                passed=bool(terminal[2] and not terminal[3] and terminal[1]==0 and
                            session.report["f1"]==1 and not access.errors and access.steps<=100 and elapsed<60))


def trial(root, label, index, config, episode=None, actual_seed=None):
    seed = int.from_bytes(hashlib.sha256(f"ultimate-matrix:{root}:{label}:{index}".encode()).digest()[:16],"big")
    seed = seed if actual_seed is None else actual_seed
    tick = time.perf_counter()
    try:
        generated_here = episode is None
        episode = generate(seed,config) if generated_here else episode
        generation_seconds=time.perf_counter()-tick if generated_here else None
        financial = audit_episode(episode)
        algorithms = {name:investigate(episode,independent) for name,independent in (("production",False),("rational_public",True))}
        public=episode["public"]
        return dict(seed=seed,config=config,label=label,generation_seconds=generation_seconds,
                    episode_id=public["manifest"]["episode_id"],records=len(public["ledger"]),
                    documents=public["manifest"]["documents"],issues=len(episode["truth"]),
                    financial_valid=financial["valid"],financial_errors=financial["errors"],algorithms=algorithms,
                    passed=financial["valid"] and all(x["passed"] for x in algorithms.values()))
    except Exception as error:
        return dict(seed=seed,config=config,label=label,passed=False,error=f"{type(error).__name__}: {error}")


def jury(root):
    """Twenty new data checks with five explicitly clean and five linked-error companies."""
    rows=[]
    for i in range(20):
        config=dict(invoices=(40,84,200)[i%3],timezone=("-12:00","+05:45","+14:00")[i%3],
                    period_month=("2000-02","2099-12","2029-02")[i%3],boundary_payments=True,
                    shuffle=bool(i%2))
        if i<5:
            config.update(clean=True,interaction=i%3)
        elif i<10:
            config.update(counts=dict.fromkeys(TYPES,1),interaction=1+i%2)
        elif i<14:
            config["counts"]={TYPES[i-10]:3}
        elif i<18:
            config["recognition_world"]=1+i%2
        else:
            config.update(counts=dict(zip(TYPES,(1,2,3,1))),interaction=i%3)
        rows.append(trial(root,"jury-data",i,config))
    return rows


def run(root):
    selected,pairs=covering_array()
    cases=[]
    for i,row in enumerate(selected):
        config,pattern=config_from_levels(row)
        cases.append(dict(trial(root,"covering",i,config),factor_indices=list(row),counts_pattern=pattern))
    active_before={(row["counts_pattern"],row["config"]["interaction"]) for row in cases
                   if not row["config"]["clean"]}
    desired=set(itertools.product(LEVELS["counts_pattern"],LEVELS["interaction"]))
    supplements=[]
    for i,(pattern,interaction) in enumerate(sorted(desired-active_before)):
        indices=[0]*len(LEVELS)
        indices[list(LEVELS).index("counts_pattern")]=LEVELS["counts_pattern"].index(pattern)
        indices[list(LEVELS).index("interaction")]=interaction
        config,_=config_from_levels(indices)
        config["clean"]=False
        supplements.append(dict(trial(root,"effective-supplement",i,config),counts_pattern=pattern))
    active_after=active_before|{(r["counts_pattern"],r["config"]["interaction"]) for r in supplements}
    # Out-of-array classes: unusual legal offsets, historical century edge,
    # all recognition variants, and dense multi-invoice batch settlements.
    holdout=[]
    for i in range(24):
        config=dict(invoices=(40,200)[i%2],timezone=("-00:30","+13:45","-09:30")[i%3],
                    period_month=("2000-02","2099-01")[i%2],boundary_payments=True,shuffle=bool(i%2))
        if i<16:
            config["recognition_world"]=i%4
        else:
            config.update(counts=dict.fromkeys(TYPES,3),interaction=i%3,clean=i==16)
        holdout.append(trial(root,"unseen-classes",i,config))
    dense=[]
    for n in (10,100):
        for dirty in (False,True):
            seed=root+n+int(dirty)
            dense.append(trial(root,"dense-batch",n+int(dirty),dict(batch_invoices=n,cutoff=dirty),
                               batch_company(seed,n,dirty),actual_seed=seed))
    jury_rows=jury(root+1)
    all_rows=cases+supplements+holdout+dense+jury_rows
    return dict(root=root,scope="Supported configuration pair coverage; fixed half-even rounding is the only declared rule.",
                factors={k:list(v) for k,v in LEVELS.items()},pair_obligations=pairs,pair_obligations_covered=pairs,
                covering=cases,effective_supplements=supplements,holdout=holdout,dense=dense,jury_data=jury_rows,
                effective_counts_interaction=dict(required=len(desired),before=len(active_before),
                    after=len(active_after),missing_before=[list(x) for x in sorted(desired-active_before)]),
                passed=all(row["passed"] for row in all_rows),failures=[row for row in all_rows if not row["passed"]],
                counts=dict(covering=len(cases),effective_supplements=len(supplements),holdout=len(holdout),dense=len(dense),jury_data=len(jury_rows),total=len(all_rows)),
                shared_implementation_risk="The public rational investigator shares _inspect_books with the independent financial validator. Production reconciliation is a separate detector. Neither public policy sees truth/provenance.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=728149011634)
    parser.add_argument("--output",type=Path,default=Path("reports/ultimate-matrix.json"))
    args=parser.parse_args()
    result=run(args.seed)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:result[k] for k in ("root","pair_obligations","counts","passed","failures")}))
    raise SystemExit(not result["passed"])