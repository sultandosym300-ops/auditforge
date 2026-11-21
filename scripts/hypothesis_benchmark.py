"""Experimental learned acceptance: dev selection precedes untouched holdout."""
import copy
import json
from pathlib import Path
import random
import statistics
import time

from auditforge.efficient_training import EfficientTrainer, SCENARIOS
from auditforge.hypothesis_training import HypothesisTrainer
from auditforge.env import Session
from auditforge.training import episode_seed
from auditforge.counterfactual import challenge

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (314159, 271828, 161803, 141421, 173205)


def evaluate(model, seed, count, ablation=None):
    rows = []
    for scenario in SCENARIOS:
        config_model = EfficientTrainer(0, scenario)
        for index in range(count):
            session = Session()
            initial, _ = session.reset(episode_seed(seed, scenario, index), config_model.config(index), 'evaluation')
            started = time.perf_counter()
            if isinstance(model, HypothesisTrainer):
                model.run(session, initial, ablation=ablation)
            else:
                model.run(session, initial)
            rows.append(dict(scenario=scenario, company=index, seconds=time.perf_counter()-started,
                             steps=session.steps, **{k:session.report[k] for k in ('f1','precision','recall','reward','fp','fn')}))
    return rows


def aggregate(rows):
    steps = sorted(r['steps'] for r in rows)
    return dict(n=len(rows), **{k:statistics.mean(r[k] for r in rows) for k in ('f1','precision','recall','reward','fp','fn','seconds')},
                mean_steps=statistics.mean(steps), median_steps=statistics.median(steps), p90_steps=steps[int(.9*(len(steps)-1))])


def main():
    started = time.perf_counter()
    source = EfficientTrainer(SEEDS[0], 'mixed')
    for _ in range(300):
        source.train_episode()
    development = []
    # Dev company seeds never occur in training or holdout; selection fully recorded.
    for lr in (.02, .1, .3):
        model = HypothesisTrainer(SEEDS[0], 'mixed', source.weights, lr)
        for _ in range(1000):
            model.train_episode()
        development.append(dict(learning_rate=lr, **aggregate(evaluate(model, 884112, 12))))
    chosen = max(development, key=lambda r:(r['reward'], -r['learning_rate']))['learning_rate']
    report = dict(status='experimental-only', design='Four learned finding acceptance heads; fixed v2 acquisition, deterministic public arithmetic and top-four proposals per type.',
                  development=development, selected_learning_rate=chosen, train_episodes=1500,
                  holdout_seed=945820137, training_seeds=SEEDS, results=[], checkpoints=[])
    for seed in SEEDS:
        source = EfficientTrainer(seed, 'mixed')
        for _ in range(300):
            source.train_episode()
        learned = HypothesisTrainer(seed, 'mixed', source.weights, chosen)
        independent = HypothesisTrainer(seed, 'mixed', source.weights, chosen)
        train_start = time.perf_counter()
        for _ in range(1500):
            learned.train_episode()
            independent.train_episode(control='independent_reward')
        report['checkpoints'].append(learned.checkpoint())
        untrained = HypothesisTrainer(seed, 'mixed', source.weights, chosen)
        randomized = copy.deepcopy(learned)
        randomized.weights = [random.Random(episode_seed(seed, 'random-weight', i)).uniform(-2,2) for i in range(12)]
        for name, model, ablation in (('v2',source,None), ('learned_acceptance',learned,None),
                                      ('zero_features',learned,'zero_features'), ('untrained',untrained,None),
                                      ('random_weights',randomized,None), ('independent_reward',independent,None)):
            rows = evaluate(model, report['holdout_seed'], 20, ablation)
            report['results'].append(dict(seed=seed, model=name, aggregate=aggregate(rows),
                per_scenario={scenario:aggregate([r for r in rows if r['scenario']==scenario]) for scenario in SCENARIOS}, rows=rows))
        print(json.dumps(dict(seed=seed, seconds=time.perf_counter()-train_start)), flush=True)
    names = sorted({r['model'] for r in report['results']})
    report['summary'] = {name:aggregate([row for result in report['results'] if result['model']==name for row in result['rows']]) for name in names}
    report['decision'] = 'Reject production replacement: same acquisition cost, no benefit over v2; keep as isolated acceptance-learning experiment.'
    report['limitations'] = ['Discrepancy arithmetic and proposal ranking are hand engineered.',
                            'Training learns acceptance predicates, not arithmetic, hypothesis generation, evidence retrieval or stop decisions.',
                            'Precision and recall are zero for empty clean episodes under the unchanged evaluator; F1 is one.',
                            'Independent reward is uniform noise, not a permutation of observed rewards.',
                            'Five training seeds share company holdouts; pooled rows are not independent companies.']
    report['seconds'] = time.perf_counter()-started
    path = ROOT/'reports/hypothesis-acceptance-experiment.json'
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))


def paired_checkpoints():
    """Use already frozen candidates, with no retraining or holdout selection."""
    path = ROOT/'reports/hypothesis-acceptance-experiment.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    results = []
    for checkpoint in report['checkpoints']:
        model = HypothesisTrainer.from_checkpoint(checkpoint)
        trial = challenge(model, count=25, seed=2026112207, include_baselines=False, include_trajectories=False)
        results.append(dict(training_seed=checkpoint['seed'], challenge=trial))
    target = ROOT/'reports/hypothesis-counterfactual-experiment.json'
    target.write_text(json.dumps(dict(status='experimental-only', selection='All five frozen candidates, no tuning', results=results), indent=2), encoding='utf-8')
    print(json.dumps([dict(seed=r['training_seed'], metrics=r['challenge']['policies'][0]['metrics'], consistency=r['challenge']['policies'][0]['pair_consistency']) for r in results], indent=2))


if __name__ == '__main__':
    main()
