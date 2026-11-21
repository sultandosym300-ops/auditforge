"""Experimental terminal-reward finding acceptance, never a production default.

Source gates are frozen v2 parameters. Four acceptance heads learn financial
predicates over both discrepancies and clean near-misses. Arithmetic, evidence
construction and top-four-per-type proposal ranking remain deterministic.
This does not learn arithmetic or free-form financial reasoning.
"""
import copy
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
import math
import random

from .efficient_training import EfficientTrainer, investigate
from .training import episode_seed, sigmoid

KINDS = ('duplicate_invoice', 'accounting_period', 'payment_allocation', 'fx_conversion')
FEATURES = ('bias', 'nonzero_public_discrepancy', 'relative_public_discrepancy')


def hypotheses(public):
    """Public-only candidate proposals, deliberately including clean hypotheses."""
    manifest = public['manifest']
    start, end = (datetime.fromisoformat(manifest[k]) for k in ('period_start', 'period_end'))
    invoices = {r['invoice_id']: r for r in public.get('invoices', [])}
    payments = {r['payment_id']: r for r in public.get('payments', [])}
    rates = {(r['date'], r['source_currency'], r['target_currency']): r for r in public.get('fx', [])}
    groups = defaultdict(list)
    pool = defaultdict(list)
    base = manifest['base_currency']
    def add(kind, ids, delta, evidence, scale):
        finding = dict(type=kind, affected_ids=sorted(ids), claimed_amount_minor=abs(delta),
                       currency=base, evidence_ids=sorted(evidence),
                       explanation='Experimental learned acceptance of public financial hypothesis.')
        x = [1., float(delta != 0), min(1., abs(delta)/max(1, abs(scale)))]
        pool[kind].append((finding, x))
    for row in public['ledger']:
        if row['account'] == 'expense' and row['payment_id'] is None:
            groups[row['invoice_id']].append(row)
    for iid, rows in groups.items():
        inv = invoices.get(iid)
        if inv is None:
            continue
        add('duplicate_invoice', [r['row_id'] for r in rows],
            sum(r['debit_minor'] for r in rows)-inv['total_minor'],
            [inv['doc_id']]+[r['row_id'] for r in rows], inv['total_minor'])
        issued = start <= datetime.fromisoformat(inv['issued_at']) < end
        for row in rows:
            booked = start <= datetime.fromisoformat(row['timestamp']) < end
            add('accounting_period', [row['row_id']], inv['total_minor'] if issued != booked else 0,
                [inv['doc_id'], row['row_id']], inv['total_minor'])
    exponents = manifest['currency_exponents']
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
            return int((Decimal(value)*Decimal(rate)*Decimal(10)**(exponents[base]-exponents[currency])).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        source = sum(r['allocated_minor'] for r in payment['invoice_refs'] if r['invoice_id'] == row['invoice_id'])
        expected = convert(row['allocation_source_minor'])
        evidence = [row['row_id'], payment['doc_id']]+([fx['row_id']] if fx else [])
        add('payment_allocation', [row['row_id']], convert(source)-expected, evidence, expected)
        add('fx_conversion', [row['row_id']], row['debit_minor']-expected, evidence, expected)
    # Ranking is a disclosed deterministic proposal heuristic, not a learned result.
    return [(KINDS.index(kind), finding, x) for kind in KINDS
            for finding, x in sorted(pool[kind], key=lambda item: -item[1][2])[:4]]


class HypothesisTrainer:
    """REINFORCE acceptance on fixed acquisition; excluded from v2 dispatch."""
    def __init__(self, seed=314159, scenario='mixed', acquisition_weights=None, learning_rate=.02):
        self.source = EfficientTrainer(seed, scenario)
        if not isinstance(acquisition_weights, (list, tuple)) or len(acquisition_weights) != 21 or any(type(w) not in (int, float) or not math.isfinite(w) or abs(w)>1000 for w in acquisition_weights):
            raise ValueError('Frozen finite v2 acquisition parameters required')
        if type(learning_rate) not in (int, float) or not math.isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError('Invalid acceptance learning rate')
        self.source.weights = list(acquisition_weights)
        self.weights = [0.] * (len(KINDS)*len(FEATURES))
        self.seed, self.learning_rate = seed, learning_rate
        self.episodes, self.baseline = 0, 0.

    def run(self, session, initial, rng=None, ablation=None):
        if ablation not in (None, 'zero_features'):
            raise ValueError('Unknown experimental ablation')
        public = dict(manifest=initial['manifest'], ledger=[])
        decisions = []
        def step(action):
            if action['tool'] == 'submit':
                accepted = []
                for head, finding, x in hypotheses(public):
                    if ablation == 'zero_features':
                        x = [1., 0., 0.]
                    p = sigmoid(sum(w*v for w, v in zip(self.weights[head*3:head*3+3], x)))
                    selected = rng.random() < p if rng else p >= .5
                    decisions.append((head, x, float(selected), p))
                    if selected:
                        accepted.append(finding)
                action = dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=accepted))
            result = session.step(action)
            if action['tool'] == 'list_records' and 'error' not in result[0]:
                public.setdefault(action['table'], []).extend(result[0]['result']['records'])
            return result
        terminal, _ = investigate(step, initial, self.source.weights)
        return terminal, decisions

    def train_episode(self, control=None):
        from .env import Session
        if control not in (None, 'frozen', 'independent_reward'):
            raise ValueError('Unknown experimental control')
        session = Session()
        initial, _ = session.reset(episode_seed(self.seed, 'hypothesis-train', self.episodes), self.source.config(self.episodes), 'train')
        terminal, decisions = self.run(session, initial, random.Random(episode_seed(self.seed, 'hypothesis-actions', self.episodes)))
        reward = terminal[1]
        if control == 'independent_reward':
            reward = random.Random(episode_seed(self.seed, 'independent-reward', self.episodes)).uniform(-1, 1)
        advantage = reward-self.baseline
        if control != 'frozen':
            for head, x, action, p in decisions:
                for j, value in enumerate(x):
                    self.weights[head*3+j] += self.learning_rate*advantage*(action-p)*value
        self.baseline = .9*self.baseline+.1*reward
        self.episodes += 1
        return dict(episode=self.episodes, **{k: session.report[k] for k in ('f1', 'precision', 'recall', 'reward')}, steps=session.steps)

    def checkpoint(self):
        return copy.deepcopy(dict(format='auditforge-experimental-hypothesis-policy', version=1,
            status='experimental-not-production', seed=self.seed, scenario=self.source.scenario,
            features=FEATURES, kinds=KINDS, acquisition_weights=self.source.weights,
            weights=self.weights, episodes=self.episodes, learning_rate=self.learning_rate, baseline=self.baseline))

    @classmethod
    def from_checkpoint(cls, data):
        if (not isinstance(data, dict) or data.get('format') != 'auditforge-experimental-hypothesis-policy'
                or type(data.get('version')) is not int or data['version'] != 1
                or data.get('status') != 'experimental-not-production'
                or not isinstance(data.get('features'), (list, tuple))
                or tuple(data['features']) != FEATURES
                or not isinstance(data.get('kinds'), (list, tuple))
                or tuple(data['kinds']) != KINDS):
            raise ValueError('Unsupported experimental checkpoint')
        result = cls(data.get('seed'), data.get('scenario'), data.get('acquisition_weights'), data.get('learning_rate'))
        weights, episodes, baseline = data.get('weights'), data.get('episodes'), data.get('baseline')
        if (not isinstance(weights, list) or len(weights) != 12
                or any(type(w) not in (int,float) or not math.isfinite(w) or abs(w)>1000 for w in weights)
                or type(episodes) is not int or not 0<=episodes<=100000
                or type(baseline) not in (int,float) or not math.isfinite(baseline) or not -1<=baseline<=1):
            raise ValueError('Invalid experimental parameters')
        result.weights, result.episodes, result.baseline = list(weights), episodes, baseline
        return result
