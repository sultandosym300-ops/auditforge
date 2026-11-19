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
        expected = convert(booked_source, pay['currency'], 'KZT', rate)
        if source != booked_source:
            full_settlement = convert(source, pay['currency'], 'KZT', rate)
            evidence = [row['row_id'], pay['doc_id'], inv['doc_id']]
            if fx:
                evidence.append(fx['row_id'])
            add('payment_allocation', [row['row_id']], full_settlement-expected, evidence)
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
        document_ids = [r['doc_id'] for table in ('invoices', 'payments') for r in books[table]]
        evidence_ids = document_ids + [r['row_id'] for table in ('ledger', 'fx') for r in books[table]]
        assert len(evidence_ids) == len(set(evidence_ids)), 'Ambiguous evidence ID'
        assert len(document_ids) == len(set(document_ids)), 'Duplicate document ID'
        assert len(invoices) == len(books['invoices']), 'Duplicate invoice ID'
        assert len(payments) == len(books['payments']), 'Duplicate payment ID'
        assert books['manifest']['records'] == len(books['ledger']), 'Incorrect record count'
        assert books['manifest']['documents'] == len(document_ids), 'Incorrect document count'
        for inv in books['invoices']:
            assert type(inv['total_minor']) is int
            assert sum(item['amount_minor'] for item in inv['line_items']) == inv['total_minor'], 'Invoice lines differ from total'
        for pay in books['payments']:
            assert type(pay['amount_minor']) is int
            assert sum(ref['allocated_minor'] for ref in pay['invoice_refs']) == pay['amount_minor'], 'Payment allocations differ from source amount'
            assert all(ref['invoice_id'] in invoices and ref['currency'] == pay['currency'] for ref in pay['invoice_refs'])
    # Validate the economic source-to-journal identities directly, independently
    # of the discrepancy detector used by the scripted policy.
    ledger = pristine['ledger']
    base = pristine['manifest']['base_currency']
    exponents = pristine['manifest']['currency_exponents']
    rates = {(r['date'], r['source_currency'], r['target_currency']): Decimal(r['rate']) for r in pristine['fx']}
    zone = datetime.fromisoformat(pristine['manifest']['period_start']).tzinfo
    for inv in pristine['invoices']:
        rows = [r for r in ledger if r['invoice_id'] == inv['invoice_id'] and r['payment_id'] is None]
        assert len(rows) == 2, 'Invoice must have exactly one balanced recognition pair'
        assert inv['currency'] == base, 'Unsupported invoice currency in generator history'
        expected = {'expense': (inv['total_minor'], 0), 'payable': (0, inv['total_minor'])}
        assert {r['account'] for r in rows} == set(expected)
        for row in rows:
            assert (row['debit_minor'], row['credit_minor']) == expected[row['account']]
            assert row['timestamp'] == inv['issued_at'] and row['entity_id'] == inv['entity_id'] and row['currency'] == base
    for pay in pristine['payments']:
        rows = [r for r in ledger if r['payment_id'] == pay['payment_id']]
        assert len(rows) == 2 * len(pay['invoice_refs']), 'Settlement journal pair missing'
        date = datetime.fromisoformat(pay['timestamp']).astimezone(zone).date().isoformat()
        rate = Decimal(1) if pay['currency'] == base else rates[date, pay['currency'], base]
        for ref in pay['invoice_refs']:
            pair = [r for r in rows if r['invoice_id'] == ref['invoice_id']]
            assert len(pair) == 2 and {r['account'] for r in pair} == {'payable', 'cash'}
            amount = int((Decimal(ref['allocated_minor']) * rate * Decimal(10) ** (exponents[base]-exponents[pay['currency']])).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
            for row in pair:
                assert row['allocation_source_minor'] == ref['allocated_minor']
                assert row['fx_date'] == date and Decimal(row['fx_rate']) == rate
                assert row['timestamp'] == pay['timestamp'] and row['currency'] == base
                assert (row['debit_minor'], row['credit_minor']) == ((amount, 0) if row['account'] == 'payable' else (0, amount)), 'Settlement differs from source conversion'
    assert not reconcile(pristine), 'Pristine history has unexplained discrepancies'
    # Replay every causal journal mutation, including both double-entry sides.
    replay = {r['row_id']: r for r in pristine['ledger']}
    assert len(episode['provenance']) == len(episode['truth'])
    assert {p['issue_id'] for p in episode['provenance']} == {t['issue_id'] for t in episode['truth']}
    for mutation in episode['provenance']:
        issue = next(t for t in episode['truth'] if t['issue_id'] == mutation['issue_id'])
        assert mutation['operation'] == issue['type']
        assert mutation['before'] != mutation['after']
        for row in mutation['before']:
            assert replay.get(row['row_id']) == row, 'Provenance before-state is not the prior journal'
        before_ids = {r['row_id'] for r in mutation['before']}
        for row in mutation['after']:
            assert row['row_id'] in before_ids or row['row_id'] not in replay, 'Unrecorded existing row overwritten'
            replay[row['row_id']] = row
    assert replay == {r['row_id']: r for r in public['ledger']}, 'Public journal differs from causal replay'
    for table in ('invoices', 'payments', 'fx'):
        identity = 'row_id' if table == 'fx' else 'doc_id'
        assert {r[identity]: r for r in pristine[table]} == {r[identity]: r for r in public[table]}, 'Unrecorded source-document change'
    recovered = reconcile(public)
    normalized = lambda f: (f['type'], tuple(sorted(f['affected_ids'])), f.get('claimed_amount_minor', f.get('expected_amount_minor')), f['currency'])
    assert sorted(map(normalized, recovered)) == sorted(map(normalized, episode['truth'])), 'Truth differs from independently recovered discrepancies'
    visible_ids = {r.get('row_id', r.get('doc_id')) for table in ('ledger','invoices','payments','fx') for r in public[table]}
    for issue in episode['truth']:
        assert all(set(s) <= visible_ids for s in issue['evidence_sets'])
        independent = next(f for f in recovered if normalized(f) == normalized(issue))
        assert issue['evidence_sets'], 'No admissible evidence set'
        assert all(set(independent['evidence_ids']) <= set(s) for s in issue['evidence_sets']), 'Evidence set does not substantiate discrepancy'
        causal = next(p for p in episode['provenance'] if p['issue_id'] == issue['issue_id'])
        # Independently measure affected debit postings across the causal change.
        # For period errors, only postings within the reporting window count.
        affected = set(issue['affected_ids'])
        start = datetime.fromisoformat(public['manifest']['period_start'])
        end = datetime.fromisoformat(public['manifest']['period_end'])
        before, after = (
            sum(row['debit_minor'] for row in causal[state]
                if row['row_id'] in affected and (
                    issue['type'] != 'accounting_period'
                    or start <= datetime.fromisoformat(row['timestamp']) < end
                ))
            for state in ('before', 'after')
        )
        assert abs(after - before) == issue['expected_amount_minor'], 'Truth differs from actual causal posting change'
        assert causal['before'] != causal['after']
        for row in causal['after']:
            assert row['row_id'] in visible_ids
    return True
