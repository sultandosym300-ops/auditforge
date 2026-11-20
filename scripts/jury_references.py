"""Measure five controlled reference configurations against the same public-case rubric.

Run python -m scripts.jury_references from the repository root. Reference mutations
exist exclusively in disposable project/work directories. E uses unmodified source.
"""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = {
    'A': 'Minimal: fixed company books for each configuration, public API and four issue types.',
    'B': 'Shortcut-prone: an incorrect FX rate is always the correct rate plus seven.',
    'C': 'Weak evaluator: accepts a claim using only the affected IDs and type.',
    'D': 'Inconsistent truth: the first discrepancy in each dirty company is overstated by one minor unit.',
    'E': 'Current AuditForge, unmodified.',
}


def configure(folder, name):
    if name == 'E':
        return
    if name == 'C':
        path = folder / 'auditforge/matcher.py'
        with path.open('a', encoding='utf-8') as handle:
            handle.write("""
_strict_evaluate = evaluate

def evaluate(episode_id, truth, payload, inspection_steps):
    import copy
    payload = copy.deepcopy(payload)
    if valid(payload, episode_id):
        for finding in payload['findings']:
            for issue in truth:
                if finding['type'] == issue['type'] and set(finding['affected_ids']) == set(issue['affected_ids']):
                    finding.update(claimed_amount_minor=issue['expected_amount_minor'], currency=issue['currency'],
                                   evidence_ids=issue['evidence_sets'][0])
                    break
    return _strict_evaluate(episode_id, truth, payload, inspection_steps)
""")
        return
    path = folder / 'auditforge/generator.py'
    before, after = {
        'A': ('def generate(seed, config=None):',
              'def generate(seed, config=None):\n    seed = 1'),
        'B': ('wrong = rng.choice(candidates)', "wrong = str(Decimal(true_rate) + Decimal(7))"),
        'D': ('    return dict(public=public, truth=truth, provenance=provenance, pristine=pristine)',
              "    if truth:\n        truth[0]['expected_amount_minor'] += 1\n"
              '    return dict(public=public, truth=truth, provenance=provenance, pristine=pristine)'),
    }[name]
    source = path.read_text(encoding='utf-8')
    if source.count(before) != 1:
        raise RuntimeError(f'Reference {name}: replacement no longer identifies exactly one source location')
    path.write_text(source.replace(before, after), encoding='utf-8')


def measured_suite(pattern):
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern)
    out = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    if out.errors or out.testsRun != 20:
        raise RuntimeError(f'{pattern}: test infrastructure error: {out.errors} ({out.testsRun} checks)')
    return dict(passed=out.testsRun - len(out.failures), failed=[t.id() for t, _ in out.failures])


def evaluate_reference(name, seed, engineering):
    from auditforge.env import Session
    from auditforge.financial_audit import audit_episode
    from auditforge.generator import generate, TYPES
    from auditforge.matcher import evaluate, oracle
    from auditforge.shortcut import fingerprint_policy
    from auditforge.verify import transform

    contract = measured_suite('test_contract.py')
    reward = measured_suite('test_reward.py')
    cases = []
    rng = random.Random(seed)
    for index in range(20):
        case_seed = rng.getrandbits(112)
        config = dict(clean=index < 5, interaction=1 + index % 2 if 5 <= index < 10 else 0,
                      counts={t: 1 + (index + j) % 3 for j, t in enumerate(TYPES)})
        episode = generate(case_seed, config)
        repeat = generate(case_seed, config)
        independent = audit_episode(episode)
        original = oracle(episode)
        renamed, mapping = transform(episode, case_seed + 1, return_mapping=True)
        renamed_answer = oracle(renamed)
        mapped_answer = copy.deepcopy(original)
        mapped_answer['episode_id'] = mapping[original['episode_id']]
        for finding in mapped_answer['findings']:
            for key in ('affected_ids', 'evidence_ids'):
                finding[key] = [mapping[x] for x in finding[key]]
        reports = [evaluate(answer['episode_id'], data['truth'], answer, 2)
                   for data, answer in ((episode, original), (renamed, renamed_answer))]
        # Exercise the same concrete tool actions, including terminal train reward.
        replay = []
        for _ in range(2):
            session = Session()
            initial, info = session.reset(case_seed, config, 'train')
            events = [initial, info]
            for action in (dict(tool='list_records', table='ledger', limit=1),
                           dict(tool='calculator', expression='1.01 * 0.99'),
                           dict(tool='submit', findings=original)):
                events.append(session.step(action))
            replay.append(json.dumps(events, sort_keys=True, ensure_ascii=False))
        pair = (episode == repeat and replay[0] == replay[1]
                and mapped_answer == renamed_answer and reports[0] == reports[1])
        twin = generate(case_seed ^ 0x81251, config)
        different_books = episode['public']['ledger'] != twin['public']['ledger']
        # Score the dated-FX shortcut against the FX subset; other issue types are
        # outside its hypothesis. The policy receives only public tool responses.
        session = Session()
        initial, _ = session.reset(case_seed, config, 'evaluation')
        fingerprint_policy(session, initial)
        fx = [item for item in episode['truth'] if item['type'] == 'fx_conversion']
        fx_score = evaluate(original['episode_id'], fx, session.final, session.steps - 1)
        shortcut = bool(fx) and fx_score['f1'] == 1
        cases.append(dict(seed=case_seed, config=config, financial=independent['valid'],
                          errors=independent['errors'], repeat_and_pair=pair,
                          distinct_new_books=different_books, fx_fingerprint_tp=fx_score['tp'],
                          fx_fingerprint_fp=fx_score['fp'], fx_truth=len(fx), fx_shortcut_solves=shortcut))
    raw_data = sum(row['financial'] for row in cases)
    strict_data = sum(row['financial'] and row['distinct_new_books'] and
                      not row['fx_shortcut_solves'] for row in cases)
    groups = dict(contract=1.25 * contract['passed'], data=1.25 * raw_data,
                  reward=1.25 * reward['passed'],
                  reproducibility=.75 * sum(row['repeat_and_pair'] for row in cases),
                  engineering=engineering)
    strict = dict(groups, data=1.25 * strict_data)
    return dict(reference=name, description=REFERENCES[name], contract=contract, reward=reward,
                common_engineering_credit=engineering, cases=cases, rubric_points=groups,
                rubric_total=sum(groups.values()), stricter_points=strict, stricter_total=sum(strict.values()))


def run(seed, engineering):
    work = ROOT / 'work'
    work.mkdir(exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(dir=work, prefix='jury-references-') as tmp:
        for name in REFERENCES:
            folder = Path(tmp) / name
            for source in ('auditforge', 'tests', 'scripts'):
                shutil.copytree(ROOT / source, folder / source,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            configure(folder, name)
            proc = subprocess.run(
                [sys.executable, '-m', 'scripts.jury_references', '--worker', name,
                 '--seed', str(seed), '--engineering', str(engineering)],
                cwd=folder, env=dict(os.environ, PYTHONPATH=str(folder), PYTHONDONTWRITEBYTECODE='1'),
                capture_output=True, encoding='utf-8', timeout=120,
            )
            if proc.returncode:
                raise RuntimeError(f'{name}: {proc.stderr}')
            results[name] = json.loads(proc.stdout)
    expected = (results['C']['rubric_points']['reward'] < results['E']['rubric_points']['reward']
                and results['D']['rubric_points']['data'] < results['E']['rubric_points']['data']
                and results['A']['stricter_points']['data'] < results['E']['stricter_points']['data']
                and results['B']['stricter_points']['data'] < results['E']['stricter_points']['data'])
    return dict(seed=seed, passed=expected, references=results,
                engineering_basis='Common release artifacts, externally assessed. Default zero until reviewed.',
                stricter_basis='Add cross-seed ledger variation and exclusion of a perfect +7 FX fingerprint to each data check.',
                source='scripts/jury_references.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=984571127)
    parser.add_argument('--engineering', type=int, choices=range(11), default=0)
    parser.add_argument('--worker', choices=REFERENCES, help=argparse.SUPPRESS)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(evaluate_reference(args.worker, args.seed, args.engineering)))
        return
    result = run(args.seed, args.engineering)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: [ref['rubric_total'], ref['stricter_total']]
                      for key, ref in result['references'].items()}))
    if not result['passed']:
        raise SystemExit('Controlled defects did not separate as expected')


if __name__ == '__main__':
    main()
