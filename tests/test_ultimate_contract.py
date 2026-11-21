import unittest

from scripts.ultimate_contract import run


class UltimateContractRegression(unittest.TestCase):
    def test_json_errors_terminal_freeze_and_equivalent_instants(self):
        self.assertTrue(run()["passed"])
