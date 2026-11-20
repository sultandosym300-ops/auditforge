import itertools
import random
import unittest
from fractions import Fraction

from auditforge.matcher import evaluate


def finding(i, evidence, amount=100):
    return dict(type='payment_allocation', affected_ids=[f'row-{i}'],
                claimed_amount_minor=amount, currency='KZT',
                evidence_ids=evidence, explanation='Synthetic test')


class JuryRewardTests(unittest.TestCase):
    def test_matching_reassigns_a_finding_to_keep_maximum_cardinality(self):
        truths = [
            dict(type='payment_allocation', affected_ids=['row-0'],
                 expected_amount_minor=100, currency='KZT', evidence_sets=[[item]])
            for item in ('rate-a', 'rate-b')
        ]
        findings = [finding(0, ['rate-a', 'rate-b']), finding(0, ['rate-a'])]
        for order in itertools.permutations(findings):
            score = evaluate('ep', truths, {'episode_id': 'ep', 'findings': list(order)}, 3)
            self.assertEqual((score['tp'], score['fp'], score['fn']), (2, 0, 0))
            self.assertAlmostEqual(score['reward'], .994)

    def test_repeated_ambiguous_claim_is_false_positive(self):
        common = dict(type='payment_allocation', affected_ids=['row-0', 'row-1'], currency='KZT')
        truths = [dict(common, expected_amount_minor=100, evidence_sets=[[doc]]) for doc in ('A', 'B')]
        first = dict(common, claimed_amount_minor=100, evidence_ids=['A', 'B'], explanation='')
        repeat = dict(first, affected_ids=['row-1', 'row-0'], evidence_ids=['B', 'unused', 'A'],
                      explanation='Different prose')
        for second in (first, repeat):
            score = evaluate('ep', truths, dict(episode_id='ep', findings=[first, second]), 0)
            self.assertEqual((score['tp'], score['fp'], score['fn'], score['reward']), (1, 1, 1, 0))

    def test_random_small_graphs_match_exhaustive_assignment(self):
        rng = random.Random(291072)
        for sample in range(1000):
            edges = [
                {j for j in range(4) if rng.getrandbits(1)}
                for _ in range(rng.randrange(6))
            ]
            truth = [
                dict(type='payment_allocation', affected_ids=['row-0'], currency='KZT',
                     expected_amount_minor=100, tolerance_minor=5, evidence_sets=[[f'rate-{j}']])
                for j in range(4)
            ]
            findings = [finding(0, [f'rate-{j}' for j in sorted(edge)], amount=100+i)
                        for i, edge in enumerate(edges)]
            # Exhaustively enumerate each assignment including the unmatched option.
            options = [(-1, *sorted(edge)) for edge in edges]
            best = 0
            for assignment in itertools.product(*options):
                matched = [j for j in assignment if j >= 0]
                if len(matched) == len(set(matched)):
                    best = max(best, len(matched))
            inspections = sample % 100
            score = evaluate('ep', truth, {'episode_id': 'ep', 'findings': findings}, inspections)
            self.assertEqual((score['tp'], score['fp'], score['fn']),
                             (best, len(findings)-best, 4-best), sample)
            f1 = Fraction(2*best, len(findings)+4)
            reward = max(-1, min(1, 2*f1 - 1 - Fraction(inspections, 500)))
            self.assertAlmostEqual(score['reward'], float(reward), msg=str(sample))

    def test_fuzz_json_types_and_extreme_amounts(self):
        rng = random.Random(5049)
        values = [None, False, True, [], {}, '', '0', -1, 1.25, 10**256]
        for _ in range(1000):
            value = rng.choice(values)
            field = rng.choice(('type', 'affected_ids', 'claimed_amount_minor', 'currency',
                                'evidence_ids', 'explanation'))
            data = finding(0, ['rate-0'])
            data[field] = value
            score = evaluate('ep', [], {'episode_id': 'ep', 'findings': [data]}, 0)
            self.assertEqual((score['tp'], score['f1'], score['reward']), (0, 0, -1))
            self.assertEqual(score['fp'], 0 if 'error' in score else 1)
