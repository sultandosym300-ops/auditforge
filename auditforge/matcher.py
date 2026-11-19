"""Exact amount tolerance; maximum-cardinality deterministic bipartite matching."""
import copy
from .generator import TYPES


def oracle(episode):
    return dict(episode_id=episode['public']['manifest']['episode_id'], findings=[dict(type=t['type'], affected_ids=t['affected_ids'], claimed_amount_minor=t['expected_amount_minor'], currency=t['currency'], evidence_ids=t['evidence_sets'][0], explanation='Verified against source documents and posting policy.') for t in episode['truth']])


def valid(payload, episode_id):
    if not isinstance(payload, dict) or payload.get('episode_id') != episode_id or not isinstance(payload.get('findings'), list) or len(payload['findings']) > 30:
        return False
    for f in payload['findings']:
        if not isinstance(f, dict) or f.get('type') not in TYPES or type(f.get('claimed_amount_minor')) is not int or f['claimed_amount_minor'] < 0:
            return False
        if not isinstance(f.get('currency'), str) or not isinstance(f.get('explanation'), str) or len(f['explanation']) > 1000:
            return False
        for key, maximum in [('affected_ids', 2000), ('evidence_ids', 10)]:
            ids = f.get(key)
            if not isinstance(ids, list) or len(ids) > maximum or any(not isinstance(x, str) or len(x) > 128 for x in ids) or len(set(ids)) != len(ids):
                return False
    return True


def evaluate(episode_id, truth, payload, inspection_steps):
    if not valid(payload, episode_id):
        return dict(tp=0, fp=0, fn=len(truth), precision=0, recall=0, f1=0, reward=-1, error='invalid_submission')
    findings = payload['findings']
    def match(f, t):
        return (f['type'] == t['type'] and sorted(f['affected_ids']) == sorted(t['affected_ids']) and f['currency'] == t['currency'] and abs(f['claimed_amount_minor'] - t['expected_amount_minor']) <= t.get('tolerance_minor', 0) and any(set(s) <= set(f['evidence_ids']) for s in t['evidence_sets']))
    graph = [[j for j, t in enumerate(truth) if match(f, t)] for f in findings]
    assigned = {}
    def augment(i, seen):
        for j in graph[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or augment(assigned[j], seen):
                assigned[j] = i
                return True
        return False
    for i in range(len(findings)):
        augment(i, set())
    tp = len(assigned)
    fp, fn = len(findings) - tp, len(truth) - tp
    p = tp / (tp+fp) if tp+fp else 0
    r = tp / (tp+fn) if tp+fn else 0
    f1 = 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1
    return dict(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f1, reward=max(-1, min(1, 2*f1-1-.002*inspection_steps)))
