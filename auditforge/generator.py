"""Versioned, deterministic synthetic double-entry books; no external dependencies."""
import copy
import hashlib
import json
import random
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN

TYPES = ('duplicate_invoice', 'payment_allocation', 'fx_conversion', 'accounting_period')
EXPONENTS = {'KZT': 2, 'USD': 2, 'EUR': 2, 'JPY': 0}
GENERATOR_VERSION = '1.1.4'


def converted(amount, source, target, rate):
    return int((Decimal(amount) * Decimal(rate) * Decimal(10) ** (EXPONENTS[target] - EXPONENTS[source])).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def generate(seed, config=None):
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    if config is not None and not isinstance(config, dict):
        raise ValueError('config must be an object')
    config = dict(config or {})
    allowed = {'clean', 'interaction', 'counts', 'invoices', 'timezone', 'shuffle',
               'period_month', 'boundary_payments'}
    if set(config) - allowed:
        raise ValueError('Unsupported configuration')
    if any(key in config and type(config[key]) is not bool for key in ('clean', 'shuffle', 'boundary_payments')):
        raise ValueError('clean, shuffle and boundary_payments must be booleans')
    period_month = config.get('period_month', '2026-10')
    if not isinstance(period_month, str) or not re.fullmatch(r'20[0-9]{2}-(?:0[1-9]|1[0-2])', period_month):
        raise ValueError('period_month must be YYYY-MM between 2000 and 2099')
    if 'timezone' in config:
        value = config['timezone']
        if not isinstance(value, str) or not re.fullmatch(r'[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
            raise ValueError('timezone must be an ISO-8601 UTC offset')
    n = config.get('invoices', 50)
    counts = config.get('counts', {t: 1 for t in TYPES})
    if type(n) is not int or not 40 <= n <= 200:
        raise ValueError('invoices must be 40..200')
    if not isinstance(counts, dict) or set(counts) - set(TYPES) or any(type(v) is not int or v < 0 or v > 3 for v in counts.values()):
        raise ValueError('Each issue count must be 0..3')
    interaction = config.get('interaction', 0)
    if type(interaction) is not int or interaction not in (0, 1, 2):
        raise ValueError('interaction must be 0, 1 or 2')
    rng = random.Random(str(seed) + json.dumps(config, sort_keys=True))
    eid = 'ep-' + hashlib.sha256((str(seed) + json.dumps(config, sort_keys=True)).encode()).hexdigest()[:16]
    tz = config.get('timezone', rng.choice(['+05:00', '+06:00', '-04:00']))
    zone = timezone(timedelta(hours=int(tz[:3]), minutes=int(tz[0] + tz[4:])))
    year, month = map(int, period_month.split('-'))
    start = datetime(year, month, 1, tzinfo=zone)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=zone)
    invoice_days = min(29, (end - start).days)
    def ident(prefix):
        return prefix + '-' + format(rng.getrandbits(60), '015x')
    fx = []
    rates = {}
    for d in range(33):
        date = (start + timedelta(days=d - 1)).date().isoformat()
        for currency, base in [('USD', 490), ('EUR', 530), ('JPY', 3)]:
            rate = str(Decimal(base) + Decimal(d % 7) / 10)
            rates[date, currency] = rate
            fx.append(dict(row_id=ident('fx'), date=date, source_currency=currency, target_currency='KZT', rate=rate))
    invoices, payments, ledger = [], [], []
    def entry(account, amount, debit, stamp, inv, payment=None, **extra):
        row = dict(row_id=ident('row'), timestamp=stamp, account=account, debit_minor=amount if debit else 0, credit_minor=0 if debit else amount, currency='KZT', entity_id=inv['entity_id'], invoice_id=inv['invoice_id'], payment_id=payment)
        row.update(extra)
        ledger.append(row)
        return row
    # Whether an invoice becomes a finding is independent of public file order.
    assignment = random.Random('assignment:' + str(seed) + json.dumps(config, sort_keys=True))
    eligibility_stride = {0: 12, 1: 4, 2: 9}[interaction]
    interaction_index = assignment.choice(range(0, n, eligibility_stride))
    # Other genuine split foreign settlements share the same cutoff timestamps.
    close_batch = set(assignment.sample([i for i in range(0, n, 4) if i != interaction_index], 2))
    if interaction == 1:
        close_batch.add(interaction_index)
    boundary_indices = assignment.sample([i for i in range(n) if i != interaction_index], 6)
    boundary_stamps = dict(zip(boundary_indices, (
        end, end + timedelta(hours=6), end + timedelta(hours=12),
        start - timedelta(hours=1), start - timedelta(hours=6), start - timedelta(hours=12),
    )))
    for i in range(n):
        stamp = (start + timedelta(days=rng.randrange(invoice_days), hours=rng.randrange(24))).isoformat()
        if i in boundary_stamps:
            stamp = boundary_stamps[i].isoformat()
        total = rng.randrange(10_000, 2_000_000) if i % 6 else 500_000
        inv = dict(doc_id=ident('doc'), invoice_id=ident('inv'), entity_id=ident('entity'), issued_at=stamp, due_at=(datetime.fromisoformat(stamp) + timedelta(days=30)).isoformat(), currency='KZT', total_minor=total, line_items=[dict(description=rng.choice(['Logistics', 'Equipment lease', 'Consulting', 'Cloud infrastructure']), quantity=1, unit_minor=total, amount_minor=total, source_ref=ident('contract'))])
        invoices.append(inv)
        entry('expense', total, True, stamp, inv)
        entry('payable', total, False, stamp, inv)
        # Split settlements, legitimate repeat amounts and documented refunds are clean distractors.
        portions = [total // 2, total - total // 2] if i % 4 == 0 else [total]
        if i % 9 == 0:
            portions += [-total // 10]
        for part in portions:
            foreign = i % 3 == 0
            currency = rng.choice(['USD', 'EUR', 'JPY']) if foreign else 'KZT'
            paid_at = stamp
            if config.get('boundary_payments', False) and i < 2:
                paid_at = (end + timedelta(seconds=2*i - 1)).isoformat()
            if i in close_batch:
                paid_at = (end - timedelta(seconds=1)).isoformat()
                currency = 'USD'
            date = datetime.fromisoformat(paid_at).astimezone(zone).date().isoformat()
            rate = rates[date, currency] if currency != 'KZT' else '1'
            source = converted(part, 'KZT', currency, str(Decimal(1) / Decimal(rate)))
            amount = converted(source, currency, 'KZT', rate)
            pay = dict(doc_id=ident('doc'), payment_id=ident('pay'), timestamp=paid_at, currency=currency, amount_minor=source, invoice_refs=[dict(invoice_id=inv['invoice_id'], allocated_minor=source, currency=currency)], kind='refund' if source < 0 else 'settlement')
            payments.append(pay)
            if pay['kind'] == 'refund':
                inv['related_credit_doc_id'] = pay['doc_id']
            extra = dict(allocation_source_minor=source, fx_rate=rate, fx_date=date)
            entry('payable', amount, True, paid_at, inv, pay['payment_id'], **extra)
            entry('cash', amount, False, paid_at, inv, pay['payment_id'], **extra)
    public = dict(manifest=dict(schema_version='1.0', generator_version=GENERATOR_VERSION, config_version='1.1', episode_id=eid, company=rng.choice(['Aral Logistics', 'Saryarka Systems', 'Turan Supply', 'Nomad Materials']) + ' ' + str(rng.randrange(100, 999)), base_currency='KZT', period_start=start.isoformat(), period_end=end.isoformat(), timezone=tz, currency_exponents=dict(EXPONENTS), rounding='ROUND_HALF_EVEN', records=0, documents=len(invoices)+len(payments)), policy=dict(fx_date='payment local date in manifest timezone', period='[period_start, period_end)', invoice_recognition='issued_at', rounding='ROUND_HALF_EVEN', amount_tolerance_minor=0, allocation='invoice_refs amounts in payment currency; refunds signed'), ledger=ledger, invoices=invoices, payments=payments, fx=fx)
    pristine = copy.deepcopy(public)
    truth, provenance = [], []
    def change(kind, rows, before, evidence, amount, causal_rows=None):
        issue = dict(issue_id=ident('issue'), type=kind, affected_ids=sorted(r['row_id'] for r in rows), expected_amount_minor=abs(amount), currency='KZT', evidence_sets=[sorted(evidence)], tolerance_minor=0)
        truth.append(issue)
        provenance.append(dict(issue_id=issue['issue_id'], operation=kind, before=before, after=copy.deepcopy(rows if causal_rows is None else causal_rows)))
    active = {} if config.get('clean', False) else dict(counts)
    shared = {1: {'payment_allocation', 'fx_conversion', 'accounting_period'},
              2: {'duplicate_invoice', 'accounting_period'}}.get(interaction, set())
    reserved = {interaction_index} if shared else set()
    targets = {}
    # Reserve foreign obligations first, then sample ordinary obligations without replacement.
    for kind in ('fx_conversion', 'duplicate_invoice', 'payment_allocation', 'accounting_period'):
        size = active.get(kind, 0)
        indices = [interaction_index] if kind in shared and size else []
        choices = [i for i in range(n) if i not in reserved
                   and (kind != 'fx_conversion' or i % 3 == 0)]
        indices.extend(assignment.sample(choices, size-len(indices)))
        targets[kind] = indices
        reserved.update(indices)
    for kind in TYPES:
        for index in targets[kind]:
            inv = invoices[index]
            invoice_rows = [r for r in ledger if r['invoice_id'] == inv['invoice_id'] and r['payment_id'] is None and r['account'] == 'expense']
            pay = next(p for p in payments if p['invoice_refs'][0]['invoice_id'] == inv['invoice_id'] and p['amount_minor'] > 0)
            rows = [r for r in ledger if r['payment_id'] == pay['payment_id']]
            if kind == 'duplicate_invoice':
                original = invoice_rows[0]
                pair = [r for r in ledger if r['invoice_id'] == inv['invoice_id'] and r['payment_id'] is None]
                clones = copy.deepcopy(pair)
                for r in clones:
                    r['row_id'] = ident('row')
                insert_at = 2 * assignment.randrange(1 + len(ledger) // 2)
                ledger[insert_at:insert_at] = clones
                evidence = [inv['doc_id'], original['row_id'], clones[0]['row_id']]
                change(kind, [original, clones[0]], copy.deepcopy(pair), evidence, inv['total_minor'], pair+clones)
            elif kind == 'payment_allocation':
                before = copy.deepcopy(rows)
                original_source = rows[0]['allocation_source_minor']
                # Missing allocations and different partial settlements must be inferred
                # from the source payment, not a fixed inverse multiplier.
                source = assignment.choice((0, original_source // 2,
                                            assignment.randrange(1, original_source)))
                if interaction == 1 and index == interaction_index:
                    # A later interacting FX change needs a nonzero monetary effect.
                    source = max(2, source)
                for r in rows:
                    r['allocation_source_minor'] = source
                    field = 'debit_minor' if r['account'] == 'payable' else 'credit_minor'
                    r[field] = converted(source, pay['currency'], 'KZT', r['fx_rate'])
                # Measure the actual journal change after rounding both postings.
                delta = before[0]['debit_minor'] - rows[0]['debit_minor']
                evidence = [pay['doc_id'], rows[0]['row_id']]
                if pay['currency'] != 'KZT':
                    fxrow = next(f for f in fx if f['date'] == before[0]['fx_date'] and f['source_currency'] == pay['currency'])
                    evidence.append(fxrow['row_id'])
                change(kind, [rows[0]], before, evidence, delta, rows)
            elif kind == 'fx_conversion':
                before = copy.deepcopy(rows)
                true_rate = rates[rows[0]['fx_date'], pay['currency']]
                source = rows[0]['allocation_source_minor']
                expected = converted(source, pay['currency'], 'KZT', true_rate)
                # Use a real quote from elsewhere in the schedule. The source date
                # determines correctness, so membership in the catalog is insufficient.
                candidates = sorted({
                    rate for (_, currency), rate in rates.items()
                    if currency == pay['currency']
                    and converted(source, currency, 'KZT', rate) != expected
                })
                wrong = rng.choice(candidates)
                actual = converted(source, pay['currency'], 'KZT', wrong)
                for r in rows:
                    r['fx_rate'] = wrong
                    r['debit_minor' if r['account'] == 'payable' else 'credit_minor'] = actual
                fxrow = next(f for f in fx if f['date'] == rows[0]['fx_date'] and f['source_currency'] == pay['currency'])
                change(kind, [rows[0]], before, [pay['doc_id'], rows[0]['row_id'], fxrow['row_id']], actual-expected, rows)
            else:
                r = invoice_rows[0]
                paired = next(x for x in ledger if x['invoice_id'] == inv['invoice_id'] and x['payment_id'] is None and x['account'] == 'payable')
                before = copy.deepcopy([r, paired])
                issued_inside = start <= datetime.fromisoformat(inv['issued_at']) < end
                if issued_inside:
                    recorded = assignment.choice(tuple(boundary_stamps.values()))
                else:
                    recorded = start + timedelta(days=assignment.randrange(invoice_days),
                                                 hours=assignment.randrange(24))
                r['timestamp'] = paired['timestamp'] = recorded.isoformat()
                change(kind, [r], before, [inv['doc_id'], r['row_id']], inv['total_minor'], [r, paired])
    for table in ('ledger', 'invoices', 'payments', 'fx'):
        if config.get('shuffle', True):
            rng.shuffle(public[table])
    public['manifest']['records'] = len(ledger)
    pristine['manifest']['records'] = len(pristine['ledger'])
    return dict(public=public, truth=truth, provenance=provenance, pristine=pristine)
