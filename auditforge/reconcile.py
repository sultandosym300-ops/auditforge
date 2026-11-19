"""Independent recovery from public records, with no provenance or truth input."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN


def reconcile(public):
    invoices = {x['invoice_id']: x for x in public['invoices']}
    payments = {x['payment_id']: x for x in public['payments']}
    rates = {(x['date'], x['source_currency'], x['target_currency']): x for x in public['fx']}
    exp = public['manifest']['currency_exponents']
    def convert(amount, source, target, rate):
        return int((Decimal(amount) * Decimal(rate) * Decimal(10)**(exp[target]-exp[source])).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    findings = []
    def add(kind, rows, amount, evidence):
        findings.append(dict(type=kind, affected_ids=sorted(rows), claimed_amount_minor=abs(amount), currency='KZT', evidence_ids=sorted(evidence), explanation='Source documents and accounting policy disagree with the recorded posting.'))
    expense = defaultdict(list)
    for row in public['ledger']:
        if row['account'] == 'expense' and row['payment_id'] is None:
            expense[row['invoice_id']].append(row)
    start = datetime.fromisoformat(public['manifest']['period_start'])
    end = datetime.fromisoformat(public['manifest']['period_end'])
    for iid, rows in expense.items():
        inv = invoices[iid]
        if len(rows) > 1:
            evidence = [inv['doc_id']] + [r['row_id'] for r in rows]
            if inv.get('related_credit_doc_id'):
                evidence.append(inv['related_credit_doc_id'])
            add('duplicate_invoice', [r['row_id'] for r in rows], sum(r['debit_minor'] for r in rows)-inv['total_minor'], evidence)
        for row in rows:
            if (start <= datetime.fromisoformat(row['timestamp']) < end) != (start <= datetime.fromisoformat(inv['issued_at']) < end):
                add('accounting_period', [row['row_id']], inv['total_minor'], [row['row_id'], inv['doc_id']])
    for row in public['ledger']:
        if row['account'] != 'payable' or row['payment_id'] is None:
            continue
        pay = payments[row['payment_id']]
        inv = invoices[row['invoice_id']]
        source = sum(ref['allocated_minor'] for ref in pay['invoice_refs'] if ref['invoice_id'] == row['invoice_id'])
        date = datetime.fromisoformat(pay['timestamp']).astimezone(start.tzinfo).date().isoformat()
        fx = rates.get((date, pay['currency'], 'KZT'))
        rate = fx['rate'] if fx else '1'
        booked_source = row['allocation_source_minor']
        if source != booked_source:
            add('payment_allocation', [row['row_id']], convert(source-booked_source, pay['currency'], 'KZT', rate), [row['row_id'], pay['doc_id'], inv['doc_id']])
        expected = convert(booked_source, pay['currency'], 'KZT', rate)
        if row['debit_minor'] != expected:
            add('fx_conversion', [row['row_id']], row['debit_minor']-expected, [row['row_id'], pay['doc_id'], fx['row_id']] if fx else [row['row_id'], pay['doc_id']])
    return sorted(findings, key=lambda f: (f['type'], f['affected_ids']))


def validate(episode):
    """Check pristine balances, public references, causal mutations and exact recoverability."""
    public, pristine = episode['public'], episode['pristine']
    for books in (pristine, public):
        invoices = {i['invoice_id'] for i in books['invoices']}
        payments = {p['payment_id'] for p in books['payments']}
        balances = defaultdict(int)
        ids = set()
        for row in books['ledger']:
            assert row['row_id'] not in ids
            ids.add(row['row_id'])
            assert row['invoice_id'] is None or row['invoice_id'] in invoices
            assert row['payment_id'] is None or row['payment_id'] in payments
            assert type(row['debit_minor']) is int and type(row['credit_minor']) is int
            balances[row['currency']] += row['debit_minor']-row['credit_minor']
        assert all(v == 0 for v in balances.values()), balances
    assert not reconcile(pristine), 'Pristine history has unexplained discrepancies'
    recovered = reconcile(public)
    normalized = lambda f: (f['type'], tuple(sorted(f['affected_ids'])), f.get('claimed_amount_minor', f.get('expected_amount_minor')), f['currency'])
    assert sorted(map(normalized, recovered)) == sorted(map(normalized, episode['truth'])), 'Truth differs from independently recovered discrepancies'
    visible_ids = {r.get('row_id', r.get('doc_id')) for table in ('ledger','invoices','payments','fx') for r in public[table]}
    for issue in episode['truth']:
        assert all(set(s) <= visible_ids for s in issue['evidence_sets'])
        causal = next(p for p in episode['provenance'] if p['issue_id'] == issue['issue_id'])
        assert causal['before'] != causal['after']
        for row in causal['after']:
            assert row['row_id'] in visible_ids
    return True
