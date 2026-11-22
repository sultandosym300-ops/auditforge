"""Adversarial controls discovered independently from the world implementation."""
import copy
import unittest
from auditforge.generator import generate
from auditforge.realistic_audit import audit_realistic


class RealisticCachedStateTests(unittest.TestCase):
    def test_cached_financial_fields_cannot_disagree_with_source_events(self):
        original=generate(930571,{'profile':'realistic_v1','business_type':'manufacturing','invoices':40,'clean':True})
        self.assertTrue(audit_realistic(original)['valid'])
        cases=[('loan','interest_paid_minor'),('tax','rate_basis_points'),('payroll','employees')]
        for branch in ('public','pristine'):
            for group,field in cases:
                with self.subTest(branch=branch,field=field):
                    changed=copy.deepcopy(original)
                    changed[branch]['business']['state'][group][field]+=1
                    self.assertFalse(audit_realistic(changed)['valid'])
            for field in ('accumulated_depreciation_minor','disposed'):
                changed=copy.deepcopy(original)
                asset=changed[branch]['business']['state']['assets'][0]
                asset[field]=not asset[field] if field=='disposed' else asset[field]+1
                self.assertFalse(audit_realistic(changed)['valid'])


if __name__=='__main__':
    unittest.main()
