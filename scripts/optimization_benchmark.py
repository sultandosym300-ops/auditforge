"""Reproduce the frozen control and compare learned acquisition on unseen companies."""
import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import time
import tracemalloc
from unittest.mock import patch

from auditforge.env import Session
from auditforge.efficient_training import EfficientTrainer
from auditforge.policies import run_policy

ROOT = Path(__file__).resolve().parents[1]
CONTROL = '1db02796f95e78b4520c528727c45240d64ee6c0'
ROOT_SEED = 601384905227
TRAIN_SEEDS = (314159, 271828, 161803)
SCENARIOS = ('period', 'duplicate', 'fx', 'allocation', 'mixed', 'clean', 'recognition')
METRICS = ('precision', 'recall', 'f1', 'reward', 'steps', 'seconds')


def frozen_trainer():
    source = (ROOT/'scripts/controls/training_201.py').read_bytes().replace(bytes([13, 10]), bytes([10]))
    if hashlib.sha256(source).hexdigest() != '587ea51655afa4ddd763888a95dd73124d693a9ac6a6f0b2ae30d48ec4728585':
        raise RuntimeError('Frozen control source changed')
    module = {'__name__': 'auditforge.frozen_control', '__package__': 'auditforge'}
    exec(compile(source, 'controls/training_201.py', 'exec'), module)
    return module['Trainer']


def trial_seed(split, index):
    return int.from_bytes(hashlib.sha256(f'optimization-study-v1:{ROOT_SEED}:{split}:{index}'.encode()).digest()[:16], 'big')


def configuration(scenario, index):
    config = dict(invoices=40, timezone=('+05:45', '-03:30', '+14:00')[index % 3],
                  period_month=('2028-02', '2031-12')[index % 2], boundary_payments=True)
    if scenario == 'recognition':
        config['recognition_world'] = index % 4
    elif scenario == 'clean':
        config.update(clean=True, interaction=index % 3)
    elif scenario == 'mixed':
        config.update(clean=index % 5 == 0, interaction=index % 3)
    else:
        kind = dict(period='accounting_period', duplicate='duplicate_invoice', fx='fx_conversion', allocation='payment_allocation')[scenario]
        config.update(clean=index % 5 == 0, counts={kind: 2})
    return config


class PublicBoundary:
    def __init__(self, step, limit, eid):
        self._step, self.limit, self.eid = step, limit, eid
        self.steps, self.visible, self.errors = 0, set(), []
        self.terminal = None
        self.final = []

    def step(self, action):
        if self.terminal is not None:
            return self.terminal
        if self.steps >= self.limit-1 and action.get('tool') != 'submit':
            action = dict(tool='submit', findings=dict(episode_id=self.eid, findings=[]))
        if action.get('tool') == 'submit':
            self.final = action.get('findings', {}).get('findings', [])
            for finding in self.final:
                if not set(finding['affected_ids']+finding['evidence_ids']) <= self.visible:
                    self.errors.append('Unobserved evidence')
        observed = self._step(action)
        self.steps += 1
        obs = copy.deepcopy(observed[0])
        result = obs.get('result')
        if isinstance(result, dict):
            for record in result.get('records', [result]):
                if isinstance(record, dict):
                    identity = record.get('row_id') or record.get('doc_id')
                    if identity:
                        self.visible.add(identity)
        obs['steps_remaining'] = max(0, self.limit-self.steps)
        returned = (obs, *observed[1:])
        if observed[2] or observed[3]:
            self.terminal = returned
        if 'error' in obs:
            self.errors.append(obs['error'])
        return returned


def trial(model, seed, config, policy='trained', limit=100):
    session = Session()
    initial, _ = session.reset(seed, config, 'evaluation')
    access = PublicBoundary(session.step, limit, initial['manifest']['episode_id'])
    initial = dict(initial, steps_remaining=limit)
    start = time.perf_counter()
    if policy in ('random', 'reconciliation'):
        run_policy(access, initial, policy)
    else:
        model.run(access, initial)
    elapsed = time.perf_counter()-start
    if session.report is None or not session.done or access.errors:
        raise AssertionError((config, policy, access.errors))
    return dict(seed=seed, config=config, steps=session.steps, seconds=elapsed,
                submitted_findings=len(access.final), **{k:session.report[k] for k in ('tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'reward')})


def summarize(rows):
    rows = list(rows)
    result = dict(episodes=len(rows))
    for key in METRICS:
        values = [r[key] for r in rows]
        ordered = sorted(values)
        result[key] = dict(mean=statistics.mean(values), std=statistics.pstdev(values),
                           median=statistics.median(values), p90=ordered[max(0, math.ceil(.9*len(ordered))-1)],
                           minimum=min(values), maximum=max(values))
    result['pooled'] = {k:sum(r[k] for r in rows) for k in ('tp', 'fp', 'fn')}
    result['clean_false_findings'] = sum(r['fp'] for r in rows if r['config'].get('clean', False))
    result['complete_f1_episodes'] = sum(r['f1'] == 1 for r in rows)
    return result


def paired_uncertainty(rows):
    """Resample companies, keeping every training-seed prediction of a company together."""
    result = {}
    for scenario in SCENARIOS:
        selected = [r for r in rows if r['scenario'] == scenario]
        values = {(r['policy'], r['training_seed'], r['index']):r for r in selected}
        indices = sorted({r['index'] for r in selected})
        comparison = {}
        for metric in ('f1', 'reward', 'steps'):
            differences = [statistics.mean(values['candidate', seed, i][metric]-values['baseline', seed, i][metric]
                                           for seed in TRAIN_SEEDS) for i in indices]
            rng = random.Random(827410)
            estimates = sorted(statistics.mean(rng.choices(differences, k=len(indices))) for _ in range(1000))
            comparison[metric] = dict(candidate_minus_baseline=statistics.mean(differences),
                                      company_bootstrap_95=[estimates[24], estimates[974]])
        result[scenario] = comparison
    return result


def memory_profiles(Baseline, rate, episodes):
    result = []
    for name, cls in (('baseline', Baseline), ('candidate', EfficientTrainer)):
        tracemalloc.start()
        _, seconds = train_model(cls, 40931771, 'period', episodes, rate if name == 'candidate' else None)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        result.append(dict(policy=name, episodes=episodes, traced_seconds=seconds,
                           peak_python_allocated_bytes=peak,
                           scope='Separate measured training run; Python allocations, not process/browser RSS.'))
    return result


def train_model(cls, seed, scenario, episodes, learning_rate=None, shuffled_rewards=None):
    model = cls(seed, scenario) if learning_rate is None else cls(seed, scenario, learning_rate=learning_rate)
    start = time.perf_counter()
    original = Session.step
    rewards = iter(shuffled_rewards) if shuffled_rewards is not None else None
    def shuffled(session, action):
        observed = original(session, action)
        return (observed[0], next(rewards), *observed[2:]) if observed[2] or observed[3] else observed
    with patch.object(Session, 'step', shuffled if rewards else original):
        for _ in range(episodes):
            model.train_episode()
    return model, time.perf_counter()-start


def run(episodes=300, count=50):
    from auditforge.training import episode_seed
    Baseline = frozen_trainer()
    original, historical_seconds = train_model(Baseline, 314159, 'period', 300)
    result = dict(control_sha=CONTROL, root=ROOT_SEED, training_seeds=list(TRAIN_SEEDS), training_episodes=episodes,
                  historical_reproduction=original.evaluate(40, 70193), historical_training_seconds=historical_seconds,
                  rows=[], training=[], development=[], pareto=[], controls=[])
    result['source_sha256'] = {name:hashlib.sha256((ROOT/name).read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()
                              for name in ('auditforge/efficient_training.py', 'auditforge/generator.py', 'scripts/controls/training_201.py')}
    train_seeds = {episode_seed(seed, namespace, i) for seed in (*TRAIN_SEEDS, 219804133)
                   for namespace in ('train', 'efficient-train') for i in range(episodes)}
    test_seeds = {trial_seed('test:'+scenario, i) for scenario in SCENARIOS for i in range(count)}
    result['train_test_seed_overlap'] = len(train_seeds & test_seeds)
    if result['train_test_seed_overlap']:
        raise AssertionError('Training and test seeds overlap')
    # Select learning rate on independent development companies before evaluating test.
    choices = []
    for rate in (.1, .3, .6):
        model, seconds = train_model(EfficientTrainer, 219804133, 'mixed', episodes, rate)
        values = [trial(model, trial_seed('development-selection', i), configuration('mixed', i)) for i in range(30)]
        choices.append(dict(rate=rate, training_seconds=seconds, summary=summarize(values)))
    rate = max(choices, key=lambda row:row['summary']['reward']['mean'])['rate']
    result.update(development=choices, selected_learning_rate=rate)
    for seed in TRAIN_SEEDS:
        models = {}
        for scenario in ('period', 'mixed'):
            old, old_seconds = train_model(Baseline, seed, scenario, episodes)
            new, new_seconds = train_model(EfficientTrainer, seed, scenario, episodes, rate)
            models[scenario] = old, new
            result['training'].append(dict(seed=seed, scenario=scenario, baseline_seconds=old_seconds,
                                           candidate_seconds=new_seconds, baseline_checkpoint=old.checkpoint(), candidate_checkpoint=new.checkpoint()))
        before = {scenario:[model.checkpoint() for model in models[scenario]] for scenario in models}
        for scenario in SCENARIOS:
            task = 'period' if scenario in ('period', 'recognition') else 'mixed'
            old, new = models[task]
            for name, model in (('baseline', old), ('candidate', new), ('untrained', EfficientTrainer(seed, task)), ('random', None), ('reconciliation', None)):
                for i in range(count):
                    row = trial(model, trial_seed('test:'+scenario, i), configuration(scenario, i), policy=name if name in ('random', 'reconciliation') else 'trained')
                    row.update(scenario=scenario, policy=name, training_seed=seed, index=i)
                    result['rows'].append(row)
        if before != {scenario:[model.checkpoint() for model in models[scenario]] for scenario in models}:
            raise AssertionError('Evaluation mutated policy state')
        for budget in (45, 20, 15, 10, 8, 6, 5):
            values = [trial(models['period'][1], trial_seed('pareto-period', i), configuration('period', i), limit=budget) for i in range(count)]
            result['pareto'].append(dict(training_seed=seed, budget=budget, summary=summarize(values)))
        rewards = [row['reward'] for row in models['period'][1].history]
        random.Random(81923+seed).shuffle(rewards)
        shuffled, _ = train_model(EfficientTrainer, seed, 'period', episodes, rate, rewards)
        random_weights = EfficientTrainer(seed, 'period')
        weight_rng = random.Random(391005+seed)
        random_weights.weights = [weight_rng.uniform(-2, 2) for _ in random_weights.weights]
        for name, control in (('shuffled_reward', shuffled), ('frozen_initial', EfficientTrainer(seed, 'period')), ('random_weights', random_weights)):
            values = [trial(control, trial_seed('negative-control', i), configuration('period', i)) for i in range(count)]
            result['controls'].append(dict(training_seed=seed, name=name, summary=summarize(values),
                                           random_weights=list(control.weights) if name == 'random_weights' else None))
    result['summary'] = {scenario:{name:summarize(r for r in result['rows'] if r['scenario'] == scenario and r['policy'] == name)
                         for name in ('baseline', 'candidate', 'untrained', 'random', 'reconciliation')} for scenario in SCENARIOS}
    result['memory_profiles'] = memory_profiles(Baseline, rate, episodes)
    result['paired_uncertainty'] = paired_uncertainty(result['rows'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episodes', type=int, default=300)
    parser.add_argument('--count', type=int, default=50)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/optimization-benchmark.json')
    args = parser.parse_args()
    if not 1 <= args.episodes <= 5000 or not 1 <= args.count <= 200:
        parser.error('episodes must be 1..5000 and count must be 1..200')
    result = run(args.episodes, args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    with args.output.with_suffix('.csv').open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['training_seed', 'scenario', 'policy', 'index', 'seed', 'tp', 'fp', 'fn', *METRICS])
        writer.writeheader()
        writer.writerows({k:r[k] for k in writer.fieldnames} for r in result['rows'])
    print(json.dumps(dict(selected_learning_rate=result['selected_learning_rate'], summary=result['summary']), indent=2))


if __name__ == '__main__':
    main()
