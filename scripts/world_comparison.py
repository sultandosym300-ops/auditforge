"""Grouped counterfactual recognition benchmark; uses only Python's standard library."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import time
import tracemalloc
from unittest.mock import patch

from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.generator import generate
from auditforge.policies import run_policy
from scripts.jury_blind import PublicActions

ROOT = Path(__file__).resolve().parents[1]
CONTROL = "e722984569a30dfdb69a938a0c35882ca1b886e5"
DEFAULT_SEED = 6982734491033
# Fingerprint of all four branches (public/pristine/truth/provenance) in the pinned
# control's 32 fit and 64 holdout families. It also works in a Git-free delivery.
CONTROL_DIGESTS = {DEFAULT_SEED:"b733bea2633f945403ce48e9328ff245be1b5476ad53d8052b037eb03d08f2b5",
                   272104686017:"6773828cd84b8b4600d497fd8df15cb485e87d0f76746866d6e9e5e1f88177b5"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def fingerprint(value):
    return sha256(canonical(value)).digest()


def family_seed(root, split, index):
    value = f"recognition-study-v1:{root}:{split}:{index}".encode()
    return int.from_bytes(sha256(value).digest()[:16], "big")


def family_config(seed):
    rng = random.Random(f"config:{seed}")
    return dict(invoices=rng.choice((40, 46, 57, 74, 82)),
                shuffle=rng.choice((True, False)), boundary_payments=rng.choice((True, False)),
                timezone=rng.choice(("+05:45", "-03:30", "-12:00", "+14:00")),
                period_month=rng.choice(("2028-02", "2031-12", "2048-07")))


def published_generator():
    # Execute the immutable baseline generator only. The evaluator and control
    # policy are held fixed for both arms. No subprocess handles private files.
    try:
        data = subprocess.check_output(["git", "show", CONTROL+":auditforge/generator.py"],
                                       cwd=ROOT, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return generate, False
    module = {"__name__": "frozen_auditforge_generator"}
    exec(compile(data, "1.1.4/auditforge/generator.py", "exec"), module)
    return module["generate"], True


def variants(arm, base):
    if arm == "control":
        return [(dict(base, clean=True), False),
                (dict(base, counts={"accounting_period": 2}), True)]
    return [(dict(base, recognition_world=variant), variant in (1, 2)) for variant in range(4)]


def marginal_views(public):
    manifest = {k:v for k,v in public["manifest"].items() if k != "episode_id"}
    header = [manifest, public["policy"]]
    return dict(ledger=fingerprint([header, public["ledger"]]),
                sources=fingerprint([header, public["invoices"], public["payments"], public["fx"]]))


def features(public):
    """Episode-level counts, amounts, date buckets, codes, order and paper format. No ID joins."""
    manifest = public["manifest"]
    start, end = map(datetime.fromisoformat, (manifest["period_start"], manifest["period_end"]))
    def outside(stamp):
        return not start <= datetime.fromisoformat(stamp) < end
    expenses = [r for r in public["ledger"] if r["account"] == "expense"]
    invoices = public["invoices"]
    outside_rows = [r for r in expenses if outside(r["timestamp"])]
    outside_docs = [r for r in invoices if outside(r["issued_at"])]
    ledger_counts = (len(outside_rows),sum(r["debit_minor"] for r in outside_rows))
    invoice_counts = (len(outside_docs),sum(r["total_minor"] for r in outside_docs))
    fields = dict(
        l_out=ledger_counts[0], l_round=sum(r["debit_minor"]==500000 for r in outside_rows),
        l_length=len(expenses), l_first_id=expenses[0]["row_id"][-1],
        l_first_out=outside(expenses[0]["timestamp"]),
        s_out=invoice_counts[0], s_round=sum(r["total_minor"]==500000 for r in outside_docs),
        s_ccy=public["payments"][0]["currency"], s_first_id=invoices[0]["doc_id"][-1],
        s_first_out=outside(invoices[0]["issued_at"]),
        s_links=sum("related_credit_doc_id" in inv for inv in invoices),
        s_layout="|".join(invoices[0]), s_repeat=len(invoices)-len({i["total_minor"] for i in invoices}),
        m_rows=manifest["records"], m_docs=manifest["documents"], m_zone=manifest["timezone"],
        m_company=manifest["company"].split()[0],
        # Test the opaque envelope ID independently from equality of the table views.
        m_id_nibble=manifest["episode_id"][-1],
        cross_count_diff=ledger_counts[0] != invoice_counts[0],
        cross_sum_diff=ledger_counts[1] != invoice_counts[1],
        cross_either_diff=ledger_counts != invoice_counts,
    )
    return fields


def fit_probes(rows):
    """Categorical naive Bayes with Laplace smoothing; fixed feature sets before holdout."""
    models = {}
    for name, prefixes in (("ledger_nb", ("l_",)), ("sources_nb", ("s_",)),
                           ("envelope_nb", ("m_",)), ("combined_no_join_nb", ("l_","s_","m_","cross_"))):
        keys = [k for k in rows[0][1] if k.startswith(prefixes)]
        counts = {key: defaultdict(Counter) for key in keys}
        label_counts = Counter()
        for label, feat in rows:
            label_counts[label] += 1
            for key in keys:
                counts[key][feat[key]][label] += 1
        models[name] = (counts, label_counts)
    clean_counts = {f["l_out"] for label,f in rows if not label}
    def predict(feat):
        result = dict(ledger_out_count=feat["l_out"] not in clean_counts,
                      count_amount_disagreement=feat["cross_either_diff"],
                      silence=False)
        for name, (counts, label_counts) in models.items():
            odds = 0.0
            for key, buckets in counts.items():
                observed = buckets.get(feat[key], {})
                for label, sign in [(True,1),(False,-1)]:
                    odds += sign*math.log((1+observed.get(label,0))/(1+len(buckets)+label_counts[label]))
            result[name] = odds > 1e-12
        return result
    return predict


def read_table(access, table):
    rows, cursor = [], None
    while True:
        result = access.step(dict(tool="list_records", table=table, cursor=cursor,limit=50))[0]["result"]
        rows.extend(result["records"])
        cursor = result["next_cursor"]
        if cursor is None:
            return rows


def cutoff_policy(access, initial, strategy):
    """Graduate from blind submit to aggregate-only to joining evidence, using the same action API."""
    manifest = initial["manifest"]
    start, end = (datetime.fromisoformat(manifest[k]) for k in ("period_start","period_end"))
    def in_period(stamp):
        return start <= datetime.fromisoformat(stamp) < end
    findings = []
    if strategy != "no_inspection":
        invoices = read_table(access, "invoices")
        expense = [r for r in read_table(access, "ledger") if r["account"]=="expense"]
        if strategy == "cutoff_join":
            docs = {d["invoice_id"]: d for d in invoices}
            pairs = [(r, docs[r["invoice_id"]]) for r in expense
                     if in_period(r["timestamp"]) != in_period(docs[r["invoice_id"]]["issued_at"])]
        else:
            outside = [r for r in expense if not in_period(r["timestamp"])]
            outside_docs = [d for d in invoices if not in_period(d["issued_at"])]
            differs = ((len(outside),sum(r["debit_minor"] for r in outside)) !=
                       (len(outside_docs),sum(d["total_minor"] for d in outside_docs)))
            # Separate rankings, no shared-key lookup or invoice/row comparison.
            pairs = zip(sorted(expense, key=lambda r:r["timestamp"], reverse=True)[:2],
                        sorted(invoices,key=lambda d:d["issued_at"], reverse=True)[:2]) if differs else []
        for row,doc in pairs:
            findings.append(dict(type="accounting_period", affected_ids=[row["row_id"]],
                currency=row["currency"], claimed_amount_minor=doc["total_minor"],
                evidence_ids=[row["row_id"],doc["doc_id"]], explanation="Recognition-period review."))
    return access.step(dict(tool="submit",findings=dict(episode_id=manifest["episode_id"],findings=findings)))


def policy_trial(episode, name):
    # The trusted harness supplies the selected generator's exact episode to reset.
    # The policy only sees initial observation and a step-only recorder.
    session = Session()
    with patch("auditforge.env.generate", return_value=episode):
        initial,_ = session.reset(0, {}, "evaluation")
    access = PublicActions(session.step)
    terminal = run_policy(access, initial) if name == "full_reconciliation" else cutoff_policy(access,initial,name)
    if not terminal[2] or terminal[3] or terminal[1] != 0 or access.errors:
        raise AssertionError((name, terminal, access.errors))
    report = session.report
    return {k:report[k] for k in ("f1","reward","tp","fp","fn")} | {"steps":access.steps}


def family_interval(values):
    # Each element is one independent family's mean. The four related worlds
    # must never enter the bootstrap as four independent companies.
    rng = random.Random(410933)
    ordered = sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(1000))
    return [round(ordered[24],4), round(ordered[974],4)]


def median(values):
    return round(statistics.median(values), 4)


def study(root, fit_count, test_count):
    baseline, from_git = published_generator()
    control_digest = sha256()
    digest = sha256()
    output = {}
    for arm, make in (("control",baseline),("candidate",generate)):
        train = []
        metric = defaultdict(list)
        family_scores = defaultdict(list)
        strategies = defaultdict(list)
        label_tp = defaultdict(Counter)
        exact_views = Counter()
        cohorts = []
        for split, count in (("fit",fit_count),("holdout",test_count)):
            if split == "holdout":
                predict = fit_probes(train)
            for i in range(count):
                seed = family_seed(root, split, i)
                base = family_config(seed)
                flags = defaultdict(list)
                predictions = defaultdict(list)
                ids = []
                for config, label in variants(arm,base):
                    tick = time.perf_counter()
                    ep = make(seed,config)
                    elapsed = time.perf_counter()-tick
                    if arm == "control":
                        control_digest.update(fingerprint(ep))
                    if bool(ep["truth"]) != label or len(ep["truth"]) != 2*label:
                        raise ValueError((arm,config,"unexpected label or multiplicity"))
                    public = ep["public"]
                    f = features(public)
                    if arm == "candidate" and f["cross_either_diff"]:
                        raise AssertionError("An aggregate mismatch exposes the candidate condition")
                    if split == "fit":
                        train.append((label,f))
                        continue
                    metric["generation_ms"].append(1000*elapsed)
                    metric["public_json_bytes"].append(len(canonical(public)))
                    if i < 8:
                        tracemalloc.start()
                        make(seed,config)
                        peak = tracemalloc.get_traced_memory()[1]
                        tracemalloc.stop()
                        metric["sample_generation_peak_bytes"].append(peak)
                    det = fingerprint(ep)
                    if det != fingerprint(make(seed,config)):
                        raise AssertionError("Different books at identical seed/config")
                    digest.update(det)
                    views = marginal_views(public)
                    for key, value in views.items():
                        flags[key].append((label,value))
                    ids.append(public["manifest"]["episode_id"])
                    audited = audit_episode(ep)
                    if not audited["valid"]:
                        raise AssertionError((arm,seed,config,audited["errors"]))
                    for name, guess in predict(f).items():
                        predictions[name].append(guess==label)
                        label_tp[name].update(["tp" if guess and label else "fp" if guess
                                              else "fn" if label else "tn"])
                    for strategy in ("no_inspection","aggregate_guess","cutoff_join","full_reconciliation"):
                        trial = policy_trial(ep,strategy)
                        strategies[strategy].append(trial)
                        if strategy in ("cutoff_join","full_reconciliation") and trial["f1"] != 1:
                            raise AssertionError((arm,seed,config,strategy,trial))
                if split == "holdout":
                    for key, labeled in flags.items():
                        if Counter(value for label,value in labeled if label) == Counter(value for label,value in labeled if not label):
                            exact_views[key] += 1
                    for name, values in predictions.items():
                        family_scores[name].append(statistics.mean(values))
                    if len(set(ids)) != len(ids):
                        raise AssertionError("Duplicate episode IDs within family")
                    cohorts.append(dict(seed=seed,config=base,episode_ids=ids))
        if arm == "candidate" and any(exact_views[k] != test_count for k in ("ledger","sources")):
            raise AssertionError("A candidate family leaks its condition through a one-sided view")
        probes = {}
        for key, values in family_scores.items():
            c = label_tp[key]
            probes[key] = dict(accuracy=statistics.mean(values), family_bootstrap_95=family_interval(values),
                               positive_f1=2*c["tp"]/(2*c["tp"]+c["fp"]+c["fn"]), **c)
        policies = {key: {k:round(statistics.mean(v[k] for v in runs),4)
                           for k in ("f1","reward","steps")} | dict(max_steps=max(v["steps"] for v in runs),
                           solved=sum(v["f1"]==1 for v in runs),
                           tp=sum(v["tp"] for v in runs), fp=sum(v["fp"] for v in runs),
                           fn=sum(v["fn"] for v in runs))
                    for key,runs in strategies.items()}
        output[arm] = dict(holdout_episodes=len(strategies["cutoff_join"]),
                           independent_audit_pass=len(strategies["cutoff_join"]),
                           exact_regeneration_pass=len(strategies["cutoff_join"]),
                           identical_label_marginal_families=dict(ledger=exact_views["ledger"],sources=exact_views["sources"]),
                           probes=probes, policies=policies,median={k:median(v) for k,v in metric.items()},
                           cohorts=cohorts)
    measured_digest = control_digest.hexdigest()
    if root in CONTROL_DIGESTS and (fit_count,test_count)==(32,64):
        if measured_digest != CONTROL_DIGESTS[root]:
            raise AssertionError(("1.1.4 reference digest mismatch", measured_digest))
    elif not from_git:
        raise RuntimeError("Custom baseline cohorts require the 1.1.4 commit in Git history")
    return dict(root=root, fit_families=fit_count, holdout_families=test_count, control_sha=CONTROL,
                control_source="git checkpoint" if from_git else "byte-verified compatibility generator",
                baseline_all_branches_digest=measured_digest, holdout_digest=digest.hexdigest(),
                core_source_sha256={p.name:sha256(p.read_bytes().replace(b"\r\n",b"\n")).hexdigest()
                                    for p in (ROOT/"auditforge/generator.py", ROOT/"auditforge/recognition_worlds.py")},
                control=output["control"],candidate=output["candidate"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=DEFAULT_SEED,
                        help="Archive-compatible roots: 6982734491033 (main) or 272104686017 (confirmation). Other roots require the control commit in Git.")
    parser.add_argument("--fit",type=int,default=32)
    parser.add_argument("--holdout",type=int,default=64)
    parser.add_argument("--output",type=Path,default=ROOT/"reports/world-comparison.json")
    options=parser.parse_args()
    if min(options.fit,options.holdout) < 1:
        parser.error("both splits require one or more families")
    result=study(options.seed,options.fit,options.holdout)
    options.output.parent.mkdir(parents=True,exist_ok=True)
    options.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({arm:{key:result[arm][key] for key in ("holdout_episodes","probes","policies","median")}
                          for arm in ("control","candidate")},indent=2))
