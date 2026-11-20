"""Public-interface evidence collection and held-out generator fingerprint probes."""
import argparse
from collections import Counter
import hashlib
import json
from unittest.mock import patch

from scripts.jury_batch import batch_company

from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.generator import TYPES
from auditforge.policies import run_policy


def trial_seed(root, index):
    material = f'jury-blind-1:{root}:{index}'.encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big')


def shortcut_counts(public, truth):
    """Predict issue location without consulting source-document amounts or dates."""
    end = public['manifest']['period_end']
    expenses = [row for row in public['ledger'] if row['account'] == 'expense']
    guesses = {
        'close_timestamp': {row['row_id'] for row in expenses if row['timestamp'] == end},
        'first_invoice': {public['invoices'][0]['invoice_id']},
        'round_invoice_amount': {inv['invoice_id'] for inv in public['invoices']
                                 if inv['total_minor'] == 500000},
        'refund_link': {inv['invoice_id'] for inv in public['invoices']
                        if inv.get('related_credit_doc_id')},
    }
    periods = {row for issue in truth if issue['type'] == 'accounting_period'
               for row in issue['affected_ids']}
    duplicates = {row for issue in truth if issue['type'] == 'duplicate_invoice'
                  for row in issue['affected_ids']}
    actual_invoices = {r['invoice_id'] for r in expenses if r['row_id'] in duplicates}
    result = {}
    for name, predicted in guesses.items():
        actual = periods if name == 'close_timestamp' else actual_invoices
        result[name] = Counter(tp=len(actual & predicted), fp=len(predicted - actual),
                               fn=len(actual - predicted))
    return result


def probes(root, count):
    from auditforge.generator import generate

    totals = {}
    for index in range(count):
        episode = generate(trial_seed(root, index), dict(shuffle=False, counts={
            'duplicate_invoice': 1, 'accounting_period': 1}))
        for name, counts in shortcut_counts(episode['public'], episode['truth']).items():
            totals.setdefault(name, Counter()).update(counts)
    return {name: dict(values, location_f1=2*values['tp'] /
                        (2*values['tp'] + values['fp'] + values['fn']))
            for name, values in totals.items()}


class PublicActions:
    """Only the action callable crosses into the policy; record evidence as delivered."""
    def __init__(self, step):
        self._step = step
        self.visible_ids = set()
        self.steps = 0
        self.claims = []
        self.errors = []

    def step(self, action):
        self.steps += 1
        if action['tool'] == 'submit':
            self.claims = action['findings']['findings']
            for claim in self.claims:
                if not set(claim['evidence_ids'] + claim['affected_ids']) <= self.visible_ids:
                    self.errors.append('Referenced evidence not observed before submit')
        result = self._step(action)
        observation = result[0]
        if 'error' in observation:
            self.errors.append(observation['error'])
        if action['tool'] == 'list_records':
            for row in observation.get('result', {}).get('records', []):
                self.visible_ids.add(row.get('row_id', row.get('doc_id')))
        return result


def collect(session, initial, seed, config):
    access = PublicActions(session.step)
    final = run_policy(access, initial)
    financial = audit_episode(session.episode)
    manifest = initial['manifest']
    return dict(seed=seed, config=config, episode_id=manifest['episode_id'],
                records=manifest['records'], documents=manifest['documents'],
                issues=financial['issue_count'], observed_evidence=len(access.visible_ids),
                steps=access.steps, f1=session.report['f1'],
                errors=access.errors + financial['errors'],
                passed=bool(final and final[2] and not final[3] and final[1] == 0
                            and session.report['f1'] == 1 and financial['valid']
                            and not access.errors and access.steps <= 100))


def run(root, count=30):
    if type(count) is not int or count < 1:
        raise ValueError('count must be a positive integer')
    rows = []
    for i in range(count):
        seed = trial_seed(root, i)
        config = dict(invoices=(42, 55, 80, 84, 200)[i % 5],
                      timezone=('-12:00', '+05:45', '+14:00', '-03:30')[i % 4],
                      period_month=('2028-02', '2099-12', '2000-01')[(i // 2) % 3],
                      boundary_payments=True, clean=i % 6 == 0, interaction=i % 3,
                      shuffle=bool(i % 2), counts={kind: (3 if i % 4 == 0 else 1)
                                                   for kind in TYPES})
        session = Session()
        initial, _ = session.reset(seed, config, 'evaluation')
        rows.append(collect(session, initial, seed, config))
    dense = []
    for size in (10, 100):
        for erroneous in (False, True):
            seed = trial_seed(root, count + len(dense))
            company = batch_company(seed, size, erroneous)
            session = Session()
            with patch('auditforge.env.generate', return_value=company):
                initial, _ = session.reset(seed, {}, 'evaluation')
            dense.append(collect(session, initial, seed, dict(batch_payments=size,
                                                               cutoff_error=erroneous)))
    return dict(seed=root, count=count, blind=rows, passed=sum(r['passed'] for r in rows),
                dense=dense, probes=probes(root+1, count),
                amounts=allocation_probe(root+2, count))


def allocation_probe(root, count, generate_company=None):
    """Give the guesser the affected row; measure source-amount inference alone."""
    if generate_company is None:
        from auditforge.generator import generate as generate_company
    correct = total = 0
    for i in range(count):
        episode = generate_company(trial_seed(root, i), {'counts': {'payment_allocation': 3}})
        for change in episode['provenance']:
            booked = change['after'][0]['allocation_source_minor']
            actual = change['before'][0]['allocation_source_minor']
            correct += actual in (2*booked, 2*booked+1)
            total += 1
    return dict(guessed=correct, total=total, accuracy=correct/total)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--count', type=int, default=30)
    args = parser.parse_args()
    output = run(args.seed, args.count)
    print(json.dumps(output, sort_keys=True))
    raise SystemExit(output['passed'] != args.count or not all(r['passed'] for r in output['dense']))

