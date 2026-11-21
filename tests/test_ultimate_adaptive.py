import unittest

from scripts.ultimate_adaptive import collect, weak_findings


class AdaptiveBoundaryTests(unittest.TestCase):
    def test_prefix_policy_stops_before_next_cursor(self):
        calls = []
        def step(action):
            calls.append(action)
            self.assertEqual(action["tool"], "list_records")
            self.assertEqual(action["table"], "ledger")
            self.assertIsNone(action["cursor"])
            return (dict(result=dict(records=[], next_cursor="50")), 0, False, False, {})
        public = collect(dict(manifest={}, policy={}), step, "ledger_prefix")
        self.assertEqual(len(calls), 1)
        self.assertEqual(public["invoices"], [])

    def test_duplicate_template_requires_observed_source_document(self):
        rows = [dict(row_id=rid, account="expense", invoice_id="inv", debit_minor=100, currency="KZT")
                for rid in ("a", "b")]
        self.assertEqual(weak_findings(dict(ledger=rows, invoices=[]), "duplicate_invoice"), [])
        answer = weak_findings(dict(ledger=rows, invoices=[dict(invoice_id="inv", doc_id="doc")]),
                               "duplicate_invoice")
        self.assertEqual(answer[0]["evidence_ids"], ["a", "b", "doc"])
        self.assertEqual(answer[0]["affected_ids"], ["a", "b"])

    def test_sequential_policy_only_fetches_source_after_graph_candidate(self):
        calls = []
        rows = [dict(account="expense", invoice_id="inv") for _ in range(2)]
        def step(action):
            calls.append(action["table"])
            records = rows if action["table"] == "ledger" else [dict(invoice_id="inv")]
            return dict(result=dict(records=records, next_cursor="50")), 0, False, False, {}
        result = collect(dict(manifest={}, policy={}), step, "sequential")
        self.assertEqual(calls, ["ledger", "invoices"])
        self.assertEqual(len(result["invoices"]), 1)
