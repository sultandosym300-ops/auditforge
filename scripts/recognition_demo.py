"""A jury demonstration of reporting-period recognition through public tools."""
import argparse
from datetime import datetime
from decimal import Decimal
import sys

from auditforge.env import AuditEnv


def read_pages(step, table):
    cursor = None
    rows = []
    while True:
        observation, reward, terminated, truncated, info = step(
            dict(tool="list_records", table=table, cursor=cursor, limit=50)
        )
        if reward or info or terminated or truncated or "error" in observation:
            raise ValueError(f"Unexpected {table} page response")
        page = observation["result"]
        rows.extend(page["records"])
        cursor = page["next_cursor"]
        if cursor is None:
            return rows


def inspect_period(initial, step):
    """Period-only policy. Its inputs are the initial observation and public actions."""
    manifest, policy = initial["manifest"], initial["policy"]
    if policy["invoice_recognition"] != "issued_at" or policy["period"] != "[period_start, period_end)":
        raise ValueError("Unsupported recognition convention")
    start, end = (datetime.fromisoformat(manifest[k]) for k in ("period_start", "period_end"))
    invoices = {r["invoice_id"]: r for r in read_pages(step, "invoices")}
    ledger = read_pages(step, "ledger")
    findings = []
    for row in ledger:
        if row["account"] != "expense" or row["payment_id"] is not None:
            continue
        invoice = invoices[row["invoice_id"]]
        issued = datetime.fromisoformat(invoice["issued_at"])
        posted = datetime.fromisoformat(row["timestamp"])
        if (start <= issued < end) != (start <= posted < end):
            findings.append(dict(type="accounting_period", affected_ids=[row["row_id"]],
                                 claimed_amount_minor=invoice["total_minor"], currency=invoice["currency"],
                                 evidence_ids=[invoice["doc_id"], row["row_id"]],
                                 explanation="Invoice and recognition posting fall in different reporting periods."))
    return ledger, invoices, findings


def trial(seed, world, omit_document=False):
    """The trusted presenter selects an episode and reads its final score after submit."""
    with AuditEnv("evaluation") as env:
        initial, _ = env.reset(seed, {"recognition_world": world})
        ledger, invoices, findings = inspect_period(initial, env.step)
        if omit_document:
            findings = [dict(f, evidence_ids=list(f["affected_ids"])) if i == 0 else f
                        for i, f in enumerate(findings)]
        payload = dict(episode_id=initial["manifest"]["episode_id"], findings=findings)
        status, reward, terminated, truncated, _ = env.step(dict(tool="submit", findings=payload))
        if not terminated or truncated or reward:
            raise ValueError("Episode did not terminate with the evaluation contract")
        return dict(manifest=initial["manifest"], ledger=ledger, invoices=invoices, findings=findings,
                    steps=100-status["steps_remaining"], score=env.evaluator_report())


def demonstrate(seed):
    clean = trial(seed, 0)
    dirty = trial(seed, 2)
    partial = trial(seed, 2, omit_document=True)
    if clean["ledger"] != dirty["ledger"]:
        raise ValueError("The two journals differ")
    findings = dirty["findings"]
    if clean["findings"] or len(findings) != 2 or clean["score"]["f1"] != 1 or dirty["score"]["f1"] != 1:
        raise ValueError("A blind investigation did not match the expected outcome")
    if partial["score"]["tp"] != 1 or partial["score"]["fn"] != 1 or partial["steps"] != dirty["steps"]:
        raise ValueError("The missing document control did not isolate the effect of evidence")

    manifest = dirty["manifest"]
    start, end = (datetime.fromisoformat(manifest[k]) for k in ("period_start", "period_end"))
    rows = {row["row_id"]: row for row in dirty["ledger"]}
    currency = manifest["base_currency"]
    exponent = manifest["currency_exponents"][currency]

    def money(minor):
        amount = Decimal(minor).scaleb(-exponent)
        digits = f"{amount:,.{exponent}f}".replace(",", " ").replace(".", ",")
        return f"{digits} {currency}"

    recognized = sum(row["debit_minor"] for row in rows.values()
                     if row["account"] == "expense" and start <= datetime.fromisoformat(row["timestamp"]) < end)
    print(f"Период с {start.isoformat()} до {end.isoformat()}. Момент закрытия входит в следующий период.")
    print(f"Все {len(rows)} проводок совпадают, включая их порядок. В обеих книгах за период признано {money(recognized)}.")
    signed = []
    for i, finding in enumerate(findings, start=1):
        row = rows[finding["affected_ids"][0]]
        iid = row["invoice_id"]
        a, b = clean["invoices"][iid], dirty["invoices"][iid]
        posted_inside = start <= datetime.fromisoformat(row["timestamp"]) < end
        sign = 1 if posted_inside else -1
        signed.append(sign * finding["claimed_amount_minor"])
        direction = "завышение" if sign == 1 else "занижение"
        print(f"\nОбязательство {i}. Счёт {b['doc_id']}, проводка {row['row_id']}.")
        print(f"  Время проводки в обеих книгах — {row['timestamp']}.")
        print(f"  Счёт А выставлен {a['issued_at']}. В Б счёт выставлен {b['issued_at']}.")
        print(f"  В книге Б {direction} расхода по этому обязательству на {money(finding['claimed_amount_minor'])}.")
    if sum(signed) != 0:
        raise ValueError("The opposite period differences should net to zero")
    print(f"\nВ А ошибок периода {len(clean['findings'])}, F1 = {clean['score']['f1']:g}, шагов {clean['steps']}.")
    print(f"В Б ошибок типа accounting_period {len(findings)}, F1 = {dirty['score']['f1']:g}, шагов {dirty['steps']}.")
    print(f"Отклонение общей суммы расходов — {money(sum(signed))}. По каждой из двух операций поступил отдельный вывод.")
    print(f"Контроль доказательств. Удалили ID счёта из первого вывода при тех же {partial['steps']} шагах. "
          f"Подтверждено находок {partial['score']['tp']} из 2, F1 = {partial['score']['f1']:g}.")
    return clean, dirty, partial


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=34815267)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    demonstrate(parser.parse_args().seed)
