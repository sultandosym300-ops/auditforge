import unittest

from scripts.ultimate_evidence import fixed_reward_cases, matcher_cases, run


class UltimateEvidenceTests(unittest.TestCase):
    def test_twenty_independent_reward_expectations(self):
        checks = fixed_reward_cases(318879406124)
        self.assertEqual(len(checks), 20)
        self.assertTrue(all(c["passed"] for c in checks), checks)

    def test_proof_local_reconstruction_and_necessary_records(self):
        report = run(root=318879406122, count=6, graphs=20)
        self.assertTrue(report["passed"])
        kinds = {c["type"] for c in report["proof_cases"]}
        self.assertEqual(kinds, {"duplicate_invoice", "payment_allocation", "fx_conversion", "accounting_period"})

    def test_small_exact_assignments_with_alternative_proofs(self):
        checks = matcher_cases(62700541398, 100)
        self.assertTrue(all(c["passed"] for c in checks), checks)
