import unittest

from auditforge.generator import generate
from auditforge.policies import run_policy
from auditforge.reconcile import reconcile
from auditforge.env import Session
from scripts.generator_probe import formula_rate_findings


class QuoteHistoryRegression(unittest.TestCase):
    def test_quotes_depend_on_company_history_and_formula_does_not_solve(self):
        episodes = [generate(seed, {"counts":{"fx_conversion":3}}) for seed in range(84561,84569)]
        def quotes(ep):
            return {(r["date"],r["source_currency"]):r["rate"] for r in ep["public"]["fx"]}
        self.assertNotEqual(quotes(episodes[0]), quotes(episodes[1]))
        self.assertTrue(any(formula_rate_findings(ep["public"]) !=
                            reconcile(ep["public"])
                            for ep in episodes))

    def test_actual_quotes_still_support_full_reconciliation(self):
        for seed in range(84561,84569):
            session=Session()
            initial,_=session.reset(seed,{"interaction":1},"evaluation")
            run_policy(session,initial)
            self.assertEqual(session.report["f1"],1)
