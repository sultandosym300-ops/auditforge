import unittest

from scripts.adversarial_logic import assignment_reference, matcher_trials, run


class AdversarialLogicTests(unittest.TestCase):
    def test_non_greedy_matcher_agrees_with_independent_permuted_assignments(self):
        self.assertEqual(assignment_reference([{0, 1}, {0}, {1, 2}, {2, 3}], 4), 4)
        rows = matcher_trials(3982006174, 80)
        self.assertTrue(all(row['passed'] for row in rows), [r for r in rows if not r['passed']])

    def test_identical_sources_support_clean_and_corrupted_counterparts(self):
        report = run(8917624451, 1)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['pairs']), 6)
        self.assertTrue(all(row['source_documents_identical'] for row in report['pairs']))


if __name__ == '__main__':
    unittest.main()