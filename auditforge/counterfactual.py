"""Evaluator-only paired challenges. Policies receive public actions, never answers.

All diagnostic matching takes place after submission. This is a local experiment,
not an official competition score or a guarantee about other generators.
"""
import copy
import hashlib
import json
import math
import statistics
import time
from collections import Counter

from .env import Session
from .generator import generate, TYPES
from .financial_audit import audit_episode
from .policies import run_policy

KINDS = TYPES + ('recognition',)


def surface_audit(count=25, seed=2026112203):
    """Paired feature-invariance screen, not a trained classifier or proof of safety.

    Changed features are reported even when economically necessary. Exact IDs and
    list order are included to avoid hiding accidental identifiers or layout cues.
    """
    if type(count) is not int or not 1 <= count <= 100 or type(seed) is not int:
        raise ValueError('count must be 1..100 and seed an integer')
    def signature(public):
        tables = ('ledger', 'invoices', 'payments', 'fx')
        records = [r for t in tables for r in public[t]]
        hist = lambda values: sorted(Counter(values).items(), key=lambda item: repr(item[0]))
        return dict(ids=sorted(k for t in tables for k in _index(public[t])),
                    order=[[r.get('row_id', r.get('doc_id')) for r in public[t]] for t in tables],
                    counts=[len(public[t]) for t in tables],
                    amounts=hist((k, v) for r in records for k, v in r.items() if k.endswith('_minor')),
                    dates=hist((k, v) for r in records for k, v in r.items() if k in ('timestamp', 'issued_at', 'due_at')),
                    currencies=hist((k, v) for r in records for k, v in r.items() if 'currency' in k),
                    layout=hist(tuple(sorted(r)) for r in records))
    pairs = []
    for index in range(count):
        metadata, clean, dirty = make_pair(index, seed)
        a, b = signature(clean['public']), signature(dirty['public'])
        pairs.append(dict(index=index, type=metadata['type'], equal_features={k:a[k] == b[k] for k in a}))
    return dict(method='Paired equality of public surface signatures; no classifier fitting, no exact-finding claim.',
                count=count, seed=seed, by_type={kind:{feature:sum(p['equal_features'][feature] for p in pairs if p['type'] == kind)
                                                     for feature in pairs[0]['equal_features']}
                                                for kind in KINDS if any(p['type'] == kind for p in pairs)},
                pairs=pairs,
                interpretation='Duplicate postings necessarily change counts and IDs; FX/allocation change amounts; period errors change dates. These are financial effects, not evidence of an answer leak. Recognition preserves ledger and aggregate source distributions. Passing this screen does not rule out learned shortcuts.')


def _index(rows):
    return {r.get('row_id', r.get('doc_id')): r for r in rows}


def make_pair(index, seed):
    """Change financial cause only, with exact independent financial validation."""
    kind = KINDS[index % len(KINDS)]
    config = dict(invoices=(40, 57, 84, 120, 200)[(index // 5) % 5],
                  timezone=('+05:45', '-03:30', '+14:00', '-09:30')[index % 4],
                  period_month=('2040-02', '2000-01', '2099-12')[index % 3],
                  boundary_payments=True)
    company_seed = int.from_bytes(hashlib.sha256(f'counterfactual-v1:{seed}:{index}'.encode()).digest()[:8], 'big')
    if kind == 'recognition':
        clean = generate(company_seed, dict(config, recognition_world=0))
        dirty = generate(company_seed, dict(config, recognition_world=2))
    else:
        dirty = generate(company_seed, dict(config, counts={t: int(t == kind) for t in TYPES}, interaction=0))
        clean = dict(public=copy.deepcopy(dirty['pristine']), pristine=copy.deepcopy(dirty['pristine']), truth=[], provenance=[])
    # Pristine and mutated books may be shuffled independently by generation.
    # Normalize both pair members: nuisance order must not encode the label.
    for episode in (clean, dirty):
        for books in (episode['public'], episode['pristine']):
            for table in ('ledger', 'invoices', 'payments', 'fx'):
                books[table].sort(key=lambda row: row.get('row_id', row.get('doc_id')))
    clean_public, dirty_public = clean['public'], dirty['public']
    before_rows, after_rows = _index(clean_public['ledger']), _index(dirty_public['ledger'])
    changed_rows = sorted(k for k in before_rows.keys() | after_rows.keys() if before_rows.get(k) != after_rows.get(k))
    changed_docs = []
    for table in ('invoices', 'payments', 'fx'):
        before, after = _index(clean_public[table]), _index(dirty_public[table])
        changed_docs.extend(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    controls = dict(same_sources=not changed_docs, same_ledger=not changed_rows,
                    changed_row_ids=changed_rows, changed_document_ids=sorted(changed_docs))
    if kind == 'recognition':
        assert controls['same_ledger'] and len(changed_docs) == 2
    else:
        assert controls['same_sources'] and changed_rows
    audits = [audit_episode(ep) for ep in (clean, dirty)]
    if not all(a['valid'] for a in audits):
        raise ValueError('Independent financial validation failed: ' + repr([a['errors'] for a in audits]))
    return dict(index=index, type=kind, seed=company_seed, config=config, controls=controls), clean, dirty


class _Actions:
    """Narrow action interface; no session/report/episode attribute for a policy."""
    def __init__(self, step):
        self.step = step


def diagnostics(truth, findings):
    """Explain rejected submissions only after terminal evaluator scoring.

    These are diagnostic hints; the unchanged official matcher remains authority.
    Do not provide this function or its output as policy inputs.
    """
    remaining = list(truth)
    errors = []
    for index, finding in enumerate(findings):
        candidates = [t for t in remaining if set(t['affected_ids']) == set(finding.get('affected_ids', []))]
        matched = next((t for t in candidates if t['type'] == finding.get('type') and
                        t['expected_amount_minor'] == finding.get('claimed_amount_minor') and
                        t['currency'] == finding.get('currency') and
                        any(set(e) <= set(finding.get('evidence_ids', [])) for e in t['evidence_sets'])), None)
        if matched is not None:
            remaining.remove(matched)
            continue
        if not candidates:
            repeated = any(t['type'] == finding.get('type') and set(t['affected_ids']) == set(finding.get('affected_ids', []))
                           for t in truth if t not in remaining)
            reason = 'duplicate_finding' if repeated else ('wrong_affected_ids' if truth else 'false_positive')
        else:
            same_type = [t for t in candidates if t['type'] == finding.get('type')]
            reason = 'wrong_type' if not same_type else 'amount_mismatch'
            exact_amount = [t for t in same_type if t['expected_amount_minor'] == finding.get('claimed_amount_minor')]
            if exact_amount:
                reason = 'currency_mismatch' if not any(t['currency'] == finding.get('currency') for t in exact_amount) else 'insufficient_evidence'
        errors.append(dict(finding_index=index, type=finding.get('type'), reason=reason,
                           affected_ids=finding.get('affected_ids', []), evidence_ids=finding.get('evidence_ids', [])))
    errors.extend(dict(finding_index=None, type=t['type'], reason='missing_finding') for t in remaining)
    return errors


def _run(episode, trainer, name, include_trajectories=True):
    session = Session()
    # Initialize evaluator bookkeeping without exposing it to policy code.
    session.episode, session.public, session.mode = copy.deepcopy(episode), copy.deepcopy(episode['public']), 'evaluation'
    session.steps, session.done, session.done_flags = 0, False, (False, False)
    session.report, session.started, session.seconds, session.final = None, time.monotonic(), 60, []
    initial = dict(task='Audit the company for four documented financial issue types; submit evidence-backed findings.',
                   manifest=copy.deepcopy(session.public['manifest']), policy=copy.deepcopy(session.public['policy']), steps_remaining=100)
    trajectory = []
    def public_step(action):
        returned = session.step(action)
        if include_trajectories:
            trajectory.append(dict(step=session.steps, action=copy.deepcopy(action),
                                   observation=copy.deepcopy(returned[0]), reward=returned[1],
                                   terminated=returned[2], truncated=returned[3]))
        return returned
    boundary = _Actions(public_step)
    if name == 'trained':
        trainer.run(boundary, initial)
    else:
        run_policy(boundary, initial, name)
    if not session.done:
        public_step(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=[])))
    findings = session.final.get('findings', []) if isinstance(session.final, dict) else []
    metrics = dict(session.report, steps=session.steps, inspection_steps=session.steps - int(session.done_flags[0]))
    return dict(episode_id=initial['manifest']['episode_id'], metrics=metrics, findings=findings,
                diagnostics=diagnostics(episode['truth'], findings), trajectory=trajectory,
                terminated=session.done_flags[0], truncated=session.done_flags[1])


def _aggregate(runs):
    tp, fp, fn = (sum(r['metrics'].get(k, 0) for r in runs) for k in ('tp', 'fp', 'fn'))
    steps = sorted(r['metrics']['steps'] for r in runs)
    n = len(runs)
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else 0,
                recall=tp/(tp+fn) if tp+fn else 0, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1,
                reward=sum(r['metrics']['reward'] for r in runs)/n,
                steps=sum(steps)/n, inspection_steps=sum(r['metrics']['inspection_steps'] for r in runs)/n,
                median_steps=statistics.median(steps), p90_steps=steps[max(0, math.ceil(.9*n)-1)])


def challenge(trainer, count=10, seed=2026112203, include_baselines=True, include_trajectories=True):
    """Frozen-checkpoint paired holdout, suitable for Python and browser workers.

    count counts pairs, not episodes. Each five consecutive pairs covers all four
    issue types and a balanced-journal recognition pair. Additional batches vary
    company size. No updates, training reward, or ground truth reach the policy.
    """
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError('count must be an integer from 1 to 100')
    if type(seed) is not int:
        raise ValueError('seed must be an integer')
    before = json.dumps(trainer.checkpoint(), sort_keys=True)
    pairs = [make_pair(i, seed) for i in range(count)]
    policies = []
    for name in (('trained', 'random', 'reconciliation') if include_baselines else ('trained',)):
        evaluated = []
        for metadata, clean, dirty in pairs:
            a, b = _run(clean, trainer, name, include_trajectories), _run(dirty, trainer, name, include_trajectories)
            evaluated.append(dict(metadata, clean=a, dirty=b,
                                  consistent=a['metrics']['f1'] == b['metrics']['f1'] == 1,
                                  presence_correct=not a['findings'] and bool(b['findings'])))
        by_type = {}
        for kind in KINDS:
            selected = [p for p in evaluated if p['type'] == kind]
            if selected:
                by_type[kind] = dict(_aggregate([r for p in selected for r in (p['clean'], p['dirty'])]),
                                     pairs=len(selected), consistent_pairs=sum(p['consistent'] for p in selected),
                                     pair_consistency=sum(p['consistent'] for p in selected)/len(selected))
        policies.append(dict(name=name, metrics=_aggregate([r for p in evaluated for r in (p['clean'], p['dirty'])]),
                             pair_consistency=sum(p['consistent'] for p in evaluated)/count,
                             presence_accuracy=sum(p['presence_correct'] for p in evaluated)/count,
                             by_type=by_type, pairs=evaluated))
    unchanged = before == json.dumps(trainer.checkpoint(), sort_keys=True)
    if not unchanged:
        raise RuntimeError('Evaluation changed the checkpoint')
    return dict(format='auditforge-counterfactual-challenge', version=1, count=count, seed=seed,
                pair_count=count, episode_count=2*count, data_validation=dict(passed=2*count, failed=0),
                policies=policies, checkpoint_unchanged=unchanged, trajectories_recorded=include_trajectories,
                scope='Local paired financial holdout; micro F1 and exact pair consistency; no official jury score. Diagnostics are evaluator-only after terminal submission.')
