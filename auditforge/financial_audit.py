"""Evaluator-only financial cross-check using exact rational arithmetic.

No matcher, reconciliation-policy detector, Decimal conversion helper or validation
function is used. Generation is imported only by the optional mass-audit runner.
"""
import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
from pathlib import Path

ISSUE_TYPES = ('duplicate_invoice', 'payment_allocation', 'fx_conversion', 'accounting_period')


def round_half_even(value):
    """Nearest integer, with exact ties rounded to an even integer, signed."""
    value = Fraction(value)
    quotient, remainder = divmod(abs(value.numerator), value.denominator)
    if 2 * remainder > value.denominator or (2 * remainder == value.denominator and quotient % 2):
        quotient += 1
    return -quotient if value < 0 else quotient


def converted_minor(amount, source, target, rate, exponents):
    scale = exponents[target] - exponents[source]
    multiplier = Fraction(10 ** scale) if scale >= 0 else Fraction(1, 10 ** -scale)
    return round_half_even(Fraction(amount) * Fraction(rate) * multiplier)


class FinancialAuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FinancialAuditError(message)


def timestamp(value):
    require(isinstance(value, str), 'Timestamp must be a string')
    parsed = datetime.fromisoformat(value)
    require(parsed.utcoffset() is not None, 'Timestamp lacks UTC offset')
    return parsed


def indexed(rows, key):
    require(all(isinstance(row.get(key), str) and row[key] for row in rows), 'Missing record identity: '+key)
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), 'Duplicate record identity: '+key)
    return result


def _inspect_books(books, pristine=False):
    manifest = books['manifest']
    base, exponents = manifest['base_currency'], manifest['currency_exponents']
    require(base == 'KZT', 'Current generator contract requires KZT invoice books')
    require(all(type(n) is int and 0 <= n <= 6 for n in exponents.values()), 'Invalid currency exponents')
    require(manifest['rounding'] == books['policy']['rounding'] == 'ROUND_HALF_EVEN', 'Unsupported rounding policy')
    require(books['policy']['fx_date'] == 'payment local date in manifest timezone', 'Unsupported FX date policy')
    require(books['policy']['invoice_recognition'] == 'issued_at', 'Unsupported recognition policy')
    start, end = timestamp(manifest['period_start']), timestamp(manifest['period_end'])
    require(start < end, 'Invalid reporting window')
    # Parsing the declared offset separately prevents a valid datetime hiding a
    # malformed or inconsistent manifest timezone.
    declared = timestamp('2000-01-01T00:00:00'+manifest['timezone'])
    require(declared.utcoffset() == start.utcoffset() == end.utcoffset(), 'Manifest timezone differs from reporting window')
    invoices = indexed(books['invoices'], 'invoice_id')
    payments = indexed(books['payments'], 'payment_id')
    ledger = indexed(books['ledger'], 'row_id')
    documents = indexed(books['invoices']+books['payments'], 'doc_id')
    evidence = list(documents) + list(ledger) + [f['row_id'] for f in books['fx']]
    require(len(set(evidence)) == len(evidence), 'Ambiguous evidence identity')
    require(manifest['records'] == len(ledger) and manifest['documents'] == len(documents), 'Incorrect manifest counts')
    rates = {}
    for row in books['fx']:
        require(isinstance(row['rate'], str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', row['rate']), 'FX rate is not a decimal string')
        key = row['date'], row['source_currency'], row['target_currency']
        require(key not in rates and Fraction(row['rate']) > 0, 'Duplicate or nonpositive FX rate')
        require(row['source_currency'] in exponents and row['target_currency'] in exponents, 'Unknown FX currency')
        rates[key] = row
    for inv in invoices.values():
        require(inv['currency'] == base and type(inv['total_minor']) is int and inv['total_minor'] > 0, 'Invalid invoice amount/currency')
        require(timestamp(inv['due_at']) >= timestamp(inv['issued_at']), 'Invoice due before issuance')
        require(inv['line_items'], 'Empty invoice lines')
        for item in inv['line_items']:
            require(all(type(item[k]) is int for k in ('quantity', 'unit_minor', 'amount_minor')), 'Invoice line has noninteger values')
            require(item['quantity'] > 0 and item['quantity'] * item['unit_minor'] == item['amount_minor'], 'Invoice line quantity/unit/amount disagree')
        require(sum(x['amount_minor'] for x in inv['line_items']) == inv['total_minor'], 'Invoice line sum differs from total')
        if inv.get('related_credit_doc_id'):
            credit = documents.get(inv['related_credit_doc_id'])
            require(credit is not None and credit.get('kind') == 'refund' and credit.get('amount_minor', 0) < 0, 'Related credit is not a refund document')
            require(any(ref['invoice_id'] == inv['invoice_id'] for ref in credit['invoice_refs']), 'Related refund belongs to a different obligation')
    for pay in payments.values():
        timestamp(pay['timestamp'])
        require(type(pay['amount_minor']) is int and pay['currency'] in exponents, 'Invalid payment amount/currency')
        require(pay['invoice_refs'] and sum(ref['allocated_minor'] for ref in pay['invoice_refs']) == pay['amount_minor'], 'Payment amount differs from allocations')
        require((pay['kind'] == 'refund') == (pay['amount_minor'] < 0), 'Refund/settlement sign disagrees')
        for ref in pay['invoice_refs']:
            require(ref['invoice_id'] in invoices and type(ref['allocated_minor']) is int and ref['currency'] == pay['currency'], 'Invalid payment invoice reference')
    balance = Counter()
    recognition, settlements = defaultdict(list), defaultdict(list)
    for row in ledger.values():
        timestamp(row['timestamp'])
        require(type(row['debit_minor']) is int and type(row['credit_minor']) is int, 'Noninteger ledger amount')
        require(row['currency'] == base and row['invoice_id'] in invoices, 'Unsupported ledger currency/invoice')
        require(row['entity_id'] == invoices[row['invoice_id']]['entity_id'], 'Posting entity differs from source invoice')
        require(not (row['debit_minor'] and row['credit_minor']), 'Posting has both debit and credit')
        balance[row['currency']] += row['debit_minor'] - row['credit_minor']
        if row['payment_id'] is None:
            recognition[row['invoice_id']].append(row)
        else:
            require(row['payment_id'] in payments, 'Posting references nonexistent payment')
            settlements[row['payment_id'], row['invoice_id']].append(row)
    require(all(n == 0 for n in balance.values()), 'Journal does not balance by currency')
    findings = []
    def finding(kind, rows, amount, ids):
        findings.append(dict(type=kind, affected_ids=sorted(rows), expected_amount_minor=abs(amount), currency=base, evidence_ids=sorted(ids)))
    for iid, inv in invoices.items():
        rows = recognition[iid]
        expenses = [r for r in rows if r['account'] == 'expense']
        liabilities = [r for r in rows if r['account'] == 'payable']
        require(expenses and len(expenses) == len(liabilities) and len(rows) == 2*len(expenses), 'Recognition pair missing or has unknown account')
        require(not pristine or len(expenses) == 1, 'Pristine recognition duplicated')
        expense_states = Counter((r['timestamp'], r['debit_minor'], r['credit_minor']) for r in expenses)
        liability_states = Counter((r['timestamp'], r['credit_minor'], r['debit_minor']) for r in liabilities)
        require(expense_states == liability_states, 'Recognition mirror disagrees')
        require(all((r['debit_minor'], r['credit_minor']) == (inv['total_minor'], 0) for r in expenses), 'Invoice recognition amount disagrees')
        if len(expenses) > 1:
            ids = [inv['doc_id']] + [r['row_id'] for r in expenses]
            finding('duplicate_invoice', [r['row_id'] for r in expenses], (len(expenses)-1)*inv['total_minor'], ids)
        for row in expenses:
            recorded = start <= timestamp(row['timestamp']) < end
            issued = start <= timestamp(inv['issued_at']) < end
            if recorded != issued:
                finding('accounting_period', [row['row_id']], inv['total_minor'], [inv['doc_id'], row['row_id']])
            require(not pristine or row['timestamp'] == inv['issued_at'], 'Pristine recognition timestamp disagrees')
    expected_settlements = set()
    for pid, pay in payments.items():
        for ref in pay['invoice_refs']:
            key = pid, ref['invoice_id']
            require(key not in expected_settlements, 'Repeated invoice reference in payment')
            expected_settlements.add(key)
            pair = settlements[key]
            require(len(pair) == 2 and {r['account'] for r in pair} == {'payable', 'cash'}, 'Settlement mirror missing')
            payable = next(r for r in pair if r['account'] == 'payable')
            cash = next(r for r in pair if r['account'] == 'cash')
            ignored = {'row_id', 'account', 'debit_minor', 'credit_minor'}
            require({k:v for k,v in payable.items() if k not in ignored} == {k:v for k,v in cash.items() if k not in ignored}, 'Settlement mirror metadata disagrees')
            require((payable['debit_minor'], payable['credit_minor']) == (cash['credit_minor'], cash['debit_minor']) and payable['credit_minor'] == 0, 'Settlement mirror amounts disagree')
            require(payable['timestamp'] == pay['timestamp'], 'Settlement timestamp differs from source payment')
            booked = payable['allocation_source_minor']
            require(type(booked) is int, 'Noninteger allocation source amount')
            date = timestamp(pay['timestamp']).astimezone(start.tzinfo).date().isoformat()
            fx = None if pay['currency'] == base else rates.get((date, pay['currency'], base))
            require(pay['currency'] == base or fx is not None, 'Required FX source unavailable')
            rate = fx['rate'] if fx else '1'
            expected_booked = converted_minor(booked, pay['currency'], base, rate, exponents)
            full = converted_minor(ref['allocated_minor'], pay['currency'], base, rate, exponents)
            if booked != ref['allocated_minor']:
                ids = [payable['row_id'], pay['doc_id']] + ([fx['row_id']] if fx else [])
                finding('payment_allocation', [payable['row_id']], full-expected_booked, ids)
            if payable['debit_minor'] != expected_booked:
                ids = [payable['row_id'], pay['doc_id']] + ([fx['row_id']] if fx else [])
                finding('fx_conversion', [payable['row_id']], payable['debit_minor']-expected_booked, ids)
            # The recorded conversion must agree with its own declared rate;
            # this distinguishes an injected wrong rate from corrupt metadata.
            require(payable['fx_date'] == date, 'Recorded FX date differs from source payment date')
            require(converted_minor(booked, pay['currency'], base, payable['fx_rate'], exponents) == payable['debit_minor'], 'Posting disagrees with its declared FX calculation')
            if pristine:
                require(booked == ref['allocated_minor'] and Fraction(payable['fx_rate']) == Fraction(rate), 'Pristine settlement differs from source')
    require(set(settlements) == expected_settlements, 'Orphan settlement pair')
    require(not pristine or not findings, 'Pristine books contain discrepancies')
    return findings, set(evidence)


def _signature(issue):
    return issue['type'], tuple(sorted(issue['affected_ids'])), issue['expected_amount_minor'], issue['currency']


def audit_episode(episode):
    """Return bounded evaluator diagnostics; do not expose these to policies."""
    findings = []
    try:
        _inspect_books(episode['pristine'], pristine=True)
        findings, visible = _inspect_books(episode['public'])
        truth = episode['truth']
        require(Counter(map(_signature, findings)) == Counter(map(_signature, truth)), 'Truth differs from rational public reconstruction')
        truth_by_id = indexed(truth, 'issue_id')
        recovered = {_signature(f): f for f in findings}
        for issue in truth:
            require(type(issue['expected_amount_minor']) is int and issue['expected_amount_minor'] >= 0, 'Invalid truth amount')
            require(issue['evidence_sets'], 'Truth has no evidence set')
            minimum = set(recovered[_signature(issue)]['evidence_ids'])
            require(any(set(ids) == minimum for ids in issue['evidence_sets']),
                    'Every admissible proof requires unrelated records')
            for evidence in issue['evidence_sets']:
                require(isinstance(evidence, list) and len(evidence) <= 10 and len(evidence) == len(set(evidence)), 'Malformed evidence set')
                require(set(evidence) <= visible and minimum <= set(evidence), 'Truth evidence does not independently establish the discrepancy')
        mutations = indexed(episode['provenance'], 'issue_id')
        require(set(mutations) == set(truth_by_id), 'Truth/provenance issue identities disagree')
        state = {r['row_id']: r for r in episode['pristine']['ledger']}
        start = timestamp(episode['public']['manifest']['period_start'])
        end = timestamp(episode['public']['manifest']['period_end'])
        permitted = {'payment_allocation': {'allocation_source_minor', 'debit_minor', 'credit_minor'}, 'fx_conversion': {'fx_rate', 'debit_minor', 'credit_minor'}, 'accounting_period': {'timestamp'}}
        for mutation in episode['provenance']:
            issue = truth_by_id[mutation['issue_id']]
            kind = issue['type']
            require(kind in ISSUE_TYPES and mutation['operation'] == kind, 'Causal operation differs from truth type')
            before, after = indexed(mutation['before'], 'row_id'), indexed(mutation['after'], 'row_id')
            require(before != after and all(state.get(k) == r for k,r in before.items()), 'Causal before-state disagrees')
            require(set(before) <= set(after), 'Causal mutation drops existing journal rows')
            for key, row in after.items():
                if key in before:
                    changed = {k for k in set(row) | set(before[key]) if row.get(k) != before[key].get(k)}
                    require(not changed if kind == 'duplicate_invoice' else changed <= permitted[kind], 'Causal operation changes unrelated fields')
                else:
                    require(kind == 'duplicate_invoice' and key not in state, 'Causal operation inserts unexplained row')
                state[key] = row
            affected = set(issue['affected_ids'])
            def amount(rows):
                return sum(r['debit_minor'] for r in rows.values() if r['row_id'] in affected and (kind != 'accounting_period' or start <= timestamp(r['timestamp']) < end))
            require(abs(amount(after)-amount(before)) == issue['expected_amount_minor'], 'Truth differs from causal base-currency amount')
        require(state == indexed(episode['public']['ledger'], 'row_id'), 'Final journal differs from causal replay')
        for table, identity in (('invoices', 'doc_id'), ('payments', 'doc_id'), ('fx', 'row_id')):
            require(indexed(episode['public'][table], identity) == indexed(episode['pristine'][table], identity), 'Unexplained source document mutation')
        return dict(valid=True, errors=[], findings=findings, issue_count=len(truth))
    except (FinancialAuditError, KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        return dict(valid=False, errors=[str(error)[:300]], findings=findings, issue_count=len(episode.get('truth', [])))


def run_mass_audit(count=1000, seed=2026112001):
    """Fresh namespaced seeds, mixed held-out parameters, stable report content."""
    from .generator import generate, GENERATOR_VERSION
    require(type(count) is int and 1 <= count <= 100000, 'count must be 1..100000')
    require(type(seed) is int, 'seed must be an integer')
    failures, checked = [], []
    rng = random.Random(seed)
    digest = hashlib.sha256()
    by_type, interactions = Counter(), Counter()
    clean_count = 0
    for index in range(count):
        episode_seed = int.from_bytes(hashlib.sha256(('financial-independent-v1:'+str(seed)+':'+str(index)).encode()).digest()[:8], 'big')
        config = dict(invoices=(40, 41, 50, 80, 120, 200)[index % 6],
                      clean=index % 5 == 0, interaction=index % 3,
                      timezone=('+05:00', '-03:30', '+05:45', '+00:00', '-12:00', '+14:00')[(index // 6) % 6],
                      period_month=('2026-10', '2024-02', '2025-02', '2031-12', '2000-01', '2099-11')[(index // 36) % 6],
                      boundary_payments=bool((index // 3) % 2),
                      shuffle=bool(index % 2), counts={kind:rng.randrange(4) for kind in ISSUE_TYPES})
        # Ensure interaction cohorts really contain the linked mechanisms.
        if config['interaction'] and not config['clean']:
            for kind in ('duplicate_invoice', 'accounting_period'):
                config['counts'][kind] = max(1, config['counts'][kind])
            if config['interaction'] == 1:
                for kind in ('payment_allocation', 'fx_conversion'):
                    config['counts'][kind] = max(1, config['counts'][kind])
        episode = generate(episode_seed, config)
        result = audit_episode(episode)
        record = dict(index=index, seed=episode_seed, config=config, episode_id=episode['public']['manifest']['episode_id'], valid=result['valid'], issues=result['issue_count'])
        checked.append(record)
        digest.update(json.dumps(episode, sort_keys=True, separators=(',', ':')).encode())
        if not result['valid']:
            failures.append(dict(**record, errors=result['errors']))
        by_type.update(t['type'] for t in episode['truth'])
        clean_count += not episode['truth']
        interactions[config['interaction']] += 1
    return dict(auditor_version='1.0', arithmetic='fractions.Fraction with integer ROUND_HALF_EVEN', generator_version=GENERATOR_VERSION,
                master_seed=seed, checked=count, passed=count-len(failures), failed=len(failures),
                clean_episodes=clean_count, interactions=dict(interactions), issues_by_type=dict(by_type),
                episode_digest_sha256=digest.hexdigest(), failures=failures, episodes=checked,
                scope='Independent local financial integrity check; no official jury score or difficulty claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=2026112001)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = run_mass_audit(args.count, args.seed)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'episodes'}, sort_keys=True))
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
