"""SHORTCUT_HUNTER 2: reward-selected public query prefixes and weak claim templates."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

from auditforge.env import Session
from auditforge.generator import TYPES
from auditforge.policies import run_policy
from auditforge.shortcut_hunter import tree_model
from scripts.jury_blind import PublicActions

ROOT = Path(__file__).resolve().parents[1]
MODES = ("ledger_prefix", "source_prefix", "joint_prefix", "all_public", "sequential")
CLASSES = ("clean",) + TYPES


def cases(root, split, count):
    for family in range(count):
        seed = int.from_bytes(hashlib.sha256(f"ultimate-adaptive:{root}:{split}:{family}".encode()).digest()[:16], "big")
        common = dict(invoices=(40, 57, 82)[family % 3], shuffle=bool(family % 2),
                      timezone=("+05:45", "-03:30", "+14:00")[family % 3],
                      period_month=("2028-02", "2031-12")[family % 2])
        configs = [(dict(common, counts={kind: 1}, clean=clean), kind)
                   for kind in TYPES for clean in (True, False)]
        configs += [(dict(common, recognition_world=i), "recognition") for i in range(4)]
        for config, scenario in configs:
            yield dict(seed=seed, config=config, family=f"{split}-{family}", scenario=scenario)


def collect(initial, step, mode):
    public = dict(manifest=initial["manifest"], policy=initial["policy"],
                  ledger=[], invoices=[], payments=[], fx=[])
    if mode == "sequential":
        first = collect(initial, step, "ledger_prefix")
        degrees = Counter(r["invoice_id"] for r in first["ledger"] if r["account"] == "expense")
        candidates = {iid for iid, n in degrees.items() if n > 1}
        if candidates:
            cursor = None
            while True:
                observation, reward, done, truncated, info = step(dict(tool="list_records", table="invoices", limit=50, cursor=cursor))
                if reward or done or truncated or info or "error" in observation:
                    raise AssertionError("Unexpected sequential inspection transition")
                first["invoices"].extend(observation["result"]["records"])
                cursor = observation["result"]["next_cursor"]
                found = {r["invoice_id"] for r in first["invoices"]}
                if found >= candidates or cursor is None:
                    break
        return first
    tables = {"ledger_prefix": ("ledger",), "source_prefix": ("invoices", "payments"),
              "joint_prefix": ("ledger", "invoices", "payments"), "all_public": ("ledger", "invoices", "payments", "fx")}[mode]
    for table in tables:
        cursor = None
        while True:
            observation, reward, done, truncated, info = step(dict(tool="list_records", table=table, limit=50, cursor=cursor))
            if reward or done or truncated or info or "error" in observation:
                raise AssertionError("Unexpected inspection transition")
            page = observation["result"]
            public[table].extend(page["records"])
            cursor = page["next_cursor"]
            if mode != "all_public" or cursor is None:
                break
    return public


def features(public):
    output = {}
    for table in ("ledger", "invoices", "payments", "fx"):
        rows = public[table]
        output[table + "_count"] = len(rows)
        output[table + "_layout"] = ",".join(rows[0]) if rows else ""
        output[table + "_id_tail"] = (rows[0].get("row_id", rows[0].get("doc_id", ""))[-1:] if rows else "")
    ledger = public["ledger"]
    output.update(expense_count=sum(r["account"] == "expense" for r in ledger),
                  null_count=sum(v is None for row in ledger for v in row.values()),
                  maximum_degree=max(Counter(r["invoice_id"] for r in ledger).values(), default=0),
                  refund_count=sum(p["amount_minor"] < 0 for p in public["payments"]),
                  foreign_count=sum(p["currency"] != "KZT" for p in public["payments"]),
                  round_total=sum(i["total_minor"] % 10000 == 0 for i in public["invoices"]),
                  outside_count=sum(not public["manifest"]["period_start"] <= r["timestamp"] < public["manifest"]["period_end"] for r in ledger),
                  repeated_totals=sum(n > 1 for n in Counter(i["total_minor"] for i in public["invoices"]).values()))
    return output


def fit(rows, forest=False):
    keys = sorted(rows[0][0])
    rng = random.Random(5719240)
    models = {}
    for kind in CLASSES:
        examples = [(x, label == kind) for x, label in rows]
        models[kind] = [tree_model(rng.choices(examples, k=len(examples)), keys, depth=3, rng=rng)
                        for _ in range(9)] if forest else [tree_model(examples, keys, depth=3)]
    def predict(x):
        votes = {kind: statistics.mean(bool(model(x)) for model in group) for kind, group in models.items()}
        return max(CLASSES, key=lambda kind: votes[kind]), max(votes.values())
    return predict


def weak_findings(public, kind):
    """Claim templates use graph links and nominal guesses, never reconcile dates or FX."""
    if kind == "clean":
        return []
    expenses = [r for r in public["ledger"] if r["account"] == "expense"]
    docs = {d["invoice_id"]: d for d in public["invoices"]}
    if kind == "duplicate_invoice":
        grouped = defaultdict(list)
        for row in expenses:
            grouped[row["invoice_id"]].append(row)
        pairs = [rows[:2] for rows in grouped.values() if len(rows) > 1]
        return [dict(type=kind, affected_ids=[r["row_id"] for r in rows],
                     claimed_amount_minor=rows[0]["debit_minor"], currency=rows[0]["currency"],
                     evidence_ids=[r["row_id"] for r in rows] + [docs[rows[0]["invoice_id"]]["doc_id"]],
                     explanation="Graph multiplicity candidate.") for rows in pairs if rows[0]["invoice_id"] in docs][:30]
    if kind == "accounting_period" and expenses:
        row = expenses[0]
        evidence = [row["row_id"]]
        if row["invoice_id"] in docs:
            evidence.append(docs[row["invoice_id"]]["doc_id"])
        return [dict(type=kind, affected_ids=[row["row_id"]], claimed_amount_minor=row["debit_minor"],
                     currency=row["currency"], evidence_ids=evidence, explanation="Prefix timing candidate.")]
    rows = [r for r in public["ledger"] if r["account"] == "payable" and r["payment_id"]]
    if not rows:
        return []
    row = rows[0]
    payment = next((p for p in public["payments"] if p["payment_id"] == row["payment_id"]), None)
    evidence = [row["row_id"]] + ([payment["doc_id"]] if payment else [])
    return [dict(type=kind, affected_ids=[row["row_id"]], claimed_amount_minor=max(1, row["debit_minor"] // 2),
                 currency=row["currency"], evidence_ids=evidence, explanation="Nominal surface guess.")]


def submit(initial, step, findings):
    return step(dict(tool="submit", findings=dict(episode_id=initial["manifest"]["episode_id"], findings=findings)))


def policy(initial, step, name, selected=None, models=None):
    if name == "majority":
        return submit(initial, step, [])
    if name in ("random", "reconciliation"):
        class Bridge:
            def __init__(self, action):
                self.step = action
        return run_policy(Bridge(step), initial, name)
    if name == "simple":
        public = collect(initial, step, "joint_prefix")
        kind = "duplicate_invoice" if features(public)["maximum_degree"] > 4 else "clean"
        return submit(initial, step, weak_findings(public, kind))
    mode, model_name, threshold = selected
    public = collect(initial, step, mode)
    kind, confidence = models[mode, model_name](features(public))
    if confidence < threshold:
        kind = "clean"
    return submit(initial, step, weak_findings(public, kind))


def trial(case, name, selected=None, models=None):
    session = Session()
    initial, _ = session.reset(case["seed"], case["config"], "evaluation")
    access = PublicActions(session.step)
    start = time.perf_counter()
    final = policy(initial, access.step, name, selected, models)
    duration = time.perf_counter() - start
    assert final[2] and not final[3] and not access.errors
    score = session.report
    truth = session.episode["truth"]
    findings = access.claims
    claim_types = {f["type"] for f in findings}
    true_types = {t["type"] for t in truth}
    affected = {rid for f in findings for rid in f["affected_ids"]}
    actual = {rid for t in truth for rid in t["affected_ids"]}
    complete = sum(any(set(f["evidence_ids"]) >= set(es) for es in t["evidence_sets"])
                   for f in findings for t in truth if f["type"] == t["type"]
                   and set(f["affected_ids"]) == set(t["affected_ids"]))
    return dict(family=case["family"], scenario=case["scenario"], **score,
                steps=access.steps, inspection_steps=access.steps-1, seconds=duration,
                issued_findings=len(findings), complete_proofs=complete,
                any_error_correct=bool(findings) == bool(truth), type_set_correct=claim_types == true_types,
                affected_set_correct=affected == actual,
                amount_currency_set_correct={(f["type"], f["claimed_amount_minor"], f["currency"]) for f in findings}
                    == {(t["type"], t["expected_amount_minor"], t["currency"]) for t in truth},
                exact_findings=score["fp"] == score["fn"] == 0)


def summarize(rows):
    keys = ("precision", "recall", "f1", "reward", "steps", "inspection_steps", "seconds")
    result = {f"mean_{key}": statistics.mean(r[key] for r in rows) for key in keys}
    result.update(tp=sum(r["tp"] for r in rows), fp=sum(r["fp"] for r in rows), fn=sum(r["fn"] for r in rows),
                  episodes=len(rows), max_steps=max(r["steps"] for r in rows),
                  complete_proof_episodes=sum(r["issued_findings"] > 0 and r["complete_proofs"] == r["issued_findings"] for r in rows),
                  exact_episodes=sum(r["exact_findings"] for r in rows),
                  stages={key:statistics.mean(r[key] for r in rows) for key in ("any_error_correct", "type_set_correct", "affected_set_correct", "amount_currency_set_correct")})
    rng = random.Random(891713)
    groups = defaultdict(list)
    for row in rows:
        groups[row["family"]].append(row["f1"])
    families = list(groups)
    bootstrap = sorted(statistics.mean(v for name in rng.choices(families, k=len(families)) for v in groups[name]) for _ in range(300))
    result["finding_f1_family_bootstrap_95"] = [bootstrap[7], bootstrap[292]]
    return result


def run(root=681903275113, train_count=16, dev_count=8, test_count=32):
    started = time.perf_counter()
    splits = {name:list(cases(root, name, n)) for name, n in (("train", train_count), ("dev", dev_count), ("test", test_count))}
    training = {mode:[] for mode in MODES}
    for case in splits["train"]:
        for mode in MODES:
            session = Session()
            initial, _ = session.reset(case["seed"], case["config"], "evaluation")
            public = collect(initial, session.step, mode)
            # Label is obtained only after the policy's public feature extraction.
            label = session.episode["truth"][0]["type"] if session.episode["truth"] else "clean"
            training[mode].append((features(public), label))
    models = {(mode,name):fit(rows, forest=name=="forest") for mode,rows in training.items() for name in ("tree","forest")}
    candidates = [(mode,name,threshold) for mode in MODES for name in ("tree","forest") for threshold in (0, .6, .9)]
    development = []
    for choice in candidates:
        rows = [trial(case,"adaptive",choice,models) for case in splits["dev"]]
        development.append(dict(query_mode=choice[0], model=choice[1], threshold=choice[2],
                                mean_reward=statistics.mean(r["reward"] for r in rows),
                                mean_f1=statistics.mean(r["f1"] for r in rows),
                                mean_steps=statistics.mean(r["steps"] for r in rows)))
    winner = max(range(len(candidates)), key=lambda i:development[i]["mean_reward"])
    selected = candidates[winner]
    # The fixed combined model always collects all pages; adaptive selection is frozen here.
    combined = ("all_public", "forest", 0)
    results = {}
    raw = {}
    for name in ("random", "majority", "simple", "combined", "adaptive", "reconciliation"):
        choice = combined if name == "combined" else selected
        rows = [trial(case,name,choice,models) for case in splits["test"]]
        results[name], raw[name] = summarize(rows), rows
    return dict(name="SHORTCUT_HUNTER_2_ADAPTIVE", root=root,
                split_families={k:len({r["family"] for r in v}) for k,v in splits.items()},
                episodes={k:len(v) for k,v in splits.items()}, selected=development[winner],
                candidate_search=development, results=results, test_results=raw,
                split_configs=splits, seconds=time.perf_counter()-started,
                inference_boundary="initial public observation, step callable, frozen trained classifiers; no seed/truth/provenance argument",
                limitations=[
                    "Duplicate graph multiplicity with linked source document is legitimate structural financial evidence.",
                    "Other claim templates intentionally make nominal guesses; failed full findings do not invalidate binary indicators.",
                    "The adaptive search selects query mode, tree or forest and confidence abstention using dev terminal reward.",
                    "Grouped train/dev/test families are independent. No weight training of a language model.",
                    "Complete-proof episode rate requires at least one issued finding; clean exact answers are counted separately."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=681903275113)
    parser.add_argument("--output", type=Path, default=ROOT/"reports/ultimate-adaptive.json")
    args = parser.parse_args()
    report = run(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf8")
    print(json.dumps(dict(selected=report["selected"], results=report["results"], seconds=report["seconds"])))


if __name__ == "__main__":
    main()
