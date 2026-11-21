"""Independent proof-local arithmetic and exhaustive evidence/matcher checks."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
from fractions import Fraction
import itertools
import json
from pathlib import Path
import random

from auditforge.generator import TYPES, generate
from auditforge.matcher import evaluate, oracle


def proof_amount(public, claim):
    """Inspect only the submitted records, without reading truth or provenance."""
    selected = set(claim["evidence_ids"])
    books = {r.get("row_id", r.get("doc_id")): r
             for table in ("ledger", "invoices", "payments", "fx") for r in public[table]
             if r.get("row_id", r.get("doc_id")) in selected}
    if not selected <= books.keys():
        raise ValueError("Unknown evidence")
    rows = [books[rid] for rid in claim["affected_ids"]]
    kind = claim["type"]
    if kind in ("duplicate_invoice", "accounting_period"):
        invoices = [r for r in books.values() if "issued_at" in r and
                    r["invoice_id"] == rows[0]["invoice_id"]]
        if len(invoices) != 1 or any(r["account"] != "expense" or
                                    r["invoice_id"] != invoices[0]["invoice_id"] for r in rows):
            raise ValueError("Wrong invoice or recognition rows")
        inv = invoices[0]
        if kind == "duplicate_invoice":
            if len(rows) < 2:
                raise ValueError("One posting cannot establish duplicate recognition")
            return abs(sum(r["debit_minor"] for r in rows) - inv["total_minor"])
        start = datetime.fromisoformat(public["manifest"]["period_start"])
        end = datetime.fromisoformat(public["manifest"]["period_end"])
        inside = lambda value: start <= datetime.fromisoformat(value) < end
        if len(rows) != 1 or inside(rows[0]["timestamp"]) == inside(inv["issued_at"]):
            raise ValueError("No recognition-period discrepancy")
        return inv["total_minor"]
    if len(rows) != 1 or rows[0]["account"] != "payable":
        raise ValueError("Unsupported affected settlement")
    row = rows[0]
    payments = [r for r in books.values() if "invoice_refs" in r and r["payment_id"] == row["payment_id"]]
    if len(payments) != 1:
        raise ValueError("Missing source payment")
    pay = payments[0]
    promised = sum(ref["allocated_minor"] for ref in pay["invoice_refs"]
                   if ref["invoice_id"] == row["invoice_id"])
    base = public["manifest"]["base_currency"]
    if pay["currency"] == base:
        rate = Fraction(1)
    else:
        zone = datetime.fromisoformat(public["manifest"]["period_start"]).tzinfo
        date = datetime.fromisoformat(pay["timestamp"]).astimezone(zone).date().isoformat()
        quotes = [r for r in books.values() if r.get("source_currency") == pay["currency"]
                  and r.get("target_currency") == base and r.get("date") == date]
        if len(quotes) != 1:
            raise ValueError("Missing applicable quote")
        rate = Fraction(quotes[0]["rate"])
    exponents = public["manifest"]["currency_exponents"]
    scale = Fraction(10) ** (exponents[base] - exponents[pay["currency"]])
    booked = row["allocation_source_minor"]
    amount = (round(Fraction(promised) * rate * scale) - round(Fraction(booked) * rate * scale)
              if kind == "payment_allocation"
              else row["debit_minor"] - round(Fraction(booked) * rate * scale))
    if not amount:
        raise ValueError("No monetary discrepancy")
    return abs(amount)


def reference_metrics(truth, claims, steps):
    """Enumerate all injective assignments, independent of augmenting-path matcher."""
    if not claims and not truth:
        return dict(tp=0, fp=0, fn=0, precision=0, recall=0, f1=1, reward=max(-1, 1-.002*steps))
    signatures = []
    edges = []
    for claim in claims:
        candidates = []
        supported = set()
        for j, issue in enumerate(truth):
            scalar = (claim["type"] == issue["type"] and claim["currency"] == issue["currency"]
                      and set(claim["affected_ids"]) == set(issue["affected_ids"])
                      and abs(claim["claimed_amount_minor"]-issue["expected_amount_minor"]) <= issue.get("tolerance_minor", 0))
            proofs = [frozenset(p) for p in issue["evidence_sets"] if set(p) <= set(claim["evidence_ids"])]
            if scalar and proofs:
                candidates.append(j)
                supported.update(proofs)
        sig = (claim["type"], frozenset(claim["affected_ids"]), claim["currency"],
               claim["claimed_amount_minor"], frozenset(supported))
        edges.append(candidates if sig not in signatures else [])
        signatures.append(sig)
    best = 0
    for choices in itertools.product(range(-1, len(truth)), repeat=len(claims)):
        used = [j for j in choices if j >= 0]
        if len(set(used)) == len(used) and all(j < 0 or j in edges[i] for i, j in enumerate(choices)):
            best = max(best, len(used))
    fp, fn = len(claims)-best, len(truth)-best
    precision = best/(best+fp) if best+fp else 0
    recall = best/(best+fn) if best+fn else 0
    f1 = 2*best/(2*best+fp+fn) if 2*best+fp+fn else 1
    return dict(tp=best, fp=fp, fn=fn, precision=precision, recall=recall,
                f1=f1, reward=max(-1,min(1,2*f1-1-.002*steps)))


def matcher_cases(root, count):
    rng = random.Random(root)
    rows = []
    for index in range(count):
        n, m = rng.randrange(5), rng.randrange(5)
        truth = [dict(type=TYPES[j%4], affected_ids=["r"+str(j%2)], currency="KZT",
                      expected_amount_minor=100+j, tolerance_minor=j%2,
                      evidence_sets=[["proof"+str(j)],["alternate"+str(j)]]) for j in range(m)]
        claims = []
        for i in range(n):
            if truth and rng.random() < .8:
                t = rng.choice(truth)
                f = dict(type=t["type"], affected_ids=list(t["affected_ids"]),
                         claimed_amount_minor=t["expected_amount_minor"]+rng.choice((-1,0,1)),
                         currency=rng.choice(("KZT","KZT","USD")),
                         evidence_ids=list(rng.choice(t["evidence_sets"])), explanation="")
            else:
                f = dict(type=TYPES[i%4], affected_ids=["unknown"], claimed_amount_minor=100,
                         currency="KZT",evidence_ids=[],explanation="")
            if claims and rng.random() < .25:
                f = deepcopy(claims[-1])
                f["explanation"] = "Different prose"
                f["evidence_ids"] += ["irrelevant"]
                f["evidence_ids"] = list(dict.fromkeys(f["evidence_ids"]))
            claims.append(f)
        steps = rng.choice((0,1,49,99,100))
        expected = reference_metrics(truth, claims, steps)
        actual = evaluate("test",truth,dict(episode_id="test",findings=claims),steps)
        rows.append(dict(index=index,steps=steps,passed=expected==actual,expected=expected,actual=actual))
    return rows



def fixed_reward_cases(root):
    """Twenty separately named expectations, without the production metric helper."""
    ep = generate(root, dict(counts=dict.fromkeys(TYPES, 1)))
    truth = ep["truth"]
    eid = ep["public"]["manifest"]["episode_id"]
    complete = oracle(ep)["findings"]
    empty = dict(episode_id=eid, findings=[])
    cases = []
    def record(name, claims, steps=0, valid=True, targets=None, episode_id=eid):
        targets = truth if targets is None else targets
        expected = (reference_metrics(targets, claims, steps) if valid else
                    dict(tp=0,fp=0,fn=len(targets),precision=0,recall=0,f1=0,reward=-1,
                         error="invalid_submission"))
        actual = evaluate(eid,targets,dict(episode_id=episode_id,findings=claims),steps)
        cases.append(dict(name=name,expected=expected,actual=actual,passed=actual==expected))
    first = deepcopy(complete[0])
    record("complete",complete)
    record("dirty_silence",[])
    record("clean_silence",[],targets=[])
    record("clean_accusation",[first],targets=[])
    record("partial_answer",[first])
    record("repeat_same_finding",[first,deepcopy(first)])
    record("permuted_evidence_and_affected", [dict(first,affected_ids=first["affected_ids"][::-1],
                                                evidence_ids=first["evidence_ids"][::-1])])
    record("unrelated_evidence_superset",[dict(first,evidence_ids=first["evidence_ids"]+["irrelevant"])])
    record("missing_necessary_document",[dict(first,evidence_ids=first["evidence_ids"][1:])])
    record("wrong_currency",[dict(first,currency="USD")])
    record("wrong_type",[dict(first,type=next(t for t in TYPES if t!=first["type"]))])
    record("wrong_amount_one_minor",[dict(first,claimed_amount_minor=first["claimed_amount_minor"]+1)])
    record("forged_affected",[dict(first,affected_ids=["forged"])])
    record("forged_all_evidence",[dict(first,evidence_ids=["forged"])])
    record("duplicate_evidence_schema",[dict(first,evidence_ids=first["evidence_ids"]*2)],valid=False)
    record("negative_money_schema",[dict(first,claimed_amount_minor=-1)],valid=False)
    record("thirty_one_findings_schema",[first]*31,valid=False)
    record("overlong_explanation",[dict(first,explanation="x"*1001)],valid=False)
    record("wrong_episode",complete,valid=False,episode_id="other")
    record("exact_cost_ninety_nine_inspections",complete,steps=99)
    assert len(cases)==20
    return cases

def run(root=318879406122, count=60, graphs=500):
    rng = random.Random(root)
    cases = []
    tally = Counter()
    for i in range(count):
        seed = rng.getrandbits(128)
        config = (dict(recognition_world=i%4) if i%5==0
                  else dict(interaction=i%3, counts=dict.fromkeys(TYPES,1+i%3)))
        ep = generate(seed,config)
        public = ep["public"]
        eid = public["manifest"]["episode_id"]
        foreign_ep = generate(seed+1,config)
        foreign_ids = [r.get("row_id",r.get("doc_id")) for table in ("ledger","invoices","payments","fx")
                       for r in foreign_ep["public"][table]]
        for issue, finding in zip(ep["truth"], oracle(ep)["findings"]):
            measured = proof_amount(public,finding)
            checks = dict(proof_local_amount=measured==issue["expected_amount_minor"])
            scored = lambda f: evaluate(eid,ep["truth"],dict(episode_id=eid,findings=[f]),19)["tp"]
            checks["complete"]=scored(finding)==1
            checks["permutation"]=scored(dict(finding,evidence_ids=finding["evidence_ids"][::-1],
                                               affected_ids=finding["affected_ids"][::-1]))==1
            extra = next(r["row_id"] for r in public["ledger"] if r["row_id"] not in finding["evidence_ids"])
            checks["irrelevant_superset"]=scored(dict(finding,evidence_ids=finding["evidence_ids"]+[extra]))==1
            checks["foreign_documents"]=scored(dict(finding,evidence_ids=foreign_ids[:len(finding["evidence_ids"])]))==0
            for rid in finding["evidence_ids"]:
                evidence = [r for r in finding["evidence_ids"] if r!=rid]
                altered = dict(finding,evidence_ids=evidence)
                try:
                    proof_amount(public,altered)
                    sufficient = True
                except (ValueError,KeyError):
                    sufficient = False
                checks["omit_"+rid]=scored(altered)==0 and not sufficient
            for alternate in issue["evidence_sets"]:
                checks["declared_proof_"+"|".join(alternate)]=scored(dict(finding,evidence_ids=alternate))==1
            for name in checks:
                tally[name.split("_")[0]] += 1
            cases.append(dict(seed=seed,config=config,type=issue["type"],affected_ids=issue["affected_ids"],
                              expected=issue["expected_amount_minor"],measured=measured,checks=checks,
                              passed=all(checks.values())))
    match = matcher_cases(root+1,graphs)
    fixed = fixed_reward_cases(root+2)
    return dict(root=root,passed=all(r["passed"] for r in cases+match+fixed),
                proof_cases=cases,matcher_cases=match,reward_checks=fixed,
                scope="Amounts reconstructed from submitted evidence only using Fraction, with no generator arithmetic. Exhaustive matcher reference shares semantic duplicate definition, so this does not independently establish that definition's correctness.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=318879406122)
    parser.add_argument("--output",type=Path,default=Path("reports/ultimate-evidence.json"))
    args=parser.parse_args()
    result=run(args.seed)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps(dict(passed=result["passed"],proof_cases=len(result["proof_cases"]),
                         matcher_cases=len(result["matcher_cases"]))))
    raise SystemExit(not result["passed"])
