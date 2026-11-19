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


def converted(amount, source, target, rate):
    return int((Decimal(amount) * Decimal(rate) * Decimal(10) ** (EXPONENTS[target] - EXPONENTS[source])).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def generate(seed, config=None):
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    if config is not None and not isinstance(config, dict):
        raise ValueError('config must be an object')
    config = dict(config or {})
    allowed = {'clean', 'interaction', 'counts', 'invoices', 'timezone', 'shuffle'}
    if set(config) - allowed:
        raise ValueError('Unsupported configuration')
    if any(key in config and type(config[key]) is not bool for key in ('clean', 'shuffle')):
        raise ValueError('clean and shuffle must be booleans')
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
    start = datetime(2026, 10, 1, tzinfo=zone)
    end = datetime(2026, 11, 1, tzinfo=zone)
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
    for i in range(n):
        stamp = (start + timedelta(days=rng.randrange(29), hours=rng.randrange(24))).isoformat()
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
            if i == 0 and interaction == 1:
                paid_at = (end - timedelta(seconds=1)).isoformat()
                currency = 'USD'
            date = datetime.fromisoformat(paid_at).astimezone(zone).date().isoformat()
            rate = rates[date, currency] if currency != 'KZT' else '1'
            source = converted(part, 'KZT', currency, str(Decimal(1) / Decimal(rate)))
            amount = converted(source, currency, 'KZT', rate)
            pay = dict(doc_id=ident('doc'), payment_id=ident('pay'), timestamp=paid_at, currency=currency, amount_minor=source, invoice_refs=[dict(invoice_id=inv['invoice_id'], allocated_minor=source, currency=currency)], kind='refund' if source < 0 else 'settlement')
            payments.append(pay)
            extra = dict(allocation_source_minor=source, fx_rate=rate, fx_date=date)
            entry('payable', amount, True, paid_at, inv, pay['payment_id'], **extra)
            entry('cash', amount, False, paid_at, inv, pay['payment_id'], **extra)
    public = dict(manifest=dict(schema_version='1.0', generator_version='1.1.0', config_version='1.1', episode_id=eid, company=rng.choice(['Aral Logistics', 'Saryarka Systems', 'Turan Supply', 'Nomad Materials']) + ' ' + str(rng.randrange(100, 999)), base_currency='KZT', period_start=start.isoformat(), period_end=end.isoformat(), timezone=tz, currency_exponents=dict(EXPONENTS), rounding='ROUND_HALF_EVEN', records=0, documents=len(invoices)+len(payments)), policy=dict(fx_date='payment local date in manifest timezone', period='[period_start, period_end)', invoice_recognition='issued_at', rounding='ROUND_HALF_EVEN', amount_tolerance_minor=0, allocation='invoice_refs amounts in payment currency; refunds signed'), ledger=ledger, invoices=invoices, payments=payments, fx=fx)
    pristine = copy.deepcopy(public)
    truth, provenance = [], []
    def change(kind, rows, before, evidence, amount, causal_rows=None):
        issue = dict(issue_id=ident('issue'), type=kind, affected_ids=sorted(r['row_id'] for r in rows), expected_amount_minor=abs(amount), currency='KZT', evidence_sets=[sorted(evidence)], tolerance_minor=0)
        truth.append(issue)
        provenance.append(dict(issue_id=issue['issue_id'], operation=kind, before=before, after=copy.deepcopy(rows if causal_rows is None else causal_rows)))
    active = {} if config.get('clean', False) else dict(counts)
    for k, kind in enumerate(TYPES):
        for j in range(active.get(kind, 0)):
            index = k * 4 + j
            if interaction == 1 and kind in ('payment_allocation', 'fx_conversion', 'accounting_period') and j == 0:
                index = 0
            if interaction == 2 and kind in ('duplicate_invoice', 'accounting_period') and j == 0:
                index = 0
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
                ledger.extend(clones)
                evidence = [inv['doc_id'], original['row_id'], clones[0]['row_id']]
                if interaction == 2 and index == 0:
                    refund = next(p for p in payments if p['invoice_refs'][0]['invoice_id'] == inv['invoice_id'] and p['kind'] == 'refund')
                    # The source document explicitly relates its credit adjustment to this obligation.
                    inv['related_credit_doc_id'] = refund['doc_id']
                    pristine['invoices'][index]['related_credit_doc_id'] = refund['doc_id']
                    evidence.append(refund['doc_id'])
                change(kind, [original, clones[0]], copy.deepcopy(pair), evidence, inv['total_minor'], pair+clones)
            elif kind == 'payment_allocation':
                before = copy.deepcopy(rows)
                original_source = rows[0]['allocation_source_minor']
                source = original_source // 2
                delta = converted(original_source - source, pay['currency'], 'KZT', rows[0]['fx_rate'])
                for r in rows:
                    r['allocation_source_minor'] = source
                    field = 'debit_minor' if r['account'] == 'payable' else 'credit_minor'
                    r[field] = converted(source, pay['currency'], 'KZT', r['fx_rate'])
                change(kind, [rows[0]], before, [pay['doc_id'], inv['doc_id'], rows[0]['row_id']], delta, rows)
            elif kind == 'fx_conversion':
                # Choose foreign settlement; native settlements have no FX error to inject.
                if pay['currency'] == 'KZT':
                    index = 3 * (k * 4 + j) % n
                    inv = invoices[index]
                    pay = next(p for p in payments if p['invoice_refs'][0]['invoice_id'] == inv['invoice_id'] and p['amount_minor'] > 0)
                    rows = [r for r in ledger if r['payment_id'] == pay['payment_id']]
                before = copy.deepcopy(rows)
                true_rate = rates[rows[0]['fx_date'], pay['currency']]
                wrong = str(Decimal(true_rate) + 7)
                source = rows[0]['allocation_source_minor']
                expected = converted(source, pay['currency'], 'KZT', true_rate)
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
                r['timestamp'] = end.isoformat()
                paired['timestamp'] = end.isoformat()
                change(kind, [r], before, [inv['doc_id'], r['row_id']], inv['total_minor'], [r, paired])
    for table in ('ledger', 'invoices', 'payments', 'fx'):
        if config.get('shuffle', True):
            rng.shuffle(public[table])
    public['manifest']['records'] = len(ledger)
    pristine['manifest']['records'] = len(pristine['ledger'])
    return dict(public=public, truth=truth, provenance=provenance, pristine=pristine)
