"""SHORTCUT_HUNTER: public-only CPU probes with grouped train/validation/test.

The trusted runner supplies labels after public feature extraction. Models receive
feature dictionaries only. Binary classification is reported separately from
evidence-backed financial findings. No external dependencies are required.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import time

from .env import Session
from .generator import TYPES
from .matcher import evaluate
from .reconcile import reconcile


def public_snapshot(initial, step):
    """The inference boundary has an observation and a public action callable."""
    public = dict(manifest=initial['manifest'], policy=initial['policy'])
    steps = 0
    for table in ('ledger', 'invoices', 'payments', 'fx'):
        public[table], cursor = [], None
        while True:
            observation, reward, ended, truncated, info = step(dict(
                tool='list_records', table=table, cursor=cursor, limit=50))
            steps += 1
            if ended or truncated or reward or info or 'error' in observation:
                raise ValueError('Public collection failed or exhausted the budget')
            public[table].extend(observation['result']['records'])
            cursor = observation['result']['next_cursor']
            if cursor is None:
                break
    return public, steps


def features(public):
    """Descriptive buckets and graph degrees, without amount/date reconciliation."""
    ledger, invoices, payments = (public[k] for k in ('ledger', 'invoices', 'payments'))
    expenses = [r for r in ledger if r['account'] == 'expense']
    degrees = Counter(ref['invoice_id'] for p in payments for ref in p['invoice_refs'])
    row_degrees = Counter(r['invoice_id'] for r in ledger)
    amounts = Counter(i['total_minor'] for i in invoices)
    start = datetime.fromisoformat(public['manifest']['period_start'])
    end = datetime.fromisoformat(public['manifest']['period_end'])
    def outside(stamp):
        return not start <= datetime.fromisoformat(stamp) < end
    lout = [r for r in expenses if outside(r['timestamp'])]
    sout = [i for i in invoices if outside(i['issued_at'])]
    fx = [r for r in ledger if r.get('fx_rate') not in (None, '1')]
    first = ledger[0]
    return dict(
        record_count=len(ledger), document_count=len(invoices)+len(payments),
        invoice_count=len(invoices), payment_count=len(payments), fx_count=len(public['fx']),
        row_id_length=len(first['row_id']), row_id_prefix=first['row_id'].split('-')[0],
        row_id_suffix=first['row_id'][-1], invoice_id_suffix=invoices[0]['invoice_id'][-1],
        payment_id_suffix=payments[0]['payment_id'][-1],
        row_layout='|'.join(first), invoice_layout='|'.join(invoices[0]),
        missing_fields=sum(v is None for r in ledger for v in r.values()),
        first_account=first['account'], first_currency=payments[0]['currency'],
        last_account=ledger[-1]['account'], first_day=first['timestamp'][8:10],
        first_invoice_day=invoices[0]['issued_at'][8:10],
        outside_postings=len(lout), outside_invoices=len(sout),
        period_count_difference=len(lout)-len(sout),
        period_total_difference=(sum(r['debit_minor'] for r in lout) != sum(i['total_minor'] for i in sout)),
        max_invoice_degree=max(row_degrees.values()), max_payment_degree=max(degrees.values()),
        split_obligations=sum(n > 1 for n in degrees.values()),
        single_payment_components=sum(n == 1 for n in degrees.values()),
        refund_count=sum(p['amount_minor'] < 0 for p in payments),
        refund_links=sum('related_credit_doc_id' in i for i in invoices),
        repeated_amounts=sum(n > 1 for n in amounts.values()),
        repeated_amount_records=sum(n for n in amounts.values() if n > 1),
        last_minor_digit=sum(i['total_minor'] % 10 for i in invoices) % 10,
        round_amounts=sum(i['total_minor'] % 10000 == 0 for i in invoices),
        first_amount_bucket=len(str(invoices[0]['total_minor'])),
        foreign_postings=len(fx), zero_bookings=sum(r['debit_minor'] == r['credit_minor'] == 0 for r in ledger),
        company=public['manifest']['company'].split()[0], zone=public['manifest']['timezone'],
        envelope_suffix=public['manifest']['episode_id'][-1],
    )


def metrics(labels, predictions):
    counts = Counter(tp=0, fp=0, tn=0, fn=0)
    for label, prediction in zip(labels, predictions):
        counts['tp' if label and prediction else 'fn' if label else 'fp' if prediction else 'tn'] += 1
    tp, fp, tn, fn = (counts[k] for k in ('tp', 'fp', 'tn', 'fn'))
    p, r = tp/(tp+fp) if tp+fp else 0, tp/(tp+fn) if tp+fn else 0
    return dict(counts, precision=p, recall=r, f1=2*p*r/(p+r) if p+r else 0,
                accuracy=(tp+tn)/len(labels), balanced_accuracy=(r+tn/(tn+fp))/2,
                positive_prevalence=sum(labels)/len(labels), samples=len(labels))


def table_model(rows, keys):
    counts = defaultdict(Counter)
    fallback = sum(y for _, y in rows) > len(rows)/2
    for x, y in rows:
        counts[tuple(x[k] for k in keys)][y] += 1
    def predict(x):
        bucket = counts.get(tuple(x[k] for k in keys))
        return bucket[True] > bucket[False] if bucket else fallback
    return predict


def tree_model(rows, keys, depth=3, rng=None):
    majority = sum(y for _, y in rows) > len(rows)/2
    if depth == 0 or len(rows) < 8 or len({y for _, y in rows}) == 1:
        return lambda x: majority
    candidates = keys if rng is None else rng.sample(keys, min(8, len(keys)))
    best = None
    for key in candidates:
        for value, frequency in Counter(x[key] for x, _ in rows).most_common(6):
            if frequency == len(rows):
                continue
            left = [(x,y) for x,y in rows if x[key] == value]
            right = [(x,y) for x,y in rows if x[key] != value]
            error = sum(min(sum(y for _,y in group), sum(not y for _,y in group)) for group in (left,right))
            if best is None or error < best[0]:
                best = error, key, value, left, right
    if best is None:
        return lambda x: majority
    _, key, value, left, right = best
    a, b = (tree_model(group, keys, depth-1, rng) for group in (left, right))
    return lambda x: a(x) if x[key] == value else b(x)


def logistic_model(rows, keys):
    vocabulary = {(key,str(x[key])) for x,_ in rows for key in keys}
    weights = dict.fromkeys(vocabulary, 0.0)
    bias = 0.0
    rng = random.Random(309481)
    ordered = list(rows)
    for _ in range(35):
        rng.shuffle(ordered)
        for x, y in ordered:
            tokens = [(key,str(x[key])) for key in keys]
            z = max(-30, min(30, bias+sum(weights[t] for t in tokens)))
            gradient = y-1/(1+math.exp(-z))
            bias += .025*gradient
            for token in tokens:
                weights[token] += .025*(gradient-.002*weights[token])
    return lambda x: bias+sum(weights.get((key,str(x[key])),0) for key in keys) > 0


def fit_models(train, validation):
    keys = sorted(train[0][0])
    ranked = sorted(keys, key=lambda k: metrics([y for _,y in train],
                    [table_model(train,[k])(x) for x,_ in train])['balanced_accuracy'], reverse=True)
    models, selected = {}, {}
    for order in (1,2,3):
        best = None
        for candidate in itertools.combinations(ranked[:10], order):
            predict = table_model(train,candidate)
            score = metrics([y for _,y in validation], [predict(x) for x,_ in validation])['balanced_accuracy']
            if best is None or score > best[0]:
                best = score, candidate, predict
        models[f'rule_{order}'] = best[2]
        selected[f'rule_{order}'] = list(best[1])
    models['decision_tree'] = tree_model(train,keys)
    rng = random.Random(490231)
    forest = [tree_model(rng.choices(train,k=len(train)),keys,3,rng) for _ in range(17)]
    models['random_forest'] = lambda x: sum(model(x) for model in forest) > len(forest)/2
    models['logistic_regression'] = logistic_model(train,keys)
    graph_keys = [k for k in keys if 'degree' in k or 'component' in k or 'split' in k or 'refund' in k]
    models['graph_tree'] = tree_model(train,graph_keys)
    models['majority'] = lambda x: sum(y for _,y in train) > len(train)/2
    models['random'] = lambda x: int(hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()[:8],16) % 2 == 0
    # Detect exact content repetition, deliberately excluding envelope ID.
    content = [k for k in keys if k != 'envelope_suffix']
    models['memorized_pattern'] = table_model(train,content)
    return models, selected


def confidence(rows, predictions):
    families = defaultdict(list)
    for row, pred in zip(rows,predictions):
        families[row['family']].append((row['label'],pred))
    names, rng = list(families), random.Random(884291)
    scores = []
    for _ in range(300):
        sampled = [pair for family in rng.choices(names,k=len(names)) for pair in families[family]]
        scores.append(metrics([y for y,_ in sampled],[p for _,p in sampled])['balanced_accuracy'])
    scores.sort()
    return [scores[7],scores[292]]


def cohort(root, split, families):
    rows = []
    for index in range(families):
        seed = int.from_bytes(hashlib.sha256(f'hunter-v1:{root}:{split}:{index}'.encode()).digest()[:16],'big')
        base = dict(invoices=(40,57,82)[index%3], shuffle=bool(index%2),
                    timezone=('+05:45','-03:30','+14:00')[index%3], period_month=('2028-02','2031-12')[index%2])
        cases = [(dict(base,counts={kind:1},clean=clean),kind) for kind in TYPES for clean in (True,False)]
        cases += [(dict(base,recognition_world=world),'recognition_worlds') for world in range(4)]
        for config, scenario in cases:
            session = Session()
            initial,_ = session.reset(seed, config, 'evaluation')
            public, steps = public_snapshot(initial,session.step)
            x = features(public)
            # Only the trusted harness accesses labels and the scorer.
            truth = session.episode['truth']
            rows.append(dict(family=f'{split}-{index}',seed=seed,config=config,scenario=scenario,
                             label=bool(truth),x=x,steps=steps,observed_records=sum(len(public[t]) for t in ('ledger','invoices','payments','fx')),
                             public=public,truth=truth))
    return rows


def run(root=951730849201, train_families=40, validation_families=20, test_families=64):
    started = time.perf_counter()
    splits = {name:cohort(root,name,n) for name,n in [('train',train_families),('validation',validation_families),('test',test_families)]}
    models, selected = fit_models(*[[(r['x'],r['label']) for r in splits[name]] for name in ('train','validation')])
    evaluated = {}
    for name, model in models.items():
        evaluated[name] = {}
        for group in ['all',*TYPES,'recognition_worlds']:
            rows = [r for r in splits['test'] if group == 'all' or r['scenario'] == group]
            predicted = [bool(model(row['x'])) for row in rows]
            m = metrics([r['label'] for r in rows],predicted)
            m['balanced_accuracy_family_bootstrap_95'] = confidence(rows,predicted)
            evaluated[name][group] = m
    test = splits['test']
    chosen = max(models,key=lambda name: metrics([r['label'] for r in splits['validation']],
                        [models[name](r['x']) for r in splits['validation']])['balanced_accuracy'])
    finding_scores, full_scores = [], []
    for row in test:
        public = row['public']
        guess = []
        if models[chosen](row['x']):
            record = next(r for r in public['ledger'] if r['account'] == 'expense')
            guess = [dict(type='accounting_period',affected_ids=[record['row_id']],currency=record['currency'],
                          claimed_amount_minor=record['debit_minor'],evidence_ids=[record['row_id']],explanation='Diagnostic surface guess.')]
        for answer,destination in ((guess,finding_scores),(reconcile(public),full_scores)):
            destination.append(evaluate(public['manifest']['episode_id'],row['truth'],dict(
                episode_id=public['manifest']['episode_id'],findings=answer),row['steps']))
    def summarize(scores):
        return dict(mean_finding_f1=statistics.mean(r['f1'] for r in scores),tp=sum(r['tp'] for r in scores),
                    fp=sum(r['fp'] for r in scores),fn=sum(r['fn'] for r in scores),
                    mean_reward=statistics.mean(r['reward'] for r in scores))
    return dict(name='SHORTCUT_HUNTER',root=root,split_families={k:len({r['family'] for r in v}) for k,v in splits.items()},
                hyperparameters=dict(rule_candidate_training_features=10,rule_orders=[1,2,3],
                    tree_depth=3,tree_minimum_rows=8,forest_trees=17,forest_features_per_node=8,
                    logistic_epochs=35,logistic_learning_rate=.025,logistic_l2=.002,
                    selection='validation balanced accuracy',bootstrap_replicates=300),
                episodes={k:len(v) for k,v in splits.items()},features=sorted(test[0]['x']),selected_rules=selected,
                selected_by_validation=chosen,models=evaluated,shortcut_findings=summarize(finding_scores),
                financial_reconciliation=summarize(full_scores),max_public_steps=max(r['steps']+1 for r in test),
                mean_public_steps=statistics.mean(r['steps']+1 for r in test),
                mean_public_records=statistics.mean(r['observed_records'] for r in test),
                cohort=[{k:r[k] for k in ('family','seed','config','scenario','label')} for r in test],
                split_cohorts={split:[{k:r[k] for k in ('family','seed','config','scenario','label','steps','observed_records')}
                                     for r in rows] for split,rows in splits.items()},
                seconds=time.perf_counter()-started,limitations=[
                    'Binary presence prediction does not establish ID, amount, currency or complete evidence.',
                    'Aggregate disagreement and graph multiplicity may be legitimate financial indicators; causality requires separate controls.',
                    'One grouped held-out experiment cannot prove absence of other shortcuts.',
                    'All models inspect the same public pages; policy step counts include submit.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int,default=951730849201)
    parser.add_argument('--output',type=Path,default=Path('reports/shortcut-hunter.json'))
    args = parser.parse_args()
    result = run(args.seed)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('episodes','selected_by_validation','shortcut_findings','financial_reconciliation','max_public_steps','seconds')}))


if __name__ == '__main__':
    main()
