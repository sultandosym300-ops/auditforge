"""Learned acquisition of source-table pages, with explicit financial decoding.

Three logistic gates choose whether to acquire invoices, payments and rates. The
decoder never sees an unrequested table. Terminal reward alone updates gates.
The previous document-query policy remains available through checkpoint dispatch.
"""
import copy
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
import json
import math
import random
import time

from .generator import GENERATOR_VERSION
from .training import Trainer, episode_seed, sigmoid

FEATURES = ('bias', 'duplicate_group', 'outside_recognition', 'boundary_recognition',
            'foreign_settlement', 'allocation_disagreement', 'remaining_budget')
TABLES = ('invoices', 'payments', 'fx')
SCENARIOS = ('period', 'duplicate', 'fx', 'allocation', 'mixed', 'clean', 'recognition')
INITIAL_WEIGHTS = [-1., 0., 0., 0., 0., 0., 0.] * 3


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


def investigate(step, initial, weights, rng=None, log=None, threshold=.5):
    remaining = initial['steps_remaining']
    public = dict(manifest=initial['manifest'], policy=initial['policy'], ledger=[])
    decisions = []
    def act(action):
        nonlocal remaining
        result = step(action)
        remaining = result[0]['steps_remaining']
        if log is not None:
            log.append(dict(episode_id=initial['manifest']['episode_id'], step=len(log)+1,
                            action=action, observation=result[0], reward=result[1],
                            terminated=result[2], truncated=result[3]))
        return result
    def acquire(table):
        public[table] = []
        cursor = None
        while remaining > 1:
            result = act(dict(tool='list_records', table=table, cursor=cursor, limit=50))
            if result[2] or result[3] or 'error' in result[0]:
                return result
            page = result[0]['result']
            public[table].extend(page['records'])
            cursor = page['next_cursor']
            if cursor is None:
                return None
        return None
    ended = acquire('ledger')
    if ended is not None:
        return ended, decisions
    start, end = (datetime.fromisoformat(initial['manifest'][k]) for k in ('period_start', 'period_end'))
    groups = defaultdict(list)
    for row in public['ledger']:
        if row['account'] == 'expense' and row['payment_id'] is None:
            groups[row['invoice_id']].append(row)
    recognition = [r for rows in groups.values() for r in rows]
    for gate, table in enumerate(TABLES):
        if remaining <= 1:
            break
        foreign = any(r.get('fx_rate', '1') != '1' for r in public['ledger'] if r['payment_id'] is not None)
        if table == 'fx' and ('payments' not in public or not foreign):
            continue
        payments = {r['payment_id']: r for r in public.get('payments', [])}
        disagreement = any(
            sum(ref['allocated_minor'] for ref in payments[r['payment_id']]['invoice_refs'] if ref['invoice_id'] == r['invoice_id']) != r['allocation_source_minor']
            for r in public['ledger'] if r['account'] == 'payable' and r['payment_id'] in payments)
        x = [1., float(any(len(rows)>1 for rows in groups.values())),
             float(any(not start <= datetime.fromisoformat(r['timestamp']) < end for r in recognition)),
             float(any(min(abs((datetime.fromisoformat(r['timestamp'])-start).total_seconds()), abs((datetime.fromisoformat(r['timestamp'])-end).total_seconds())) < 86400 for r in recognition)),
             float(foreign), float(disagreement), remaining/100]
        probability = sigmoid(sum(w*v for w,v in zip(weights[gate*len(FEATURES):(gate+1)*len(FEATURES)], x)))
        selected = rng.random() < probability if rng is not None else probability >= threshold
        decisions.append((gate, x, float(selected), probability))
        if selected:
            ended = acquire(table)
            if ended is not None:
                return ended, decisions
    return act(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=decode(public)[:30]))), decisions


class EfficientTrainer:
    def __init__(self, seed=20261121, scenario='period', learning_rate=.1):
        if type(seed) is not int or scenario not in SCENARIOS or type(learning_rate) not in (int,float) or not math.isfinite(learning_rate) or not 0 < learning_rate <= 2:
            raise ValueError('Invalid training configuration')
        self.seed, self.scenario, self.learning_rate = seed, scenario, learning_rate
        self.weights = list(INITIAL_WEIGHTS)
        self.episodes = self.optimizer_steps = 0
        self.baseline = 0.
        self.history = []

    def config(self, index):
        if self.scenario == 'recognition':
            return dict(recognition_world=index%4, invoices=40)
        config = dict(invoices=40, timezone=('+05:45','-03:30','+14:00')[index%3],
                      period_month=('2028-02','2031-12')[index%2], boundary_payments=True)
        if self.scenario in ('mixed','clean'):
            config.update(clean=self.scenario == 'clean' or index%5 == 0, interaction=index%3)
        else:
            kind = dict(period='accounting_period', duplicate='duplicate_invoice', fx='fx_conversion', allocation='payment_allocation')[self.scenario]
            config.update(clean=index%5 == 0, counts={kind:2})
        return config

    def train_episode(self):
        from .env import Session
        session = Session()
        initial,_ = session.reset(episode_seed(self.seed,'efficient-train',self.episodes), self.config(self.episodes),'train')
        started = time.perf_counter()
        terminal, decisions = investigate(session.step, initial, self.weights,
                                           random.Random(episode_seed(self.seed,'efficient-actions',self.episodes)))
        advantage = terminal[1]-self.baseline
        for gate,x,action,p in decisions:
            for j,value in enumerate(x):
                self.weights[gate*len(FEATURES)+j] += self.learning_rate*advantage*(action-p)*value
        self.baseline = .9*self.baseline+.1*terminal[1]
        self.episodes += 1
        self.optimizer_steps += 1
        row = dict(episode=self.episodes, optimizer_steps=self.optimizer_steps,
                   weight_norm=math.sqrt(sum(w*w for w in self.weights)),
                   weight_change=math.sqrt(sum((w-i)**2 for w,i in zip(self.weights,INITIAL_WEIGHTS))),
                   steps=session.steps, inspection_steps=session.steps-1,
                   seconds=time.perf_counter()-started,
                   **{k:session.report[k] for k in ('precision','recall','f1','reward')})
        self.history.append(row)
        return copy.deepcopy(row)

    def run(self, session, initial, log=None):
        return investigate(session.step, initial, self.weights, log=log)[0]

    def evaluate(self, count=12, seed=70193):
        from .env import Session
        from .policies import run_policy
        if type(count) is not int or not 1<=count<=200 or type(seed) is not int:
            raise ValueError('Invalid evaluation configuration')
        rows = []
        for index in range(count):
            for policy in ('untrained','trained','random','reconciliation'):
                session=Session()
                initial,_=session.reset(episode_seed(seed,'holdout',index),self.config(index),'evaluation')
                started=time.perf_counter()
                if policy in ('random','reconciliation'):
                    run_policy(session,initial,policy)
                else:
                    investigate(session.step,initial,INITIAL_WEIGHTS if policy=='untrained' else self.weights)
                rows.append(dict(policy=policy,index=index,steps=session.steps,seconds=time.perf_counter()-started,
                                 **{k:session.report[k] for k in ('precision','recall','f1','reward')}))
        results=[]
        for policy in ('untrained','trained','random','reconciliation'):
            selected=[r for r in rows if r['policy']==policy]
            results.append(dict(policy=policy,episodes=count,**{k:sum(r[k] for r in selected)/count for k in ('precision','recall','f1','reward','steps','seconds')}))
        return dict(seed=seed,count=count,results=results,episodes=rows,scope='Frozen holdout. Learned source-table acquisition, deterministic documentary decoding.')

    def checkpoint(self):
        return dict(format='auditforge-source-acquisition-policy',version=2,environment=GENERATOR_VERSION,
                    architecture='three logistic source-table gates',algorithm='REINFORCE with moving reward baseline',
                    features=list(FEATURES),tables=list(TABLES),seed=self.seed,scenario=self.scenario,
                    learning_rate=self.learning_rate,weights=list(self.weights),episodes=self.episodes,
                    optimizer_steps=self.optimizer_steps,baseline=self.baseline,history=copy.deepcopy(self.history))

    @classmethod
    def from_checkpoint(cls,data):
        if not isinstance(data,dict) or data.get('format')!='auditforge-source-acquisition-policy' or data.get('version')!=2 or data.get('environment')!=GENERATOR_VERSION or data.get('features')!=list(FEATURES) or data.get('tables')!=list(TABLES) or data.get('algorithm')!='REINFORCE with moving reward baseline' or data.get('architecture')!='three logistic source-table gates':
            raise ValueError('Incompatible checkpoint')
        result=cls(data.get('seed'),data.get('scenario'),data.get('learning_rate'))
        weights=data.get('weights')
        if not isinstance(weights,list) or len(weights)!=len(INITIAL_WEIGHTS) or any(type(w) not in (int,float) or not math.isfinite(w) or abs(w)>1000 for w in weights):
            raise ValueError('Invalid parameters')
        for key in ('episodes','optimizer_steps'):
            if type(data.get(key)) is not int or not 0<=data[key]<=100000:
                raise ValueError('Invalid optimizer metadata')
        history=data.get('history')
        if data['episodes']!=data['optimizer_steps'] or not isinstance(history,list) or len(history)!=data['episodes'] or any(not isinstance(r,dict) for r in history):
            raise ValueError('Invalid history')
        baseline=data.get('baseline')
        if type(baseline) not in (int,float) or not math.isfinite(baseline) or not -1<=baseline<=1:
            raise ValueError('Invalid reward baseline')
        json.dumps(data,allow_nan=False)
        result.weights=list(weights)
        result.episodes=data['episodes']
        result.optimizer_steps=data['optimizer_steps']
        result.baseline=baseline
        result.history=copy.deepcopy(history)
        return result


def _validate_loaded_history(model):
    """Reject malformed metric histories before they reach chart rendering."""
    fields = ("weight_norm", "weight_change", "seconds", "precision", "recall", "f1", "reward")
    for index, row in enumerate(model.history, 1):
        if row.get("episode") != index or row.get("optimizer_steps") != index:
            raise ValueError("Invalid history sequence")
        for field in fields:
            value = row.get(field)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Invalid history metric")
        if any(not 0 <= row[key] <= 1 for key in ("precision", "recall", "f1")) or not -1 <= row["reward"] <= 1:
            raise ValueError("Invalid history metric range")
        if any(row[key] < 0 for key in ("weight_norm", "weight_change", "seconds")):
            raise ValueError("Invalid history measurement")
        if type(row.get("steps")) is not int or not 1 <= row["steps"] <= 100:
            raise ValueError("Invalid history action count")
        if type(row.get("inspection_steps")) is not int or row["inspection_steps"] != row["steps"]-1:
            raise ValueError("Invalid history inspection count")
    return model


def load_trainer(data):
    if isinstance(data,dict) and data.get('format')=='auditforge-source-acquisition-policy':
        return _validate_loaded_history(EfficientTrainer.from_checkpoint(data))
    return _validate_loaded_history(Trainer.from_checkpoint(data))
