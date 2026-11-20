import copy
import unittest
from datetime import datetime
from fractions import Fraction

from auditforge.financial_audit import audit_episode
from auditforge.generator import generate
from auditforge.matcher import evaluate, oracle


class MinimalEvidenceTests(unittest.TestCase):
    def score(self, episode, finding):
        eid = episode['public']['manifest']['episode_id']
        return evaluate(eid, episode['truth'], dict(episode_id=eid, findings=[finding]), 0)['tp']

    def test_oracle_edits_cannot_change_the_evaluator(self):
        episode = generate(44891, dict(interaction=2))
        original = copy.deepcopy(episode['truth'])
        answer = oracle(episode)
        for finding in answer['findings']:
            finding['affected_ids'].clear()
            finding['evidence_ids'].clear()
        self.assertEqual(episode['truth'], original)
        self.assertEqual(self.score(episode, answer['findings'][0]), 0)

    def test_refund_is_irrelevant_to_duplicate_expense_recognition(self):
        seen_refund = False
        for seed in range(44891, 44911):
            episode = generate(seed, dict(interaction=2))
            books = episode['public']
            for inv in books['invoices']:
                if not inv.get('related_credit_doc_id'):
                    continue
                rows = [r for r in books['ledger'] if r['account'] == 'expense' and
                        r['payment_id'] is None and r['invoice_id'] == inv['invoice_id']]
                if len(rows) != 2:
                    continue
                seen_refund = True
                affected = [r['row_id'] for r in rows]
                finding = dict(type='duplicate_invoice', currency=inv['currency'], affected_ids=affected,
                               claimed_amount_minor=sum(r['debit_minor'] for r in rows)-inv['total_minor'],
                               evidence_ids=[inv['doc_id'], *affected], explanation='')
                self.assertEqual(self.score(episode, finding), 1)
                for evidence_id in finding['evidence_ids']:
                    smaller = [item for item in finding['evidence_ids'] if item != evidence_id]
                    self.assertEqual(self.score(episode, dict(finding, evidence_ids=smaller)), 0)
                issue = next(t for t in episode['truth'] if t['type'] == 'duplicate_invoice')
                issue['evidence_sets'][0].append(inv['related_credit_doc_id'])
                self.assertFalse(audit_episode(episode)['valid'])
                return
        self.assertTrue(seen_refund, 'No duplicate with a linked refund was exercised')

    def test_allocation_proved_from_payment_posting_and_applicable_quote(self):
        currencies = set()
        for seed in range(589101, 589112):
            episode = generate(seed, dict(counts={'payment_allocation': 3}))
            books = episode['public']
            quotes = {(r['source_currency'], r['date']): r for r in books['fx']}
            payments = {p['payment_id']: p for p in books['payments']}
            exponents = books['manifest']['currency_exponents']
            base = books['manifest']['base_currency']
            for row in books['ledger']:
                if row['account'] != 'payable' or row['payment_id'] is None:
                    continue
                pay = payments[row['payment_id']]
                promised = next(ref['allocated_minor'] for ref in pay['invoice_refs']
                                if ref['invoice_id'] == row['invoice_id'])
                booked = row['allocation_source_minor']
                if promised == booked:
                    continue
                currency = pay['currency']
                currencies.add(currency)
                multiplier = Fraction(10) ** (exponents[base] - exponents[currency])
                evidence = [pay['doc_id'], row['row_id']]
                if currency != base:
                    zone = datetime.fromisoformat(books['manifest']['period_start']).tzinfo
                    date = datetime.fromisoformat(pay['timestamp']).astimezone(zone).date().isoformat()
                    quote = quotes[currency, date]
                    evidence.append(quote['row_id'])
                    multiplier *= Fraction(quote['rate'])
                difference = abs(round(promised * multiplier) - round(booked * multiplier))
                finding = dict(type='payment_allocation', currency=base, affected_ids=[row['row_id']],
                               claimed_amount_minor=difference, evidence_ids=evidence, explanation='')
                self.assertEqual(self.score(episode, finding), 1)
                for item in evidence:
                    self.assertEqual(self.score(episode, dict(finding, evidence_ids=[
                        evidence_id for evidence_id in evidence if evidence_id != item])), 0)
        self.assertIn('KZT', currencies)
        self.assertGreater(len(currencies), 1)
