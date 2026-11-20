"""Fixed univariate location probes and evidence ablations on separate seed namespaces."""
from collections import Counter
from datetime import datetime
from fractions import Fraction

from auditforge.generator import generate
from auditforge.matcher import evaluate, oracle
from scripts.jury_blind import trial_seed


def features(public):
    invoices = {r["invoice_id"]: r for r in public["invoices"]}
    payments = {r["payment_id"]: r for r in public["payments"]}
    links = Counter(ref["invoice_id"] for p in payments.values() for ref in p["invoice_refs"])
    totals = Counter(r["total_minor"] for r in invoices.values())
    for i, row in enumerate(public["ledger"]):
        invoice = invoices[row["invoice_id"]]
        payment = payments.get(row["payment_id"])
        issued = datetime.fromisoformat(invoice["issued_at"])
        delay = (datetime.fromisoformat(row["timestamp"])-issued).days
        yield row["row_id"], {
            "row_id_last_hex": row["row_id"][-1],
            "invoice_id_last_hex": invoice["invoice_id"][-1],
            "payment_id_last_hex": payment["payment_id"][-1] if payment else "none",
            "ledger_position_decile": 10*i//len(public["ledger"]),
            "linked_payment_count": links[row["invoice_id"]],
            "rounded_log_amount": len(str(invoice["total_minor"])),
            "repeated_amount": totals[invoice["total_minor"]] > 1,
            "payment_or_posting_delay_days": min(3,max(-1,delay)),
            "company_name": public["manifest"]["company"].split()[0],
            "description": invoice["line_items"][0]["description"],
            "invoice_field_order": ",".join(invoice),
            "ledger_field_order": ",".join(row),
            "null_field_count": sum(value is None for value in row.values()),
            "payment_currency": payment["currency"] if payment else "none",
        }


def cohort(seed, count):
    for index in range(count):
        config = dict(clean=index%5==0, interaction=index%3, shuffle=bool(index%2))
        episode = generate(trial_seed(seed, index), config)
        target = {rid for issue in episode["truth"] for rid in issue["affected_ids"]}
        for rid, values in features(episode["public"]):
            yield rid in target, values


def feature_audit(root, count=64):
    fit = {}
    for label, values in cohort(root, count):
        for key, value in values.items():
            fit.setdefault(key, Counter())[(value,label)] += 1
    selected = {}
    for key, table in fit.items():
        positives = sum(n for (v,label),n in table.items() if label)
        def f1(v):
            tp = table[v,True]
            return Fraction(2*tp, positives+tp+table[v,False])
        selected[key] = max(sorted({v for v,_ in table}), key=f1)
    counts = {k: Counter(tp=0,fp=0,fn=0) for k in selected}
    for label, values in cohort(root+1, count):
        for key, value in values.items():
            match = value == selected[key]
            if match or label:
                counts[key]["tp" if match and label else "fp" if match else "fn"] += 1
    return dict(training_root=root, holdout_root=root+1, companies_per_split=count,
                target="union of affected ledger row IDs across types; location only",
                results={k: dict(value=selected[k], **c, location_f1=2*c["tp"]/(2*c["tp"]+c["fp"]+c["fn"]))
                         for k,c in counts.items()})


def ablate(root, minimum=500):
    counts, index, failures = Counter(), 0, []
    while sum(counts.values()) < minimum:
        seed = trial_seed(root, index)
        ep = generate(seed, dict(interaction=index%3))
        index += 1
        answer = oracle(ep)
        for finding in answer["findings"]:
            evidence = finding["evidence_ids"]
            for omitted in [None] + evidence:
                trial = dict(finding, evidence_ids=[rid for rid in evidence if rid != omitted])
                observed = evaluate(answer["episode_id"], ep["truth"],
                                    dict(episode_id=answer["episode_id"], findings=[trial]), 0)["tp"]
                if observed != int(omitted is None):
                    failures.append(dict(seed=seed, finding=finding, omitted=omitted, actual=observed))
                if omitted:
                    counts[finding["type"]] += 1
    return dict(seed=root, omissions=dict(counts), companies=index, failures=failures)
