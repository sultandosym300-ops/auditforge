"""Run deliberately incorrect business/contract variants in disposable copies.

Usage: py -3.11 scripts/mutation_audit.py [--output reports/mutation-audit.json]
The canonical source is never mutated. Survivors, timeouts and infrastructure
errors fail the run; only an actual unittest failure/error kills a mutant.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ['-m', 'unittest', 'discover', '-s', 'tests', '-v']
MUTATIONS = (
    dict(id='interaction_fx_missing_mirror_provenance', file='auditforge/generator.py',
         description='Record only the affected payable row while mutating both settlement sides.',
         before="actual-expected, rows)", after="actual-expected)"),
    dict(id='reverse_currency_exponent', file='auditforge/generator.py',
         description='Reverse source and target currency exponent scaling.',
         before="EXPONENTS[target] - EXPONENTS[source]", after="EXPONENTS[source] - EXPONENTS[target]"),
    dict(id='counterfactual_book_uses_source_bit', file='auditforge/recognition_worlds.py',
         description='Assign journal dates from the source decision and erase the intended counterfactual discrepancy.',
         before="dates_by_bit[book_bit ^ index]", after="dates_by_bit[source_bit ^ index]"),

    dict(id='fx_rounding', file='auditforge/generator.py',
         description='Round FX conversions toward zero instead of half-even.',
         before='rounding=ROUND_HALF_EVEN))', after="rounding='ROUND_DOWN'))"),
    dict(id='loose_amount_tolerance', file='auditforge/matcher.py',
         description='Accept a one-minor-unit amount error.',
         before="<= t.get('tolerance_minor', 0)", after="<= t.get('tolerance_minor', 0) + 1"),
    dict(id='incorrect_true_positive', file='auditforge/matcher.py',
         description='Inflate the true-positive count by one.',
         before='tp = len(assigned)', after='tp = len(assigned) + 1'),
    dict(id='repeated_finding_double_count', file='auditforge/matcher.py',
         description='Count every matching submission, including repeated findings.',
         before='tp = len(assigned)', after='tp = sum(bool(matches) for matches in graph)'),
    dict(id='truth_in_observation', file='auditforge/env.py',
         description='Include evaluator truth in the reset observation.',
         before="policy=copy.deepcopy(self.public['policy']),",
         after="policy=copy.deepcopy(self.public['policy']), truth=self.episode['truth'],"),
    dict(id='inclusive_period_end', file='auditforge/reconcile.py',
         description='Include the exclusive period end in the reporting window.',
         before="start <= datetime.fromisoformat(row['timestamp']) < end",
         after="start <= datetime.fromisoformat(row['timestamp']) <= end", occurrences=2),
    dict(id='nondeterministic_generation', file='auditforge/generator.py',
         description='Ignore the supplied seed when initializing generation.',
         before='rng = random.Random(str(seed) + json.dumps(config, sort_keys=True))',
         after='rng = random.Random()'),
    dict(id='allow_101_steps', file='auditforge/env.py',
         description='Delay action-budget exhaustion until action 101.',
         before='if self.steps >= 100:', after='if self.steps >= 101:'),
    dict(id='wrong_evidence_id', file='auditforge/generator.py',
         description='Publish an invoice identifier where a document evidence ID is required.',
         before="evidence = [inv['doc_id'], original['row_id'], clones[0]['row_id']]",
         after="evidence = [inv['invoice_id'], original['row_id'], clones[0]['row_id']]"),
    dict(id='omitted_false_negative', file='auditforge/matcher.py',
         description='Drop unmatched truth entries from the false-negative count.',
         before='len(findings) - tp, len(truth) - tp', after='len(findings) - tp, 0'),
    dict(id='empty_truth_penalty', file='auditforge/matcher.py',
         description='Give an empty correct submission zero F1 on a clean company.',
         before='if 2*tp+fp+fn else 1', after='if 2*tp+fp+fn else 0'),
    dict(id='cursor_skips_record', file='auditforge/env.py',
         description='Skip one source record between every two consecutive pages.',
         before='next_cursor=str(offset+limit)', after='next_cursor=str(offset+limit+1)'),
    dict(id='incomplete_evidence', file='auditforge/matcher.py',
         description='Accept a single overlapping item from a mandatory evidence set.',
         before="evidence.issuperset(ids)", after="bool(evidence.intersection(ids))"),
    dict(id='repeat_submit', file='auditforge/env.py',
         description='Allow submit after an episode already terminated.',
         before='if self.done:', after="if self.done and action.get('tool') != 'submit':"),
    dict(id='unbalanced_clean_entry', file='auditforge/generator.py',
         description='Understate the invoice liability by one minor unit.',
         before="entry('payable', total, False, stamp, inv)", after="entry('payable', total-1, False, stamp, inv)"),
    dict(id='incorrect_clean_handling', file='auditforge/generator.py',
         description='Inject discrepancies even when clean generation was requested.',
         before="active = {} if config.get('clean', False) else dict(counts)",
         after='active = dict(counts)'),
)


EXPECTED_DETECTION = {
    'interaction_fx_missing_mirror_provenance': 'Causal replay must include both sides of every changed FX settlement.',
    'reverse_currency_exponent': 'JPY conversion must scale zero-exponent source to two-exponent base money correctly.',
    'counterfactual_book_uses_source_bit': 'Crossed source/book decisions must retain two independently provable period discrepancies.',

    'fx_rounding': 'Independent source-to-ledger conversion disagrees at a fractional minor unit.',
    'loose_amount_tolerance': 'An amount one minor unit beyond tolerance does not earn a TP.',
    'incorrect_true_positive': 'The evaluator cannot credit more matches than a complete correct answer contains.',
    'repeated_finding_double_count': 'Repeating an otherwise correct finding adds a false positive.',
    'truth_in_observation': 'Initial public observation contains a forbidden evaluator field.',
    'inclusive_period_end': 'An entry at the exclusive closing boundary is outside the period.',
    'nondeterministic_generation': 'Identical inputs must yield byte-equivalent financial episodes.',
    'allow_101_steps': 'The hundredth inspection truncates the episode.',
    'wrong_evidence_id': 'Every required evidence ID resolves to a sufficient public source.',
    'omitted_false_negative': 'An omitted true issue contributes exactly one FN.',
    'empty_truth_penalty': 'A clean company with no submitted findings earns F1=1.',
    'cursor_skips_record': 'Concatenated pages equal the full ordered source table.',
    'incomplete_evidence': 'Removing a necessary item from a finding eliminates its TP.',
    'repeat_submit': 'A second submit cannot produce new terminal reward.',
    'unbalanced_clean_entry': 'Independent bookkeeping rejects unequal debits and credits in the pristine journal.',
    'incorrect_clean_handling': 'A clean configuration produces zero discrepancies.',
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests(folder, timeout):
    start = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(folder),
               PYTHONIOENCODING='utf-8')
    try:
        result = subprocess.run([sys.executable, *COMMAND], cwd=folder, env=env,
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=timeout)
        output = result.stdout + result.stderr
        count = re.search(r'Ran (\d+) tests?', output)
        failures = re.findall(r'^(?:FAIL|ERROR): (.+)$', output, re.MULTILINE)
        # A failed import or test discovery is infrastructure failure, never a kill.
        infrastructure = '_FailedTest' in output or not count or int(count[1]) == 0
        if infrastructure:
            status = 'error'
        elif result.returncode == 0 and re.search(r'^OK(?:\s|$)', output, re.MULTILINE):
            status = 'passed'
        elif result.returncode != 0 and failures and 'FAILED (' in output:
            status = 'failed'
        else:
            status = 'error'
        return dict(status=status, returncode=result.returncode,
                    tests_run=int(count[1]) if count else 0,
                    failing_tests=failures, elapsed_seconds=round(time.monotonic()-start, 3),
                    output=output)
    except subprocess.TimeoutExpired as error:
        def decode(value):
            return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''
        return dict(status='timeout', returncode=None, tests_run=0, failing_tests=[],
                    elapsed_seconds=round(time.monotonic()-start, 3),
                    output=decode(error.stdout)+decode(error.stderr))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/mutation-audit.json')
    parser.add_argument('--timeout', type=float, default=180,
                        help='Maximum seconds per complete test run (default: 180).')
    parser.add_argument('--list', action='store_true', help='List mutations without running tests.')
    args = parser.parse_args()
    if args.list:
        print(json.dumps(MUTATIONS, indent=2))
        return 0
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    work = ROOT/'work'
    work.mkdir(exist_ok=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_dir = output.parent/(output.stem+'-logs')
    log_dir.mkdir(exist_ok=True)
    paths = sorted((ROOT/'auditforge').glob('*.py'))
    originals = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    report = dict(scope='Local business/accounting/contract mutation testing; not official grading.',
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  python=sys.version, command=['python', *COMMAND],
                  source_hashes=originals, baseline=None, mutations=[])
    # TemporaryDirectory owns a verified child of project/work, never a computed
    # user directory. All edits and cleanup apply only to this disposable tree.
    with tempfile.TemporaryDirectory(prefix='mutation-audit-', dir=work) as name:
        sandbox = Path(name).resolve()
        if sandbox.parent != work.resolve():
            raise RuntimeError('Mutation sandbox escaped project/work')
        template = sandbox/'template'
        template.mkdir()
        for directory in ('auditforge', 'tests', 'scripts'):
            shutil.copytree(ROOT/directory, template/directory,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        baseline = run_tests(template, args.timeout)
        (log_dir/'baseline.log').write_text(baseline.pop('output'), encoding='utf-8')
        report['baseline'] = baseline
        print(f"baseline: {baseline['status']} ({baseline['tests_run']} tests)", flush=True)
        if baseline['status'] == 'passed':
            for mutation in MUTATIONS:
                folder = sandbox/mutation['id']
                shutil.copytree(template, folder)
                target = folder/mutation['file']
                source = target.read_text(encoding='utf-8')
                expected = mutation.get('occurrences', 1)
                if source.count(mutation['before']) != expected:
                    result = dict(status='stale_target', tests_run=0,
                                  error=f'Expected {expected} exact replacement targets; found {source.count(mutation["before"])}')
                else:
                    changed = source.replace(mutation['before'], mutation['after'])
                    try:
                        compile(changed, mutation['file'], 'exec')
                    except SyntaxError as error:
                        result = dict(status='invalid_mutant', tests_run=0, error=str(error))
                    else:
                        target.write_text(changed, encoding='utf-8')
                        result = run_tests(folder, args.timeout)
                        log = log_dir/(mutation['id']+'.log')
                        log.write_text(result.pop('output'), encoding='utf-8')
                        result['log'] = str(log.relative_to(output.parent))
                        result['status'] = {'failed': 'killed', 'passed': 'survived'}.get(result['status'], result['status'])
                result.update(id=mutation['id'], file=mutation['file'],
                              description=mutation['description'], expected_detection=EXPECTED_DETECTION[mutation['id']])
                report['mutations'].append(result)
                print(f"{mutation['id']}: {result['status']}", flush=True)
    report['source_unchanged'] = all(digest(ROOT/path) == value for path, value in originals.items())
    report['killed'] = sum(row['status'] == 'killed' for row in report['mutations'])
    report['survivors'] = [row['id'] for row in report['mutations'] if row['status'] == 'survived']
    report['errors'] = [row['id'] for row in report['mutations'] if row['status'] not in ('survived', 'killed')]
    report['passed'] = (baseline['status'] == 'passed' and report['source_unchanged']
                        and report['killed'] == len(MUTATIONS))
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('killed', 'survivors', 'errors', 'source_unchanged', 'passed')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
