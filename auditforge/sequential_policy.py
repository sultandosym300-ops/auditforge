"""Public-only sequential policies. Financial decoding is shared by every policy."""
import itertools
import math
import random

from .documentary_decode import decode

FEATURES = ('bias', 'manual', 'cutoff', 'cross_border', 'supplier_change',
            'manual_cutoff', 'observed_issue_rate', 'budget_fraction',
            'remaining_cost', 'started', 'inverse_cost', 'manual_per_cost',
            'cutoff_per_cost', 'cross_border_per_cost', 'supplier_change_per_cost', 'stop')
INITIAL_WEIGHTS = [0.] * (len(FEATURES)-1) + [-2.]
POLICIES = ('random_valid', 'fixed_source', 'budget_aware', 'greedy',
            'heuristic_search', 'reconciliation', 'learned', 'untrained',
            'random_weights', 'zero_features', 'no_financial_rules', 'no_source_selection')


def softmax(values):
    top = max(values)
    exps = [math.exp(max(-60, value-top)) for value in values]
    return [value/sum(exps) for value in exps]


def vector(candidate, remaining, completed, positive, *, stop=False):
    if stop:
        return [0.]*(len(FEATURES)-1)+[1.]
    return [1., candidate['manual_entries'], candidate['cutoff_pressure'],
            candidate['cross_border'], candidate['supplier_change'],
            candidate['manual_entries']*candidate['cutoff_pressure'],
            positive/max(1, completed), remaining/100,
            candidate['left']/3, float(candidate['left']<candidate['query_cost']),
            1/candidate['left'],candidate['manual_entries']/candidate['left'],
            candidate['cutoff_pressure']/candidate['left'],candidate['cross_border']/candidate['left'],
            candidate['supplier_change']/candidate['left'],0.]


def estimated_yield(candidate, completed, positive):
    # Strong hand-written operational-risk prior, updated by observed departments.
    risk = (-2.1 + 1.1*candidate['manual_entries'] + .8*candidate['cutoff_pressure']
            + .6*candidate['cross_border'] + .7*candidate['supplier_change'])
    posterior = (positive+1)/(completed+2)
    risk += 1.8*(posterior-.5)
    return 2.5/(1+math.exp(-risk))


def investigate(step, initial, *, policy='learned', budget=10, weights=None,
                rng=None, zero_features=False, financial_rules=True):
    if policy not in POLICIES or type(budget) is not int or not 2<=budget<=100:
        raise ValueError('Invalid policy or action budget')
    candidates = [dict(item, left=item['query_cost'], next=item['document_id'])
                  for item in initial['manifest'].get('investigations', [])]
    if not candidates:
        raise ValueError('Sequential policy requires investigation_v1')
    weights = list(INITIAL_WEIGHTS if weights is None else weights)
    if len(weights)!=len(FEATURES) or any(not math.isfinite(w) for w in weights):
        raise ValueError('Invalid policy weights')
    rng = rng or random.Random(0)
    remaining = min(budget, initial['steps_remaining'])
    trajectory, decisions, findings = [], [], []
    completed = positive = 0
    def act(action, reason):
        nonlocal remaining
        result = step(action)
        remaining -= 1
        trajectory.append(dict(episode_id=initial['manifest']['episode_id'], step=len(trajectory)+1,
                               action=action, observation=result[0], reward=result[1],
                               terminated=result[2], truncated=result[3], reason=reason))
        if 'error' in result[0]:
            raise ValueError('Policy received an invalid tool response')
        return result
    if policy=='reconciliation':
        public = dict(manifest=initial['manifest'], policy=initial['policy'], ledger=[], invoices=[], payments=[], fx=[])
        for table in ('ledger','invoices','payments','fx'):
            cursor = None
            while remaining>1:
                result=act(dict(tool='list_records',table=table,cursor=cursor,limit=50), 'Full-source reconciliation; retain partial evidence at budget limit')
                public[table].extend(result[0]['result']['records'])
                cursor=result[0]['result']['next_cursor']
                if cursor is None:break
        findings=decode(public)
    else:
        while remaining>1:
            available=[c for c in candidates if c['left'] and c['left']<=remaining-1]
            if not available:break
            xs=[vector(c,remaining,completed,positive) for c in available]
            xs.append(vector(None,remaining,completed,positive,stop=True))
            chosen=0
            if policy=='random_valid':
                chosen=rng.randrange(len(available)+(completed>0))
            elif policy in ('fixed_source','no_source_selection'):
                chosen=0
            elif policy=='budget_aware':
                chosen=max(range(len(available)),key=lambda i:estimated_yield(available[i],completed,positive)/available[i]['left'])
            elif policy=='greedy':
                def information_gain(i):
                    p=estimated_yield(available[i],completed,positive)/2.5
                    entropy=-p*math.log(max(p,1e-12))-(1-p)*math.log(max(1-p,1e-12))
                    return entropy/available[i]['left']
                chosen=max(range(len(available)),key=information_gain)
            elif policy=='heuristic_search':
                # Enumerate feasible portfolios, then query best expected-yield/cost first.
                subsets=[items for size in range(1,len(available)+1)
                         for items in itertools.combinations(range(len(available)),size)
                         if sum(available[i]['left'] for i in items)<=remaining-1]
                best=max(subsets,key=lambda items:sum(estimated_yield(available[i],completed,positive) for i in items))
                chosen=max(best,key=lambda i:estimated_yield(available[i],completed,positive)/available[i]['left'])
            else:
                effective=[list(x) for x in xs]
                if zero_features or policy=='zero_features':
                    effective=[[x[0]]+[0.]*(len(FEATURES)-2)+[x[-1]] for x in effective]
                active_weights=INITIAL_WEIGHTS if policy=='untrained' else weights
                if policy=='random_weights':
                    active_weights=[random.Random(719+i).uniform(-1,1) for i in range(len(FEATURES))]
                probabilities=softmax([sum(w*x for w,x in zip(active_weights,features)) for features in effective])
                # Stochastic only when explicitly requested for training.
                chosen=rng.choices(range(len(xs)),weights=probabilities)[0] if getattr(rng,'training',False) else max(range(len(xs)),key=lambda i:probabilities[i])
                decisions.append(dict(features=effective,probabilities=probabilities,chosen=chosen))
            if chosen==len(available):break
            candidate=available[chosen]
            reason=dict(policy=policy,case_id=candidate['case_id'],remaining_budget=remaining,
                        remaining_cost=candidate['left'])
            if policy in ('learned','untrained','random_weights','zero_features','no_financial_rules'):
                reason.update(selected_probability=probabilities[chosen],features=effective[chosen],
                              learned_score=sum(w*x for w,x in zip(active_weights,effective[chosen])))
            elif policy in ('budget_aware','greedy','heuristic_search'):
                reason['estimated_yield']=estimated_yield(candidate,completed,positive)
            result=act(dict(tool='get_document',doc_id=candidate['next']),reason)
            document=result[0]['result'];candidate['left']-=1
            if 'records' in document:
                recovered=decode(document['records']) if financial_rules and policy!='no_financial_rules' else []
                findings.extend(recovered);completed+=1;positive+=bool(recovered)
                candidate['left']=0
            else:
                candidate['next']=document['next_document_id']
    # Every finding uses acquired financial documents, never case risk estimates.
    unique={ (f['type'],tuple(f['affected_ids'])):f for f in findings }
    terminal=act(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=list(unique.values())[:30])), 'Submit documentary findings; reserve one action for termination')
    return dict(terminal=terminal, decisions=decisions, trajectory=trajectory, findings=list(unique.values()))
