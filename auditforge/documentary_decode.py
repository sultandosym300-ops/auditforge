"""Shared public-document financial decoder; no generator or evaluator imports."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN


def decode(public):
    """Deterministic documentary proof construction, independent of acquisition."""
    findings = []
    manifest = public['manifest']
    base = manifest['base_currency']
    start, end = (datetime.fromisoformat(manifest[k]) for k in ('period_start', 'period_end'))
    invoices = {r['invoice_id']: r for r in public.get('invoices', [])}
    payments = {r['payment_id']: r for r in public.get('payments', [])}
    rates = {(r['date'], r['source_currency'], r['target_currency']): r for r in public.get('fx', [])}
    groups = defaultdict(list)
    def add(kind, ids, amount, evidence):
        findings.append(dict(type=kind, affected_ids=sorted(ids),
                             claimed_amount_minor=abs(amount), currency=base,
                             evidence_ids=sorted(evidence), explanation='Checked against acquired source pages.'))
    for row in public['ledger']:
        if row['account'] == 'expense' and row['payment_id'] is None:
            groups[row['invoice_id']].append(row)
    for iid, rows in groups.items():
        invoice = invoices.get(iid)
        if invoice is None:
            continue
        if len(rows) > 1:
            add('duplicate_invoice', [r['row_id'] for r in rows],
                sum(r['debit_minor'] for r in rows)-invoice['total_minor'],
                [invoice['doc_id']] + [r['row_id'] for r in rows])
        issued_inside = start <= datetime.fromisoformat(invoice['issued_at']) < end
        for row in rows:
            booked_inside = start <= datetime.fromisoformat(row['timestamp']) < end
            if issued_inside != booked_inside:
                add('accounting_period', [row['row_id']], invoice['total_minor'],
                    [invoice['doc_id'], row['row_id']])
    exp = manifest['currency_exponents']
    for row in public['ledger']:
        if row['account'] != 'payable' or row['payment_id'] is None:
            continue
        payment = payments.get(row['payment_id'])
        if payment is None:
            continue
        currency = payment['currency']
        date = datetime.fromisoformat(payment['timestamp']).astimezone(start.tzinfo).date().isoformat()
        fx = rates.get((date, currency, base))
        if currency != base and fx is None:
            continue
        rate = fx['rate'] if fx else '1'
        def convert(value):
            return int((Decimal(value)*Decimal(rate)*Decimal(10)**(exp[base]-exp[currency])).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        source = sum(ref['allocated_minor'] for ref in payment['invoice_refs'] if ref['invoice_id'] == row['invoice_id'])
        booked = row['allocation_source_minor']
        expected = convert(booked)
        evidence = [row['row_id'], payment['doc_id']] + ([fx['row_id']] if fx else [])
        if source != booked:
            add('payment_allocation', [row['row_id']], convert(source)-expected, evidence)
        if row['debit_minor'] != expected:
            add('fx_conversion', [row['row_id']], row['debit_minor']-expected, evidence)
    return sorted(findings, key=lambda f: (f['type'], f['affected_ids']))
