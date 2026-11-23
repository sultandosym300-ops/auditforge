"""Differential properties against an independently enumerated small-task judge."""
import copy
import itertools
import random
import unittest

from auditforge.generator import generate
from auditforge.matcher import evaluate
from auditforge.reference_evaluator import evaluate_reference


def claim(evidence=None, amount=100, **overrides):
    result = dict(type='payment_allocation', affected_ids=['row-0'],
                  claimed_amount_minor=amount, currency='KZT',
                  evidence_ids=['doc-a'] if evidence is None else evidence,
                  explanation='Independent fixture')
    result.update(overrides)
    return result


def truth(evidence=None, amount=100, **overrides):
    result = dict(type='payment_allocation', affected_ids=['row-0'],
                  expected_amount_minor=amount, currency='KZT',
                  evidence_sets=[['doc-a']] if evidence is None else evidence)
    result.update(overrides)
    return result


class ReferenceEvaluatorTests(unittest.TestCase):
    def compare(self, truths, findings, inspections=0):
        payload = dict(episode_id='ep', findings=findings)
        expected = evaluate_reference('ep', truths, payload, inspections)
        actual = evaluate('ep', truths, payload, inspections)
        self.assertEqual(set(actual), set(expected))
        for key, value in expected.items():
            if isinstance(value, float):
                self.assertAlmostEqual(actual[key], value, places=12, msg=key)
            else:
                self.assertEqual(actual[key], value, key)
        return actual

    def test_evidence_tolerance_currency_and_false_claims(self):
        truths = [truth([['A', 'B'], ['C']], tolerance_minor=1)]
        variants = [claim(['A']), claim(['A', 'B']), claim(['C']),
                    claim(['A', 'B', 'irrelevant']), claim(['C'], amount=101),
                    claim(['C'], amount=102), claim(['C'], currency='USD'),
                    claim(['C'], affected_ids=['forged']),
                    claim(['C'], type='accounting_period')]
        for variant in variants:
            with self.subTest(variant=variant):
                self.compare(truths, [variant], 17)

    def test_conflicting_matches_duplicates_and_all_permutations(self):
        truths = [truth([[doc]]) for doc in ('A', 'B', 'C')]
        first = claim(['A', 'B'])
        repeated = dict(first, evidence_ids=['irrelevant', 'B', 'A'], explanation='Changed prose')
        findings = [first, repeated, claim(['A']), claim(['B', 'C'])]
        for order in itertools.permutations(findings):
            result = self.compare(truths, list(order), 3)
            self.assertEqual((result['tp'], result['fp'], result['fn']), (3, 1, 0))

    def test_seeded_small_random_problem_properties(self):
        rng = random.Random(2026112301)
        for _ in range(700):
            truths = [truth([[f'doc-{j}']], amount=100+rng.randrange(3),
                            tolerance_minor=rng.randrange(2)) for j in range(rng.randrange(6))]
            findings = [claim([f'doc-{j}' for j in range(6) if rng.random()<.4],
                              amount=99+rng.randrange(5),
                              currency=rng.choice(['KZT']*4+['USD']))
                        for _ in range(rng.randrange(8))]
            if findings and rng.random()<.35:
                findings.append(copy.deepcopy(rng.choice(findings)))
            self.compare(truths, findings, rng.randrange(101))

    def test_arbitrary_json_payloads_never_inflate_score(self):
        rng = random.Random(2026112302)
        values = [None, True, False, [], {}, '', 'bad', -1, 0, 1.5, 10**200]
        keys = ['type', 'affected_ids', 'evidence_ids', 'claimed_amount_minor', 'currency', 'explanation']
        for _ in range(500):
            finding = claim()
            finding[rng.choice(keys)] = rng.choice(values)
            self.compare([truth()], [finding], rng.randrange(101))
        for payload in values + [dict(episode_id='wrong', findings=[]), dict(episode_id='ep', findings=[claim()]*31)]:
            self.assertEqual(evaluate('ep', [truth()], payload, 0),
                             evaluate_reference('ep', [truth()], payload, 0))

    def test_generated_financial_tasks_and_mutated_claims(self):
        for seed in range(12):
            episode = generate(seed, {'clean': seed%5==0, 'interaction': seed%3})
            claims = [dict(type=t['type'], affected_ids=list(t['affected_ids']),
                           claimed_amount_minor=t['expected_amount_minor'], currency=t['currency'],
                           evidence_ids=list(t['evidence_sets'][0]), explanation='Independent conversion')
                      for t in episode['truth']]
            self.compare(episode['truth'], claims, 12)
            if claims:
                changed = copy.deepcopy(claims)
                changed[0]['claimed_amount_minor'] += 1
                self.compare(episode['truth'], changed, 12)
                self.compare(episode['truth'], claims+[copy.deepcopy(claims[0])], 12)

    def test_clean_and_action_cost_exactly(self):
        for inspections in (0, 1, 10, 99, 100):
            score = self.compare([], [], inspections)
            self.assertAlmostEqual(score['reward'], 1-inspections/500)
        self.assertEqual(self.compare([truth()], [], 0)['reward'], -1)

    def test_reference_explicitly_bounds_exponential_audit(self):
        with self.assertRaises(ValueError):
            evaluate_reference('ep', [truth()]*17, dict(episode_id='ep', findings=[]), 0)

