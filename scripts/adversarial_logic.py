"""Independent public-investigation counterfactual stress and small matcher reference."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import random
from unittest.mock import patch

from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.generator import TYPES, generate
from auditforge.matcher import evaluate
from auditforge.policies import run_policy
from scripts.jury_blind import PublicActions
from scripts.jury_reward import reference_metrics, same_metrics


def assignment_reference(edges, columns):
    """Enumerate injective partial assignments, including abstentions."""
    best = 0
    for chosen in itertools.product(range(-1, columns), repeat=len(edges)):
        selected = [j for j in chosen if j >= 0]
        if len(set(selected)) != len(selected):
            continue
        if all(j == -1 or j in edges[i] for i, j in enumerate(chosen)):
            best = max(best, len(selected))
    return best


def matcher_trials(seed, count=400):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        n, m = rng.randint(1, 4), rng.randint(1, 4)
        edges = [{j for j in range(m) if rng.randrange(2)} for _ in range(n)]
        truth = [dict(type=TYPES[0], affected_ids=['r'], currency='KZT',
                      expected_amount_minor=100, tolerance_minor=5,
                      evidence_sets=[[f'd{j}']]) for j in range(m)]
        claims = [dict(type=TYPES[0], affected_ids=['r'], currency='KZT',
                       claimed_amount_minor=100+i, explanation='',
                       evidence_ids=[f'd{j}' for j in sorted(neighbors)])
                  for i, neighbors in enumerate(edges)]
        expected_tp = assignment_reference(edges, m)
        steps = rng.randrange(100)
        expected = reference_metrics(expected_tp, n-expected_tp, m-expected_tp, steps)
        observed = evaluate('reference', truth, dict(episode_id='reference', findings=claims), steps)
        variants = []
        # Arbitrary source/claim order must preserve metrics.
        for _ in range(3):
            rng.shuffle(truth)
            rng.shuffle(claims)
            variants.append(evaluate('reference', truth,
                                     dict(episode_id='reference', findings=claims), steps))
        rows.append(dict(index=index, edges=[sorted(e) for e in edges],
                         expected=expected, observed=observed,
                         passed=all(same_metrics(v, expected) for v in [observed]+variants)))
    return rows


def public_trial(episode):
    """A step-only facade is the policy's sole access to an episode."""
    session = Session()
    with patch('auditforge.env.generate', return_value=episode):
        initial, _ = session.reset(0, {}, 'evaluation')
    access = PublicActions(session.step)
    run_policy(access, initial, 'reconciliation')
    return dict(f1=session.report['f1'], tp=session.report['tp'],
                steps=access.steps, reward=session.report['reward'], errors=access.errors,
                passed=session.report['f1'] == 1 and not access.errors
                and session.done_flags == (True, False) and access.steps <= 100)


def run(root=9234107783201, count=40):
    scenarios = [(kind, dict(counts={kind: 1})) for kind in TYPES]
    scenarios += [('split_foreign_cutoff', dict(interaction=1)),
                  ('refund_duplicate_cutoff', dict(interaction=2))]
    rows = []
    for index in range(count):
        seed = int.from_bytes(hashlib.sha256(f'logic-audit:{root}:{index}'.encode()).digest()[:16], 'big')
        for label, config in scenarios:
            config = dict(config, timezone=('-00:30', '+14:00', '-12:00')[index%3],
                          period_month=('2028-02', '2000-01', '2099-12')[index%3],
                          boundary_payments=True)
            dirty = generate(seed, config)
            clean = dict(public=copy.deepcopy(dirty['pristine']),
                         pristine=copy.deepcopy(dirty['pristine']), truth=[], provenance=[])
            # Keep a separate episode identity, without changing its business records.
            for branch in ('public', 'pristine'):
                clean[branch]['manifest']['episode_id'] += '-control'
            audit_dirty, audit_clean = audit_episode(dirty), audit_episode(clean)
            clean_score, dirty_score = public_trial(clean), public_trial(dirty)
            public = dirty['public']
            rows.append(dict(seed=seed, scenario=label, config=config,
                             source_documents_identical=all(sorted(public[t],key=lambda r:r.get('row_id',r.get('doc_id'))) == sorted(clean['public'][t],key=lambda r:r.get('row_id',r.get('doc_id')))
                                                            for t in ('invoices','payments','fx')),
                             signed_refunds=sum(p['amount_minor'] < 0 for p in public['payments']),
                             legitimate_split_payments=sum(len([p for p in public['payments']
                                 if any(r['invoice_id']==inv['invoice_id'] for r in p['invoice_refs'])])>1
                                 for inv in public['invoices']),
                             dirty=dirty_score, clean=clean_score,
                             issues=len(dirty['truth']),
                             audit_errors=audit_dirty['errors']+audit_clean['errors'],
                             passed=audit_dirty['valid'] and audit_clean['valid']
                             and clean_score['passed'] and dirty_score['passed']))
    assignments = matcher_trials(root+1)
    return dict(root=root, pairs=rows, matching=assignments,
                passed=all(r['passed'] for r in rows+assignments),
                scope='Paired pristine/corrupted business histories, not equal-ledger camouflage. '
                      'Graph assignments use distinct claim amounts within an explicit tolerance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=9234107783201)
    parser.add_argument('--count', type=int, default=40)
    parser.add_argument('--output', type=Path, default=Path('reports/adversarial-logic.json'))
    args = parser.parse_args()
    result = run(args.seed, args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], financial_pairs=len(result['pairs']),
                         matcher_graphs=len(result['matching']))))
    raise SystemExit(not result['passed'])