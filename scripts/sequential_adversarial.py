"""Bounded, reproducible adversarial audit; never trains or modifies sources.

python -m scripts.sequential_adversarial --output work/sequential-adversarial.json
The generated artifact belongs to the trusted evaluator, not the policy image.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

from auditforge.env import Session
from auditforge.generator import generate, TYPES
from auditforge.reconcile import reconcile
from auditforge.sequential_policy import investigate
from auditforge.training import episode_seed
from auditforge.verify import transform

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_KEYS = {'truth', 'provenance', 'pristine', 'seed',
                'expected_amount_minor', 'evidence_sets'}
POLICIES = ('reconciliation', 'budget_aware', 'greedy', 'heuristic_search', 'fixed_source')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def fixture(episode):
    """Trusted host fixture; only the copied observation and step reach policy."""
    session = Session()
    session.episode = episode
    session.public = episode['public']
    session.mode = 'evaluation'
    session.steps = 0
    session.done = False
    session.done_flags = (False, False)
    session.report = None
    session.started = time.monotonic()
    session.seconds = 60
    session.final = []
    return session, dict(manifest=copy.deepcopy(session.public['manifest']),
                         policy=copy.deepcopy(session.public['policy']), steps_remaining=100)


def run_policy(episode, policy, budget):
    session, initial = fixture(episode)
    acquired = set()
    checks = dict(no_private_fields=not (set(key for key, _ in walk(initial)) & PRIVATE_KEYS),
                  evaluation_reward_hidden=True, acquired_evidence_only=True,
                  budget_respected=True)
    def boundary(action):
        if action.get('tool') == 'submit':
            for finding in action['findings']['findings']:
                checks['acquired_evidence_only'] &= set(finding['evidence_ids']+finding['affected_ids']) <= acquired
        response = session.step(action)
        checks['evaluation_reward_hidden'] &= response[1] == 0 and response[4] == {}
        checks['no_private_fields'] &= not (set(key for key, _ in walk(response[0])) & PRIVATE_KEYS)
        acquired.update(value for key, value in walk(response[0])
                        if key in ('row_id', 'doc_id') and isinstance(value, str))
        checks['budget_respected'] &= session.steps <= budget
        return response
    result = investigate(boundary, initial, policy=policy, budget=budget)
    if not session.done or not result['terminal'][2] or 'error' in session.report:
        raise AssertionError('Policy did not submit a valid terminal finding set')
    return dict(policy=policy, budget=budget, steps=session.steps,
                inspections=session.steps-1, **session.report), checks


def minimum_costs(episode):
    public = episode['public']
    packets = {doc['case_id']: doc for doc in public['business']['source_documents'] if 'records' in doc}
    positive_cases = {case_id for case_id, packet in packets.items() if reconcile(packet['records'])}
    index = public['manifest']['investigations']
    # This is an exact witness lower bound only for the declared routed-packet
    # acquisition path, informed by evaluator-side knowledge of positive cases.
    return dict(minimum_route_witness_actions=1+sum(c['query_cost'] for c in index if c['case_id'] in positive_cases),
                complete_route_actions=1+sum(c['query_cost'] for c in index),
                complete_bulk_actions=1+sum((len(public[table])+49)//50 for table in ('ledger', 'invoices', 'payments', 'fx')),
                positive_departments=len(positive_cases))


def metadata_shortcut(episode):
    session, initial = fixture(episode)
    # Guesses use only the public index. No hidden amount, row ID or truth label
    # is supplied. A guessed document reference is not a proof of a discrepancy.
    guesses = [dict(type=kind, affected_ids=[case['case_id']], claimed_amount_minor=0,
                    currency=initial['manifest']['base_currency'],
                    evidence_ids=[case['document_id']], explanation='Metadata-only guess')
               for case in initial['manifest']['investigations'] for kind in TYPES]
    session.step(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=guesses)))
    guessed = dict(session.report)
    empty, initial = fixture(episode)
    empty.step(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=[])))
    return dict(guessed=guessed, empty=dict(empty.report), inspection_actions=0)


def permutation(episode, seed):
    changed = transform(episode, seed)
    rng = random.Random(seed)
    def shuffle(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('ledger', 'invoices', 'payments', 'fx', 'investigations') and isinstance(child, list):
                    rng.shuffle(child)
                shuffle(child)
        elif isinstance(value, list):
            for child in value:
                shuffle(child)
    shuffle(changed)
    return changed


def audit(seed=2026112307, count=6, cases=6, budgets=(5, 10, 100)):
    if (type(seed) is not int or type(count) is not int or not 1 <= count <= 100
            or type(cases) is not int or not 4 <= cases <= 6
            or not isinstance(budgets, (tuple, list)) or not budgets
            or any(type(b) is not int or not 2 <= b <= 100 for b in budgets)):
        raise ValueError('Invalid bounded audit configuration')
    rows, fixtures, shortcuts = [], [], []
    checks = dict(full_solve=True, zero_false_positives=True, no_private_fields=True,
                  evaluation_reward_hidden=True, acquired_evidence_only=True,
                  budget_respected=True, metadata_only_zero_tp=True,
                  fixtures_unchanged=True)
    metamorphic = dict(companies=0, full_budget_f1_changes=0, full_budget_false_positives=0,
                       low_budget_reward_changes=0, comparisons=[])
    for family in ('procurement', 'closing_transfer'):
        for clean in (False, True):
            for index in range(count):
                company_seed = episode_seed(seed, family+'-audit-'+str(clean), index)
                config = dict(profile='investigation_v1', cases=cases, family=family, clean=clean)
                episode = generate(company_seed, config)
                original_digest = digest(episode)
                company = f'{family}:{clean}:{index}'
                fixtures.append(dict(company=company, seed=company_seed, config=config,
                                     sha256=original_digest, truth_count=len(episode['truth']), **minimum_costs(episode)))
                for budget in sorted(set(budgets) | {100}):
                    for policy in POLICIES:
                        row, boundary_checks = run_policy(episode, policy, budget)
                        rows.append(dict(company=company, family=family, clean=not episode['truth'], **row))
                        for key, value in boundary_checks.items():
                            checks[key] &= value
                        checks['zero_false_positives'] &= row['fp'] == 0
                        if budget == 100:
                            checks['full_solve'] &= row['f1'] == 1
                shortcut = metadata_shortcut(episode)
                shortcuts.append(dict(company=company, **shortcut))
                checks['metadata_only_zero_tp'] &= shortcut['guessed']['tp'] == shortcut['empty']['tp'] == 0
                changed = permutation(episode, company_seed ^ 9157)
                metamorphic['companies'] += 1
                for budget in (min(budgets), 100):
                    original, _ = run_policy(episode, 'budget_aware', budget)
                    replacement, bounds = run_policy(changed, 'budget_aware', budget)
                    metamorphic['comparisons'].append(dict(company=company, budget=budget,
                        original_f1=original['f1'], transformed_f1=replacement['f1'],
                        original_reward=original['reward'], transformed_reward=replacement['reward']))
                    if budget == 100:
                        metamorphic['full_budget_f1_changes'] += original['f1'] != replacement['f1']
                        metamorphic['full_budget_false_positives'] += replacement['fp']
                    else:
                        metamorphic['low_budget_reward_changes'] += original['reward'] != replacement['reward']
                    for key, value in bounds.items():
                        checks[key] &= value
                checks['fixtures_unchanged'] &= original_digest == digest(episode)
    checks['full_solve'] &= metamorphic['full_budget_f1_changes'] == 0 and metamorphic['full_budget_false_positives'] == 0
    summary = []
    for family in ('procurement', 'closing_transfer'):
        for budget in sorted(set(row['budget'] for row in rows)):
            for policy in POLICIES:
                selected = [r for r in rows if (r['family'], r['budget'], r['policy']) == (family, budget, policy)]
                summary.append(dict(family=family, budget=budget, policy=policy, companies=len(selected),
                    **{key:statistics.mean(r[key] for r in selected) for key in ('reward', 'f1', 'steps')},
                    full_solve_fraction=statistics.mean(r['f1']==1 for r in selected)))
    sources = ('investigation_world.py', 'sequential_policy.py', 'documentary_decode.py', 'env.py', 'matcher.py')
    return dict(format='auditforge-sequential-adversarial-v1', seed=seed,
        independent_companies=len(fixtures), policy_runs=len(rows), checks=checks,
        fixtures=fixtures, rows=rows, summary=summary, metadata_shortcuts=shortcuts,
        metamorphic=metamorphic,
        source_sha256={name:hashlib.sha256((ROOT/'auditforge'/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for name in sources},
        action_cost_scope='Exact route witness minimum uses trusted positive-case membership; not a global minimum over mixed bulk/get_record/document strategies. Bulk count covers all table pages; full route count covers every department. Neither lower bound is supplied to a policy.',
        limitations=['No model is trained or selected by this audit.',
            'Two families share economic-book generation; transfer is a different period-injection mechanism, not a different bank.',
            'Metadata-only checks cover these explicit guessed and empty strategies, not all possible shortcuts.',
            'Equal-feature deterministic ties may change finite-budget choices under index permutation; their observed reward changes are retained.',
            'Native trusted fixture checks public protocol; Docker OS isolation is verified separately.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=2026112307)
    parser.add_argument('--count', type=int, default=6)
    parser.add_argument('--output', type=Path, default=ROOT/'work/sequential-adversarial.json')
    args = parser.parse_args()
    report = audit(seed=args.seed, count=args.count)
    report['created_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')
    print(json.dumps(dict(independent_companies=report['independent_companies'], policy_runs=report['policy_runs'],
                         checks=report['checks'], output=str(args.output)), ensure_ascii=True))
    if not all(report['checks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
