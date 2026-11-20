"""Independent reward tournament for the AuditForge jury gauntlet (Python 3.11)."""
import argparse
import itertools
import json
from fractions import Fraction

from auditforge.env import Session
from auditforge.generator import TYPES, generate
from auditforge.matcher import evaluate


def reference_metrics(tp, fp, fn, steps):
    precision = Fraction(tp, tp + fp) if tp + fp else 0
    recall = Fraction(tp, tp + fn) if tp + fn else 0
    f1 = Fraction(2 * tp, 2 * tp + fp + fn) if tp or fp or fn else 1
    reward = max(-1, min(1, 2 * f1 - 1 - Fraction(steps, 500)))
    return dict(tp=tp, fp=fp, fn=fn, precision=float(precision), recall=float(recall),
                f1=float(f1), reward=float(reward))


def exhaustive_graphs():
    """Enumerate all 512 labeled 3-by-3 graphs and their legal partial assignments."""
    truths = [dict(type=TYPES[0], affected_ids=['r'], currency='KZT', expected_amount_minor=100,
                   tolerance_minor=2, evidence_sets=[[str(j)]]) for j in range(3)]
    assignments = [a for a in itertools.product(range(-1, 3), repeat=3)
                   if len(set(j for j in a if j >= 0)) == sum(j >= 0 for j in a)]
    failures = []
    for mask in range(1 << 9):
        edges = [[j for j in range(3) if mask & (1 << (3 * i + j))] for i in range(3)]
        findings = [dict(type=TYPES[0], affected_ids=['r'], currency='KZT', claimed_amount_minor=100+i,
                         evidence_ids=list(map(str, edges[i])), explanation='') for i in range(3)]
        best = max(sum(j >= 0 for j in a) for a in assignments
                   if all(j < 0 or j in edges[i] for i, j in enumerate(a)))
        actual = evaluate('synthetic', truths, dict(episode_id='synthetic', findings=findings), mask % 100)
        if not same_metrics(actual, reference_metrics(best, 3-best, 3-best, mask % 100)):
            failures.append(mask)
    return failures


def same_metrics(actual, expected):
    return all(key in actual and abs(value - actual[key]) < 1e-12 for key, value in expected.items())


def run(seed=901405):
    session = Session()
    session.reset(seed, dict(interaction=2), 'train')
    episode = session.episode
    truth = episode['truth']
    eid = episode['public']['manifest']['episode_id']
    correct = [dict(type=t['type'], affected_ids=t['affected_ids'], currency=t['currency'],
                    claimed_amount_minor=t['expected_amount_minor'], evidence_ids=t['evidence_sets'][0],
                    explanation='') for t in truth]
    n = len(truth)
    clean = generate(seed, dict(clean=True))
    foreign = generate(seed+1, dict(interaction=2))['truth']
    checks = []

    def record(name, inputs, expected, actual, passed, source='auditforge/matcher.py'):
        checks.append(dict(name=name, requirement='Reward Robustness', seed=seed, inputs=inputs,
                           expected=expected, actual=actual, passed=passed, severity='high', source=source))

    def check(name, inputs, findings, tp, fp, fn, steps=0, target=episode):
        target_id = target['public']['manifest']['episode_id']
        payload = dict(episode_id=target_id, findings=findings)
        expected = reference_metrics(tp, fp, fn, steps)
        actual = evaluate(target_id, target['truth'], payload, steps)
        record(name, inputs, expected, actual, same_metrics(actual, expected))

    check('full-answer', 'All four correctly supported findings', correct, n, 0, 0)
    check('silence', 'Empty findings on erroneous books', [], 0, 0, n)
    check('clean-silence', 'Empty findings on clean books', [], 0, 0, 0, target=clean)
    check('clean-accusation', 'One finding on clean books', correct[:1], 0, 1, 0, target=clean)
    check('duplicate', 'Repeat every correct claim', correct + correct, n, n, 0)
    check('canonical-order', 'Reverse all affected and evidence IDs',
          [dict(f, affected_ids=f['affected_ids'][::-1], evidence_ids=f['evidence_ids'][::-1]) for f in correct], n, 0, 0)
    check('guess-affected', 'Replace affected IDs with unrelated IDs',
          [dict(f, affected_ids=['row-unrelated']) for f in correct], 0, n, n)
    check('guess-evidence', 'Invent IDs', [dict(f, evidence_ids=['doc-unrelated']) for f in correct], 0, n, n)
    check('partial-proof', 'Remove one required ID per finding',
          [dict(f, evidence_ids=f['evidence_ids'][:-1]) for f in correct], 0, n, n)
    check('cross-company', 'Use evidence sets from seed + 1',
          [dict(f, evidence_ids=t['evidence_sets'][0]) for f, t in zip(correct, foreign)], 0, n, n)
    check('wrong-denomination', 'Correct amount in USD instead of KZT',
          [dict(f, currency='USD') for f in correct], 0, n, n)
    check('wrong-category', 'Rotate issue types retaining amount',
          [dict(f, type=TYPES[(TYPES.index(f['type'])+1) % len(TYPES)]) for f in correct], 0, n, n)
    check('one-minor-unit', 'Add one minor unit outside zero tolerance',
          [dict(f, claimed_amount_minor=f['claimed_amount_minor']+1) for f in correct], 0, n, n)
    check('mark-all', 'Accuse every ledger row of each issue limited to first 30 claims',
          [dict(f, affected_ids=[r['row_id']], evidence_ids=[r['row_id']])
           for r in episode['public']['ledger'][:30] for f in correct][:30], 0, 30, n)
    check('inspection-cost', 'Submit full answer after 99 inspections', correct, n, 0, 0, steps=99)
    limits = {'31 findings': [correct[0]]*31, '11 evidence IDs': [dict(correct[0], evidence_ids=list(map(str, range(11))))],
              '1001 characters': [dict(correct[0], explanation='x'*1001)]}
    invalid = {**limits, 'boolean amount': [dict(correct[0], claimed_amount_minor=True)],
               'null findings': None, 'object IDs': [dict(correct[0], affected_ids={})]}
    rejected = [key for key, fs in invalid.items()
                if evaluate(eid, truth, dict(episode_id=eid, findings=fs), 0) ==
                dict(tp=0, fp=0, fn=n, precision=0, recall=0, f1=0, reward=-1, error='invalid_submission')]
    record('schema-and-limits', list(invalid), list(invalid), rejected, len(rejected) == len(invalid))

    action = dict(tool='submit', findings=dict(episode_id=eid, findings=correct))
    first, repeat = session.step(action), session.step(action)
    transition = [list(r[1:4]) for r in (first, repeat)]
    expected = [[1, True, False], [0, True, False]]
    record('repeat-submit', 'Submit the same valid answer twice', expected, transition, transition == expected,
           'auditforge/env.py')

    shared = dict(type=TYPES[0], currency='KZT', affected_ids=['a', 'b'])
    two_truths = [dict(shared, expected_amount_minor=100, evidence_sets=[[doc]]) for doc in ('A', 'B')]
    first_claim = dict(shared, claimed_amount_minor=100, evidence_ids=['A', 'B'], explanation='')
    padded = dict(first_claim, affected_ids=['b', 'a'], evidence_ids=['B', 'irrelevant', 'A'], explanation='New prose')
    for name, other, counts in [('ambiguous-repeat', padded, (1, 1, 1)),
                                ('ambiguous-distinct', dict(first_claim, evidence_ids=['A']), (2, 0, 0))]:
        actual = evaluate(eid, two_truths, dict(episode_id=eid, findings=[first_claim, other]), 4)
        expected = reference_metrics(*counts, 4)
        record(name, dict(truth=two_truths, findings=[first_claim, other]), expected, actual, same_metrics(actual, expected))
    failures = exhaustive_graphs()
    record('exhaustive-matching', 'Each 3x3 graph, bitmask 0..511, distinct claims, all partial assignments',
           [], failures, not failures)
    return dict(seed=seed, passed=all(c['passed'] for c in checks), checks=checks,
                passed_checks=sum(c['passed'] for c in checks), total_checks=len(checks), assignment_graphs=512)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=901405)
    result = run(parser.parse_args().seed)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
