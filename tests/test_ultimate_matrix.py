import unittest

from auditforge.financial_audit import audit_episode
from auditforge.generator import generate
from scripts.jury_batch import batch_company
from scripts.ultimate_matrix import investigate


class UltimatePublicSolvability(unittest.TestCase):
    def test_independent_public_reconstruction_of_compensated_world(self):
        for world in range(4):
            episode=generate(149873361,dict(recognition_world=world,timezone="-00:30",
                                           period_month="2000-02",invoices=40))
            self.assertTrue(audit_episode(episode)["valid"])
            result=investigate(episode,True)
            self.assertTrue(result["passed"],result)
            self.assertEqual(result["f1"],1)

    def test_dense_two_thousand_posting_case_fits_action_budget(self):
        episode=batch_company(441386987,100,True)
        self.assertEqual(len(episode["public"]["ledger"]),2000)
        self.assertEqual(episode["public"]["manifest"]["documents"],200)
        self.assertTrue(audit_episode(episode)["valid"])
        result=investigate(episode,True)
        self.assertTrue(result["passed"],result)
        self.assertEqual(result["steps"],47)