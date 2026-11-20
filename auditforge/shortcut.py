"""Holdout diagnostic for a fixed FX-rate fingerprint and refund metadata."""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN
import json
import random

from .env import Session
from .generator import GENERATOR_VERSION
from .policies import run_policy


def read_table(session, table):
    records, cursor = [], None
    while True:
        observation, _, terminated, truncated, _ = session.step(
            dict(tool='list_records', table=table, cursor=cursor, limit=50)
        )
        assert not terminated and not truncated
        page = observation['result']
        records.extend(page['records'])
        cursor = page['next_cursor']
        if cursor is None:
            return records


def fingerprint_policy(session, initial):
    """Guess the expected rate by subtracting seven; ignore the payment date."""
    ledger = read_table(session, 'ledger')
    payments = {p['payment_id']: p for p in read_table(session, 'payments')}
    rates = read_table(session, 'fx')
    base = initial['manifest']['base_currency']
    exponents = initial['manifest']['currency_exponents']
    by_value = {}
    for rate in rates:
        by_value.setdefault((rate['source_currency'], Decimal(rate['rate'])), []).append(rate)
    findings = []
    for row in ledger:
        if row['account'] != 'payable' or row['payment_id'] is None:
            continue
        payment = payments[row['payment_id']]
        currency = payment['currency']
        guessed_rate = Decimal(row['fx_rate']) - 7
        candidates = by_value.get((currency, guessed_rate), [])
        if not candidates:
            continue
        expected = Decimal(row['allocation_source_minor']) * guessed_rate * 10**(exponents[base]-exponents[currency])
        amount = abs(row['debit_minor'] - int(expected.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)))
        # Guess each plausible rate row rather than use the required date policy.
        # Group the set so one correct guess can count at most once.
        findings.append(dict(type='fx_conversion', affected_ids=[row['row_id']],
                             claimed_amount_minor=amount, currency=base,
                             evidence_ids=[row['row_id'], payment['doc_id'],
                                           *[candidate['row_id'] for candidate in candidates[:8]]],
                             explanation='Fixed rate offset fingerprint'))
    session.step(dict(tool='submit', findings=dict(
        episode_id=initial['manifest']['episode_id'], findings=findings[:30]
    )))


def run(root, count):
    rng = random.Random(root)
    fingerprint_f1 = reconciliation_f1 = 0.0
    refund_markers = Counter()
    for index in range(count):
        seed = rng.getrandbits(128)
        config = dict(counts={'fx_conversion': 1 + index % 3})
        session = Session()
        initial, _ = session.reset(seed, config, 'evaluation')
        fingerprint_policy(session, initial)
        fingerprint_f1 += session.report['f1']
        initial, _ = session.reset(seed, config, 'evaluation')
        run_policy(session, initial, 'reconciliation')
        reconciliation_f1 += session.report['f1']
        # Public marker predictions are collected before inspecting evaluator truth.
        session.reset(seed, dict(interaction=2, clean=index % 2 == 0), 'evaluation')
        guesses = {invoice['invoice_id'] for invoice in read_table(session, 'invoices')
                   if invoice.get('related_credit_doc_id')}
        public_rows = {row['row_id']: row['invoice_id'] for row in read_table(session, 'ledger')}
        actual = {public_rows[row] for issue in session.episode['truth']
                  if issue['type'] == 'duplicate_invoice' for row in issue['affected_ids']}
        refund_markers.update(tp=len(guesses & actual), fp=len(guesses - actual), fn=len(actual - guesses))
    return dict(version=GENERATOR_VERSION, root_seed=root, episodes_per_cohort=count,
                fx_fingerprint_mean_f1=fingerprint_f1/count,
                reconciliation_mean_f1=reconciliation_f1/count,
                refund_marker=dict(refund_markers))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=648911247)
    parser.add_argument('--count', type=int, default=80)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000:
        parser.error('--count must be 1..10000')
    print(json.dumps(run(args.seed, args.count), sort_keys=True))


if __name__ == '__main__':
    main()
