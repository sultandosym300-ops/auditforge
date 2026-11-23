"""Frozen 2.2 study; company-cluster statistics never count model replicates as companies."""
import argparse
import csv
import hashlib
import json
import random
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def summarize(rows):
    counts = {key: sum(row[key] for row in rows) for key in ('tp', 'fp', 'fn')}
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    clean = [row for row in rows if row['clean']]
    return dict(runs=len(rows), independent_companies=len({row['company'] for row in rows}),
                macro_f1=statistics.mean(row['f1'] for row in rows),
                micro_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 1.,
                **counts, **{key: statistics.mean(row[key] for row in rows)
                             for key in ('reward', 'precision', 'recall', 'steps', 'seconds')},
                clean_companies=len({row['company'] for row in clean}),
                clean_fp=sum(row['fp'] for row in clean),
                clean_reward=statistics.mean(row['reward'] for row in clean) if clean else None)


def paired(rows, budget, left, right, metric, replicates, seed):
    groups = {}
    for row in rows:
        if row['budget'] == budget and row['policy'] in (left, right):
            groups.setdefault(row['company'], {}).setdefault(row['policy'], []).append(row[metric])
    differences = [statistics.mean(group[left])-statistics.mean(group[right]) for group in groups.values()]
    rng = random.Random(seed)
    samples = sorted(statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(replicates))
    return dict(budget=budget, left=left, right=right, metric=metric, companies=len(differences),
                difference=statistics.mean(differences), bootstrap_95=[samples[int(.025*replicates)], samples[int(.975*replicates)-1]],
                unit='company; checkpoint replicates averaged before resampling')


def source_snapshot(output):
    hashes = {}
    target = output/'source'
    target.mkdir(exist_ok=True)
    for file in sorted((ROOT/'auditforge').glob('*.py')):
        data = file.read_bytes().replace(b'\r\n', b'\n')
        (target/file.name).write_bytes(data)
        hashes[file.name] = hashlib.sha256(data).hexdigest()
    save(output/'source-sha256.json', hashes)


def export_csv(path, rows):
    with Path(path).open('w', encoding='utf8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_panel(spec, models, family, output):
    from auditforge.document_policy import investigate, CATEGORIES
    from auditforge.generator import generate
    from auditforge.training import episode_seed
    from scripts.final_policy_study import immutable_fixture
    policies = tuple(p for group in spec['baseline_groups'].values() for p in group)
    rows, fixtures = [], []
    for index in range(spec['test_companies']):
        seed = episode_seed(spec['test_root'], 'document-evaluation', index)
        config = models[0].config(index, family)
        episode = generate(seed, config)
        digest = hashlib.sha256(json.dumps(episode, sort_keys=True).encode()).hexdigest()
        fixtures.append(dict(company=index, seed=seed, config=config, sha256=digest, truth_count=len(episode['truth'])))
        for checkpoint, model in enumerate(models):
            for budget in spec['budgets']:
                for policy in policies:
                    session, initial = immutable_fixture(episode)
                    started = time.perf_counter()
                    investigate(session.step, initial, policy=policy, model=model.network,
                                budget=budget, blind_statistics=model.blind_statistics)
                    if session.steps > budget or not session.done or 'error' in session.report:
                        raise AssertionError('Invalid document benchmark run')
                    rows.append(dict(company=index, checkpoint=checkpoint, training_seed=model.seed,
                                     budget=budget, policy=policy, category=CATEGORIES[policy],
                                     clean=not episode['truth'], steps=session.steps,
                                     seconds=time.perf_counter()-started, **session.report))
        if hashlib.sha256(json.dumps(episode, sort_keys=True).encode()).hexdigest() != digest:
            raise AssertionError('Policy changed frozen company')
        if (index+1)%8 == 0:
            print(f'PANEL train={models[0].family} test={family} {index+1}/{spec["test_companies"]}', flush=True)
    summary = {str(b): {p:summarize([r for r in rows if r['budget']==b and r['policy']==p])
                       for p in policies} for b in spec['budgets']}
    comparisons = [paired(rows, b, 'learned', baseline, metric, spec['bootstrap']['resamples'], spec['bootstrap']['seed'])
                   for b in spec['budgets'] for baseline in policies if baseline != 'learned'
                   for metric in ('reward', 'f1')]
    value = dict(training_family=models[0].family, test_family=family, fixtures=fixtures,
                 rows=rows, summary=summary, paired=comparisons)
    save(output, value)
    export_csv(output.with_suffix('.csv'), rows)
    return {k:v for k,v in value.items() if k not in ('rows', 'fixtures')}


def train_family(spec, family, output):
    from auditforge.document_training import DocumentTrainer
    candidates, snapshots = [], {}
    for candidate_id, settings in enumerate(spec['candidates']):
        settings = {k:v for k,v in settings.items() if k!='name'}
        for seed in spec['training_seeds']:
            model = DocumentTrainer(seed, spec['selection_budget'], family=family, **settings)
            model.fit_blind(spec['train_episodes'])
            validations = {}
            for number in range(1, spec['train_episodes']+1):
                model.train_episode()
                if number in spec['checkpoint_episodes']:
                    model.flush()
                    validation = model.evaluate(spec['validation_companies'], spec['validation_root'], policies=('learned',))
                    checkpoint = model.checkpoint()
                    snapshots[(candidate_id,number,seed)] = checkpoint
                    validations[str(number)] = validation
                    save(output/f'{family}-candidate-{candidate_id}-seed-{seed}-ep-{number}.json',
                         dict(checkpoint=checkpoint, validation=validation))
                    print(f'TRAIN {family} candidate={candidate_id} seed={seed} episodes={number}', flush=True)
            candidates.append(dict(candidate=candidate_id, seed=seed, validations=validations))
    scores = []
    for candidate_id, settings in enumerate(spec['candidates']):
        for number in spec['checkpoint_episodes']:
            score = statistics.mean(row['validations'][str(number)]['results'][0]['reward']
                                    for row in candidates if row['candidate']==candidate_id)
            scores.append(dict(candidate=candidate_id, episode=number, reward=score,
                               architecture=settings['architecture']))
    chosen = max(scores, key=lambda r:(r['reward'], r['architecture']=='linear', -r['episode'], -r['candidate']))
    save(output/f'{family}-selection.json', dict(chosen=chosen, scores=scores, candidates=candidates,
                                               criterion=spec['selection']))
    models = [DocumentTrainer.from_checkpoint(snapshots[(chosen['candidate'], chosen['episode'], seed)])
              for seed in spec['training_seeds']]
    for i,model in enumerate(models):
        save(output/f'{family}-selected-{i}.json', model.checkpoint())
    return models, chosen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=ROOT/'configs/document-study-2.2.json')
    parser.add_argument('--output', type=Path, default=ROOT/'work/document-study-2.2')
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Preserve experiments: select a new empty output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    protocol=args.protocol.read_bytes();spec=json.loads(protocol)
    save(args.output/'protocol.json', dict(specification=spec, sha256=hashlib.sha256(protocol).hexdigest()))
    source_snapshot(args.output)
    models, selections = {}, {}
    for family in spec['families']:
        models[family], selections[family] = train_family(spec, family, args.output)
    # Both family selections are written before any final test company is opened.
    save(args.output/'selection-frozen-before-test.json', selections)
    transfer = {}
    for trained in spec['families']:
        transfer[trained] = {}
        for evaluated in spec['families']:
            transfer[trained][evaluated] = run_panel(spec, models[trained], evaluated,
                           args.output/f'{trained}-to-{evaluated}-raw.json')
    save(args.output/'summary.json', dict(protocol_sha256=hashlib.sha256(protocol).hexdigest(),
                                        selections=selections, transfer=transfer,
                                        note='Test companies are shared across model directions; checkpoints are repeated measurements, not independent companies.'))


if __name__ == '__main__':
    main()
