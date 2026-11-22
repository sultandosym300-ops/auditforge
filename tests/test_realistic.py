import unittest
from auditforge.realistic import generate_realistic, replay_business, change_customer_receipt
from auditforge.realistic_audit import audit_realistic
from auditforge.generator import generate
from auditforge.policies import run_policy
from auditforge.env import Session

class RealisticWorldTests(unittest.TestCase):
    def test_five_profiles_have_real_different_processes_and_independent_checks(self):
        signatures=[]
        for business in ('logistics','trade','manufacturing','it','services'):
            ep=generate_realistic(301,dict(profile='realistic_v1',business_type=business,invoices=40))
            check=audit_realistic(ep)
            self.assertTrue(check['valid'],check['errors'])
            pristine=dict(public=ep['pristine'],pristine=ep['pristine'],truth=[],provenance=[])
            self.assertTrue(audit_realistic(pristine)['valid'],audit_realistic(pristine)['errors'])
            self.assertEqual(ep['pristine']['business']['state']['bank_reconciliation_difference_minor'],0)
            world=ep['public']['business']
            self.assertTrue(world['reports']['balance_sheet']['balanced'])
            self.assertTrue(world['chains'])
            signatures.append(tuple(sorted(set(e['type'] for e in world['events']))))
        self.assertEqual(len(set(signatures)),5)

    def test_deterministic_and_no_public_private_mirror(self):
        config=dict(profile='realistic_v1',business_type='trade',invoices=40)
        a=generate_realistic(221,config);b=generate_realistic(221,config)
        self.assertEqual(a,b)
        self.assertNotEqual(a['public']['business']['journal'],a['pristine']['business']['journal'])
        self.assertNotIn('truth',a['public']['business'])
        self.assertFalse(any('expected' in key or 'pristine' in key for event in a['public']['business']['events'] for key in event))

    def test_clean_and_interactions_recover_original_four_types(self):
        for interaction in (0,1,2):
            for clean in (False,True):
                ep=generate_realistic(621,dict(profile='realistic_v1',business_type='it',invoices=40,interaction=interaction,clean=clean))
                self.assertTrue(audit_realistic(ep)['valid'])
                session=Session(); session.episode=ep;session.public=ep['public'];session.mode='evaluation';session.steps=0;session.done=False;session.done_flags=(False,False);session.report=None;session.final=[]
                import time
                session.started=time.monotonic();session.seconds=60
                initial=dict(manifest=ep['public']['manifest'],policy=ep['public']['policy'],steps_remaining=100)
                run_policy(session,initial,'reconciliation')
                self.assertEqual(session.report['f1'],1)
                self.assertEqual(bool(ep['truth']),not clean)

    def test_payment_counterfactual_replay_changes_cash_and_receivable(self):
        ep=generate_realistic(551,dict(profile='realistic_v1',business_type='services',invoices=40,clean=True))
        world=ep['public']['business']
        event=next(e for e in world['events'] if e['type']=='customer_receipt')
        before=replay_business(world['events'],world['journal'],world['as_of'])
        import copy
        changed=change_customer_receipt(world,event['event_id'],event['amount_minor']-100)
        after=replay_business(changed['events'],changed['journal'],changed['as_of'])
        self.assertEqual(after['accounts']['cash'],before['accounts']['cash']-100)
        self.assertEqual(after['accounts']['receivable'],before['accounts']['receivable']+100)
        other=copy.deepcopy(ep);other['public']['business']=changed
        self.assertTrue(audit_realistic(other)['valid'],audit_realistic(other)['errors'])
        self.assertEqual(next(e for e in world['events'] if e['event_id']==event['event_id'])['amount_minor'],event['amount_minor'])

    def test_private_cached_state_and_source_inventory_corruption_are_rejected(self):
        import copy
        ep=generate_realistic(517,dict(profile='realistic_v1',business_type='trade',invoices=40))
        bad=copy.deepcopy(ep);bad['pristine']['business']['state']['accounts']['cash']+=1
        self.assertFalse(audit_realistic(bad)['valid'])
        bad=copy.deepcopy(ep);bad['public']['business']['state']['inventory']['quantity']+=1
        self.assertFalse(audit_realistic(bad)['valid'])
        bad=copy.deepcopy(ep)
        for name in ('documents','source_documents'):
            next(d for d in bad['public']['business'][name] if d['type']=='bank_statement')['cash_delta_minor']+=1
        self.assertFalse(audit_realistic(bad)['valid'])

    def test_seed_varies_inventory_and_customer_payment_terms(self):
        terms=[]
        for seed in (11,12,13):
            world=generate_realistic(seed,dict(profile='realistic_v1',business_type='trade',invoices=40))['public']['business']
            terms.append((world['state']['inventory']['quantity'],tuple(e['payment_fraction_basis_points'] for e in world['events'] if e['type']=='customer_receipt')))
        self.assertEqual(len(set(terms)),3)

    def test_stock_cannot_be_sold_before_received_even_if_closing_balances_match(self):
        import copy
        ep=generate_realistic(819,dict(profile='realistic_v1',business_type='trade',invoices=40,clean=True))
        bad=copy.deepcopy(ep);world=bad['public']['business']
        event=next(e for e in world['events'] if e['type']=='trading_goods_sold')
        from datetime import datetime,timedelta
        earlier=(datetime.fromisoformat(world['period_start'])+timedelta(days=1)).isoformat()
        event['timestamp']=earlier
        for key in ('documents','source_documents'):
            for doc in world[key]:
                if doc['event_id']==event['event_id']:doc['timestamp']=earlier
        for row in world['journal']:
            if row.get('event_id')==event['event_id']:row['timestamp']=earlier
        self.assertFalse(audit_realistic(bad)['valid'])

    def test_corruption_of_context_journal_and_bank_is_rejected(self):
        import copy
        ep=generate_realistic(901,dict(profile='realistic_v1',business_type='manufacturing',invoices=40,clean=True))
        bad=copy.deepcopy(ep);bad['public']['business']['journal'][-1]['debit_minor']+=1
        self.assertFalse(audit_realistic(bad)['valid'])
        bad=copy.deepcopy(ep);bad['public']['business']['source_documents'][-1]['amount_minor']+=1
        self.assertFalse(audit_realistic(bad)['valid'])

if __name__=='__main__':unittest.main()
