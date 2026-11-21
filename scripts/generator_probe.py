"""Public-only generator hypotheses, with labels scored only after prediction."""
import argparse
import copy
import hashlib
import json
import subprocess
from unittest.mock import patch
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.generator import generate
from auditforge.policies import run_policy
from auditforge.reconcile import reconcile

DEPENDENCIES = {
    "manifest": "seed+canonical config hash -> episode_id; RNG -> company; policy config -> period/timezone; table cardinality -> counts",
    "fx": "33 dates starting period_start-1 day; baseline fixed base+date index modulo7/10; revised independent private company quote history with daily increments; ordinary ID RNG -> row_id",
    "invoice": "index periodicity -> default round totals; RNG -> amount/date/entity/ID/description; due_at=issued_at+30 days; refund payment -> related_credit_doc_id",
    "payment": "invoice index modulo4 -> split; modulo9 -> refund; modulo3 -> foreign; source conversion -> source amount; invoice time except closing/boundary cases -> timestamp",
    "ledger": "double-entry projection -> accounts/debits/credits; RNG -> IDs; invoice/payment keys -> links; payment -> allocation_source_minor and published fx_rate/date",
    "mutation": "private domain-separated assignment RNG -> target invoices; changed paired rows -> ledger; explicit causal change -> truth/provenance",
    "recognition": "family private hash -> nominal/recurring obligations/date selection; source_bit -> issued dates; book_bit -> postings; mismatch -> two offsetting cutoff issues; blind selection -> private hash",
}


def read_public(step, initial):
    public = {"manifest": initial["manifest"], "policy": initial["policy"]}
    steps = 0
    for table in ("ledger", "invoices", "payments", "fx"):
        public[table] = []
        cursor = None
        while True:
            result = step(dict(tool="list_records", table=table, cursor=cursor, limit=50))
            steps += 1
            if result[2] or result[3]:
                raise RuntimeError("inspection exhausted")
            page = result[0]["result"]
            public[table].extend(page["records"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
    return public, steps


def formula_rate_findings(public):
    """Ignore all quote values, retaining date/currency/ID solely as evidence addresses."""
    public = copy.deepcopy(public)
    start = datetime.fromisoformat(public["manifest"]["period_start"]).date()
    bases = {"USD": Decimal(490), "EUR": Decimal(530), "JPY": Decimal(3)}
    for quote in public["fx"]:
        date = datetime.fromisoformat(quote["date"]).date()
        quote["rate"] = str(bases[quote["source_currency"]] +
                            Decimal(((date-start).days+1) % 7)/10)
    return reconcile(public)


def run(root, count=64, baseline=False):
    make = generate
    if baseline:
        source=subprocess.check_output(["git","show","b77ad073daeb8ca3358faeed0d5ae100c909eb2d:auditforge/generator.py"])
        module={"__name__":"frozen_generator"}
        exec(compile(source,"baseline-generator.py","exec"),module)
        make=module["generate"]
    rows, quote_rows, formula_hits = [], 0, 0
    for i in range(count):
        seed = int.from_bytes(hashlib.sha256(f"generator-probe-v1:{root}:{i}".encode()).digest()[:16], "big")
        config = dict(clean=i%4==0, interaction=i%3,
                      timezone=("+05:45", "-03:30", "+14:00", "-12:00")[i%4],
                      period_month=("2028-02", "2031-12")[i%2])
        session = Session()
        with patch("auditforge.env.generate", return_value=make(seed,config)):
            initial, _ = session.reset(seed, config, "evaluation")
        public, steps = read_public(session.step, initial)
        # Predictions consume public values only. Trusted code scores after submission.
        findings = formula_rate_findings(public)[:30]
        session.step(dict(tool="submit", findings=dict(
            episode_id=initial["manifest"]["episode_id"], findings=findings)))
        assert "error" not in session.report, session.report
        proper=reconcile(public)
        from auditforge.matcher import evaluate
        proper_score=evaluate(initial["manifest"]["episode_id"], session.episode["truth"],dict(episode_id=initial["manifest"]["episode_id"],findings=proper), steps)
        assert proper_score["f1"]==1
        rows.append(dict(seed=seed, config=config, steps=steps+1, proper_f1=proper_score["f1"],
                         financial_valid=audit_episode(session.episode)["valid"],
                         **session.report))
        start = datetime.fromisoformat(public["manifest"]["period_start"]).date()
        for quote in public["fx"]:
            offset = (datetime.fromisoformat(quote["date"]).date()-start).days+1
            expected = {"USD":Decimal(490),"EUR":Decimal(530),"JPY":Decimal(3)}[quote["source_currency"]]+Decimal(offset%7)/10
            quote_rows += 1
            formula_hits += Decimal(quote["rate"]) == expected
    # Falsifier: predictions must respond to monetary facts, unlike the formula.
    first = make(root, dict(counts={"fx_conversion":1}))
    alternate = copy.deepcopy(first["public"])
    for quote in alternate["fx"]:
        quote["rate"] = str(Decimal(quote["rate"]) + Decimal("0.031"))
    formula_unchanged = formula_rate_findings(first["public"]) == formula_rate_findings(alternate)
    real_changed = reconcile(first["public"]) != reconcile(alternate)
    return dict(root_seed=root, episodes=count, dependencies=DEPENDENCIES,
                quote_formula=dict(correct=formula_hits, total=quote_rows),
                full_findings_mean_f1=sum(r["f1"] for r in rows)/count,
                min_steps=min(r["steps"] for r in rows), max_steps=max(r["steps"] for r in rows),
                interpretation="Generator-specific monetary shortcut. All pages including quote IDs are still read. No evidence acquisition saving or isolation breach demonstrated.",
                falsifier=dict(formula_ignores_changed_quote_values=formula_unchanged,
                               financial_reconciliation_changes=real_changed,
                               scope="Public calculation sensitivity control, not a generated/validated financial episode."),
                cases=rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=584049197113)
    p.add_argument("--baseline",action="store_true",help="Evaluate pinned 2.0 generator from Git history")
    p.add_argument("--count", type=int, default=64)
    p.add_argument("--output", type=Path, default=Path("reports/generator-probe.json"))
    a = p.parse_args()
    result = run(a.seed, a.count, a.baseline)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("cases","dependencies")}))
