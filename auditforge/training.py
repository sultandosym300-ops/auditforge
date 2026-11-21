"""CPU REINFORCE policy learning which recognition documents to inspect.

The policy receives public observations and a step callable. Evidence assembly is
an explicit accounting rule after inspection. It does not learn all audit types.
"""
import copy
from datetime import datetime
import hashlib
import json
import math
import random
import time

from .generator import GENERATOR_VERSION

FEATURES = ('bias', 'duplicate_recognition', 'outside_period', 'near_boundary', 'repeated_amount')
INITIAL_WEIGHTS = [-1.0, 0.0, 0.0, 0.0, 0.0]
SCENARIOS = ('period', 'duplicate', 'mixed')


def episode_seed(root, split, index):
    value = f'recognition-rl-v1:{root}:{split}:{index}'.encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:16], 'big')


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-35, min(35, value))))


def investigate(step, initial, weights, rng=None, log=None):
    """Public-only inference. The optional RNG samples the query action in training."""
    manifest = initial['manifest']
    remaining = initial['steps_remaining']
    decisions, ledger, findings = [], [], []
    def act(action):
        nonlocal remaining
        result = step(action)
        remaining = result[0]['steps_remaining']
        if log is not None:
            log.append(dict(episode_id=manifest['episode_id'], step=len(log)+1,
                            action=action, observation=result[0], reward=result[1],
                            terminated=result[2], truncated=result[3]))
        return result
    cursor = None
    while remaining > 1:
        result = act(dict(tool='list_records', table='ledger', cursor=cursor, limit=50))
        if result[2] or result[3] or 'error' in result[0]:
            return result, decisions
        page = result[0]['result']
        ledger.extend(page['records'])
        cursor = page['next_cursor']
        if cursor is None:
            break
    groups = {}
    for row in ledger:
        if row['account'] == 'expense' and row['payment_id'] is None:
            groups.setdefault(row['invoice_id'], []).append(row)
    start, end = (datetime.fromisoformat(manifest[k]) for k in ('period_start','period_end'))
    amounts = {}
    for rows in groups.values():
        amount = rows[0]['debit_minor']
        amounts[amount] = amounts.get(amount, 0)+1
    for iid, rows in groups.items():
        if remaining <= 1:
            break
        stamps = [datetime.fromisoformat(row['timestamp']) for row in rows]
        outside = any(not start <= stamp < end for stamp in stamps)
        nearby = any(min(abs((stamp-start).total_seconds()), abs((stamp-end).total_seconds())) < 86400 for stamp in stamps)
        features = [1., float(len(rows)>1), float(outside), float(nearby), float(amounts[rows[0]['debit_minor']]>1)]
        probability = sigmoid(sum(w*x for w,x in zip(weights,features)))
        query = rng.random() < probability if rng is not None else probability >= .5
        decisions.append((features, float(query), probability))
        if not query:
            continue
        result = act(dict(tool='get_record', table='invoices', id=iid))
        if result[2] or result[3]:
            return result, decisions
        if 'error' in result[0]:
            continue
        invoice = result[0]['result']
        def finding(kind, affected, amount, evidence):
            findings.append(dict(type=kind, affected_ids=sorted(affected),
                                 claimed_amount_minor=abs(amount), currency=manifest['base_currency'],
                                 evidence_ids=sorted(evidence), explanation='Invoice recognition checked against the source document.'))
        if len(rows)>1:
            finding('duplicate_invoice',[r['row_id'] for r in rows],
                    sum(r['debit_minor'] for r in rows)-invoice['total_minor'],
                    [invoice['doc_id']]+[r['row_id'] for r in rows])
        issued = datetime.fromisoformat(invoice['issued_at'])
        for row,stamp in zip(rows,stamps):
            if (start <= issued < end) != (start <= stamp < end):
                finding('accounting_period',[row['row_id']],invoice['total_minor'],[invoice['doc_id'],row['row_id']])
    return act(dict(tool='submit', findings=dict(episode_id=manifest['episode_id'],findings=findings[:30]))), decisions


class Trainer:
    def __init__(self, seed=20261121, scenario='period'):
        if type(seed) is not int or scenario not in SCENARIOS:
            raise ValueError('Invalid training seed or scenario')
        self.seed, self.scenario = seed, scenario
        self.weights = list(INITIAL_WEIGHTS)
        self.episodes = 0
        self.optimizer_steps = 0
        self.baseline = 0.0
        self.history = []

    def config(self, index):
        counts = {'accounting_period': 2} if self.scenario == 'period' else {'duplicate_invoice':2}
        if self.scenario == 'mixed':
            return dict(clean=index%5 == 0, interaction=index%3)
        return dict(clean=index%5 == 0, counts=counts, invoices=40,
                    timezone=('+05:45','-03:30','+14:00')[index%3],
                    period_month=('2028-02','2031-12')[index%2],boundary_payments=True)

    def train_episode(self):
        from .env import Session
        session = Session()
        seed = episode_seed(self.seed,'train',self.episodes)
        initial,_ = session.reset(seed,self.config(self.episodes),'train')
        rng = random.Random(episode_seed(self.seed,'actions',self.episodes))
        started = time.perf_counter()
        terminal, decisions = investigate(session.step,initial,self.weights,rng)
        reward = terminal[1]
        advantage = reward-self.baseline
        gradient = [sum((action-p)*x[j] for x,action,p in decisions) for j in range(len(FEATURES))]
        for j, value in enumerate(gradient):
            self.weights[j] += .12 * advantage * max(-5,min(5,value))
        self.baseline = .9*self.baseline+.1*reward
        self.episodes += 1
        self.optimizer_steps += 1
        row = dict(episode=self.episodes, optimizer_steps=self.optimizer_steps,
                   weight_norm=math.sqrt(sum(w*w for w in self.weights)),
                   weight_change=math.sqrt(sum((w-i)**2 for w,i in zip(self.weights,INITIAL_WEIGHTS))),
                   inspection_steps=session.steps-1, steps=session.steps,
                   seconds=time.perf_counter()-started,
                   **{k:session.report[k] for k in ('precision','recall','f1','reward')})
        self.history.append(row)
        return copy.deepcopy(row)

    def run(self, session, initial, log=None):
        return investigate(session.step,initial,self.weights,log=log)[0]

    def evaluate(self, count=12, seed=70193):
        from .env import Session
        from .policies import run_policy
        if type(count) is not int or not 1 <= count <= 200 or type(seed) is not int:
            raise ValueError('Invalid evaluation configuration')
        rows = []
        for index in range(count):
            hidden_seed = episode_seed(seed,'holdout',index)
            config = self.config(index)
            for policy in ('untrained','trained','random','reconciliation'):
                session = Session()
                initial,_ = session.reset(hidden_seed,config,'evaluation')
                started = time.perf_counter()
                if policy in ('random','reconciliation'):
                    run_policy(session,initial,policy)
                else:
                    investigate(session.step,initial,INITIAL_WEIGHTS if policy=='untrained' else self.weights)
                rows.append(dict(policy=policy, index=index, steps=session.steps, inspection_steps=session.steps-int(session.done_flags[0]),
                                 seconds=time.perf_counter()-started,
                                 **{k:session.report[k] for k in ('precision','recall','f1','reward')}))
        summary = []
        for policy in ('untrained','trained','random','reconciliation'):
            selected = [r for r in rows if r['policy']==policy]
            summary.append(dict(policy=policy, episodes=count,
                                **{k:sum(r[k] for r in selected)/count for k in ('precision','recall','f1','reward','steps','inspection_steps','seconds')}))
        return dict(seed=seed,count=count,results=summary,episodes=rows,
                    scope='Frozen holdout, no optimizer update. Learned skill is invoice-document acquisition for recognition errors.')

    def checkpoint(self):
        return dict(format='auditforge-recognition-policy',version=1,environment=GENERATOR_VERSION,
                    algorithm='REINFORCE with moving reward baseline',architecture='logistic query policy',
                    features=list(FEATURES),seed=self.seed,scenario=self.scenario,weights=list(self.weights),
                    episodes=self.episodes,optimizer_steps=self.optimizer_steps,baseline=self.baseline,
                    history=copy.deepcopy(self.history))

    @classmethod
    def from_checkpoint(cls, data):
        if not isinstance(data,dict) or data.get('format')!='auditforge-recognition-policy' or data.get('version')!=1 or data.get('environment')!=GENERATOR_VERSION or data.get('features')!=list(FEATURES) or data.get('algorithm')!='REINFORCE with moving reward baseline' or data.get('architecture')!='logistic query policy':
            raise ValueError('Incompatible checkpoint')
        result = cls(data.get('seed'),data.get('scenario'))
        weights = data.get('weights')
        if not isinstance(weights,list) or len(weights)!=len(FEATURES) or any(type(w) not in (int,float) or not math.isfinite(w) or abs(w)>1000 for w in weights):
            raise ValueError('Invalid policy parameters')
        for key in ('episodes','optimizer_steps'):
            if type(data.get(key)) is not int or not 0<=data[key]<=100000:
                raise ValueError('Invalid optimizer metadata')
        if data['episodes'] != data['optimizer_steps']:
            raise ValueError('Inconsistent optimizer metadata')
        history = data.get('history')
        if not isinstance(history,list) or len(history)!=data['episodes'] or any(not isinstance(r,dict) for r in history):
            raise ValueError('Invalid training history')
        baseline=data.get('baseline')
        if type(baseline) not in (int,float) or not math.isfinite(baseline) or not -1<=baseline<=1:
            raise ValueError('Invalid baseline')
        json.dumps(data,allow_nan=False)
        result.weights=list(weights)
        result.episodes=data['episodes']
        result.optimizer_steps=data['optimizer_steps']
        result.baseline=baseline
        result.history=copy.deepcopy(history)
        return result
