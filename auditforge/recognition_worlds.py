"""Counterfactual period recognition with a private, balanced assignment of dates."""
import hashlib
import json
import random
from datetime import datetime, timedelta

from . import __version__


def fingerprint(seed, config, purpose):
    data = json.dumps([seed, config, purpose], sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(('recognition-v1:' + data).encode()).digest()


def recurrence_terms(seed, config, n, closing_indices):
    """A company-specific recurring charge shared by several genuine obligations."""
    rng = random.Random(fingerprint(seed, config, 'contract terms'))
    others = [i for i in range(n) if i not in closing_indices]
    indices = set(closing_indices) | set(rng.sample(others, max(6, n // 6) - len(closing_indices)))
    return indices, rng.randrange(10_000, 2_000_000)


def build_world(episode, seed, config, world, nominal):
    """Transpose two equal-valued obligations while preserving financial period aggregates."""
    if world == 'blind':
        world = fingerprint(seed, config, 'blind selection')[0] % 4
    source_bit, book_bit = divmod(world, 2)
    rng = random.Random(fingerprint(seed, config, 'history'))
    public = episode['public']
    start = datetime.fromisoformat(public['manifest']['period_start'])
    end = datetime.fromisoformat(public['manifest']['period_end'])
    dates = sorted({datetime.fromisoformat(inv['issued_at']) for inv in public['invoices']})
    inside = [d for d in dates if start <= d < end]
    payments = {}
    for payment in public['payments']:
        when = datetime.fromisoformat(payment['timestamp'])
        for ref in payment['invoice_refs']:
            iid = ref['invoice_id']
            payments[iid] = min(payments.get(iid, when), when)

    recurring = [inv for inv in public['invoices'] if inv['total_minor'] == nominal]
    if rng.choice((True, False)):
        inside_date, outside_date = rng.choice(inside[-3:]), end
    else:
        inside_date = rng.choice(inside[:3])
        outside_date = rng.choice([d for d in dates if d < start])
    latest = max(inside_date, outside_date)
    eligible = [inv for inv in recurring if payments[inv['invoice_id']] >= latest]
    if len(eligible) < 2:
        # Some legitimate settlements precede the closing batch. Use the opening
        # cut instead so that moving issuance never creates an unexplained advance.
        inside_date, outside_date = start, rng.choice([d for d in dates if d < start])
        latest = start
        eligible = [inv for inv in recurring if payments[inv['invoice_id']] >= latest]

    obligations = rng.sample(eligible, 2)
    dates_by_bit = (inside_date.isoformat(), outside_date.isoformat())
    eid = 'ep-' + fingerprint(seed, config, ['episode', world]).hex()[:16]
    for books in (episode['pristine'], public):
        books['manifest'].update(episode_id=eid, generator_version=__version__)

    for index, invoice in enumerate(obligations):
        iid = invoice['invoice_id']
        issued, booked = dates_by_bit[source_bit ^ index], dates_by_bit[book_bit ^ index]
        due = (datetime.fromisoformat(issued) + timedelta(days=30)).isoformat()
        for books in (episode['pristine'], public):
            doc = next(inv for inv in books['invoices'] if inv['invoice_id'] == iid)
            doc.update(issued_at=issued, due_at=due)
            for row in books['ledger']:
                if row['invoice_id'] == iid and row['payment_id'] is None:
                    row['timestamp'] = issued

        if issued == booked:
            continue
        pair = [r for r in public['ledger'] if r['invoice_id'] == iid and r['payment_id'] is None]
        before = [r.copy() for r in pair]
        for row in pair:
            row['timestamp'] = booked
        expense = next(r for r in pair if r['account'] == 'expense')
        amount = expense['debit_minor']
        in_period_before = amount if start <= datetime.fromisoformat(issued) < end else 0
        in_period_after = amount if start <= datetime.fromisoformat(booked) < end else 0
        issue_id = 'issue-' + fingerprint(seed, config, ['issue', world, index]).hex()[:15]
        episode['truth'].append(dict(issue_id=issue_id, type='accounting_period',
                                     affected_ids=[expense['row_id']],
                                     expected_amount_minor=abs(in_period_after-in_period_before),
                                     currency=expense['currency'], tolerance_minor=0,
                                     evidence_sets=[sorted([invoice['doc_id'], expense['row_id']])]))
        episode['provenance'].append(dict(issue_id=issue_id, operation='accounting_period',
                                          before=before, after=[r.copy() for r in pair]))
    return episode
