"""Reproducibility checks on configurable data and across fresh interpreters."""
import argparse
import hashlib
import json
import os
import random
import subprocess
import sys

from .generator import GENERATOR_VERSION, TYPES, generate
from .matcher import oracle
from .reconcile import reconcile, validate
from .verify import check_transitions, transform


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def fingerprint(episode):
    return hashlib.sha256(canonical(episode)).hexdigest()


def process_fingerprint(seed, config, hashseed):
    env = dict(os.environ, PYTHONHASHSEED=str(hashseed))
    result = subprocess.run(
        [sys.executable, '-m', 'auditforge.metamorphic', '--fingerprint', str(seed)],
        input=canonical(config), capture_output=True, env=env, check=True, timeout=30,
    )
    return result.stdout.decode('ascii').strip()


def run(seed, count):
    rng = random.Random(seed)
    subprocess_pairs = 0
    for i in range(count):
        episode_seed = rng.getrandbits(128)
        config = dict(
            clean=i % 7 == 0, interaction=i % 3, invoices=(40, 50, 84, 200)[i % 4],
            counts={kind: (i+j) % 4 for j, kind in enumerate(TYPES)},
            timezone=('-00:30', '+05:45', '+14:00', '-12:00')[i % 4],
            period_month=('2027-02', '2028-02', '2028-12', '2029-04')[i % 4],
            boundary_payments=i % 2 == 0,
        )
        try:
            episode = generate(episode_seed, config)
            assert canonical(episode) == canonical(generate(episode_seed, config))
            if i % 10 == 0:
                expected = fingerprint(episode)
                assert process_fingerprint(episode_seed, config, 1) == expected
                assert process_fingerprint(episode_seed, config, 4129) == expected
                subprocess_pairs += 1
            renamed, mapping = transform(episode, episode_seed+1, return_mapping=True)
            validate(episode)
            validate(renamed)
            for original, replacement in zip(oracle(episode)['findings'], oracle(renamed)['findings']):
                assert sorted(mapping[x] for x in original['affected_ids']) == sorted(replacement['affected_ids'])
                assert sorted(mapping[x] for x in original['evidence_ids']) == sorted(replacement['evidence_ids'])
                assert all(original[key] == replacement[key] for key in ('type', 'currency', 'claimed_amount_minor'))
            assert reconcile(renamed['public']) or not episode['truth']
            check_transitions(episode, renamed)
        except (AssertionError, ValueError) as error:
            raise AssertionError(f'Pair {i}, seed={episode_seed}, config={config}: {error}') from error
    return dict(version=GENERATOR_VERSION, root_seed=seed, paired_checks=count,
                clean_process_pairs=subprocess_pairs)


def main():
    if not __debug__:
        raise RuntimeError('Run verification without Python optimization')
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=917329138)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--fingerprint', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.fingerprint is not None:
        print(fingerprint(generate(args.fingerprint, json.load(sys.stdin))))
    else:
        if not 1 <= args.count <= 10000:
            parser.error('--count must be 1..10000')
        print(json.dumps(run(args.seed, args.count), sort_keys=True))


if __name__ == '__main__':
    main()
