"""Reproduce a five-training-seed paired holdout without tuning on test results."""
import argparse
import json
from pathlib import Path
import statistics
import time

from auditforge.counterfactual import challenge, surface_audit
from auditforge.efficient_training import EfficientTrainer

TRAIN_SEEDS = (314159, 271828, 161803, 141421, 173205)
HOLDOUT_SEED = 934177620531


def benchmark(episodes=300, pairs=25):
    trials = []
    started = time.monotonic()
    for seed in TRAIN_SEEDS:
        model = EfficientTrainer(seed, 'mixed')
        for _ in range(episodes):
            model.train_episode()
        result = challenge(model, pairs, HOLDOUT_SEED, include_trajectories=False)
        trials.append(dict(training_seed=seed, training_episodes=episodes,
                           optimizer_steps=model.checkpoint()['optimizer_steps'], challenge=result))
    summary = []
    for name in ('trained', 'random', 'reconciliation'):
        policies = [next(p for p in trial['challenge']['policies'] if p['name'] == name) for trial in trials]
        summary.append(dict(policy=name,
                            metrics={key:dict(mean=statistics.mean(p['metrics'][key] for p in policies),
                                              minimum=min(p['metrics'][key] for p in policies),
                                              maximum=max(p['metrics'][key] for p in policies))
                                     for key in ('precision', 'recall', 'f1', 'reward', 'steps', 'inspection_steps', 'median_steps', 'p90_steps')},
                            pair_consistency=statistics.mean(p['pair_consistency'] for p in policies)))
    return dict(study='auditforge-v3-paired-holdout', version=1, training_seeds=list(TRAIN_SEEDS),
                holdout_seed=HOLDOUT_SEED, training_episodes=episodes, pairs_per_seed=pairs,
                paired_episode_evaluations=2*pairs*len(TRAIN_SEEDS)*3,
                duration_seconds=time.monotonic()-started, summary=summary, trials=trials,
                surface_shortcut_screen=surface_audit(pairs, HOLDOUT_SEED),
                limitations=['All episodes come from the current generator; this does not prove out-of-distribution financial competence.',
                             'Learned gates select source acquisition; financial finding construction remains deterministic.',
                             'Five checkpoints share one frozen holdout panel; do not count these as independent companies.',
                             'Full-source reconciliation is a strong nonlearning baseline; matching it is not a learning breakthrough.',
                             'No official hackathon score or ranking is inferred.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episodes', type=int, default=300)
    parser.add_argument('--pairs', type=int, default=25)
    parser.add_argument('--output', type=Path, default=Path('reports/v3-paired-benchmark.json'))
    args = parser.parse_args()
    if not 0 <= args.episodes <= 10000 or not 5 <= args.pairs <= 100:
        parser.error('episodes must be 0..10000 and pairs 5..100')
    result = benchmark(args.episodes, args.pairs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'trials'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
