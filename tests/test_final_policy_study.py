import unittest
import copy
import json
from auditforge.generator import generate
from auditforge.env import Session
from auditforge.policies import run_policy
from auditforge.efficient_training import investigate
from scripts.final_policy_study import PublicBudget, run_baseline, paired_interval, immutable_fixture, run_acquisition


class FinalPolicyStudyTests(unittest.TestCase):
    def test_shared_evaluator_fixture_returns_copies_without_private_fields(self):
        episode=generate(719834,{'invoices':40})
        before=copy.deepcopy(episode)
        session,initial=immutable_fixture(episode)
        observation,_,_,_,_=session.step(dict(tool='list_records',table='ledger',limit=1))
        observation['result']['records'][0]['debit_minor']+=100
        self.assertEqual(before,episode)
        for field in ('"truth"','"provenance"','"expected_amount_minor"'):
            self.assertNotIn(field,json.dumps(dict(initial=initial,observation=observation)))

    def test_full_budget_baselines_match_existing_policies(self):
        for policy in ('random','reconciliation'):
            original=Session();first,_=original.reset(719834,{'invoices':84,'interaction':2},'evaluation')
            run_policy(original,first,policy)
            budgeted=Session();second,_=budgeted.reset(719834,{'invoices':84,'interaction':2},'evaluation')
            run_baseline(PublicBudget(budgeted,100),second,policy)
            self.assertEqual(original.report,budgeted.report)
            self.assertEqual(original.steps,budgeted.steps)

    def test_small_budget_reserves_terminal_submit_and_cost_is_exact(self):
        for policy in ('random','reconciliation'):
            session=Session();initial,_=session.reset(719834,{'invoices':200},'evaluation')
            initial['steps_remaining']=5
            boundary=PublicBudget(session,5)
            run_baseline(boundary,initial,policy)
            self.assertEqual(session.steps,5)
            self.assertEqual(boundary.remaining,0)
            self.assertEqual(session.done_flags,(True,False))
            self.assertAlmostEqual(session.report['reward'],max(-1,min(1,2*session.report['f1']-1-.002*4)))

    def test_without_decoder_source_acquisition_cannot_create_correct_findings(self):
        session=Session();initial,_=session.reset(719834,{'invoices':40},'evaluation')
        run_acquisition(PublicBudget(session,100),initial,[20.]*21,remove_decoder=True)
        self.assertEqual(session.final['findings'],[])
        self.assertEqual(session.report['f1'],0)

    def test_bootstrap_counts_companies_instead_of_checkpoint_runs(self):
        rows=[]
        for company,delta in ((1,1.),(2,-1.)):
            for _ in range(5):
                for policy,value in (('trained',delta),('reconciliation',0.)):
                    rows.append(dict(company=company,budget=100,policy=policy,reward=value))
        result=paired_interval(rows,100)
        self.assertEqual(result['independent_company_clusters'],2)
        self.assertEqual(result['paired_difference'],0)
        self.assertEqual(result['bootstrap_95'],[-1.,1.])


if __name__=='__main__':unittest.main()
