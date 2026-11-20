import unittest

from scripts.jury_blind import allocation_probe, probes, run


class PublicHoldoutTests(unittest.TestCase):
    def test_document_position_and_close_timestamp_are_insufficient(self):
        results = probes(918204040, 20)
        for name in ('first_invoice', 'close_timestamp'):
            self.assertGreater(results[name]['fn'], 0, name)
            self.assertGreater(results[name]['fp'], 0, name)

    def test_fixed_multiplier_cannot_recover_partial_allocations(self):
        result = allocation_probe(971467120, 18)
        self.assertLess(result['guessed'], result['total']//2)

    def test_all_claimed_evidence_is_read_within_budget(self):
        results = run(790124731, 6)
        self.assertEqual(results['passed'], 6, results['blind'])
        self.assertTrue(all(r['passed'] for r in results['dense']), results['dense'])
        self.assertEqual({(r['records'], r['documents'], r['issues']) for r in results['dense']},
                         {(200, 20, 0), (200, 20, 1), (2000, 200, 0), (2000, 200, 1)})

