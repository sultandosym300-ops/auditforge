import json
from pathlib import Path
import tempfile
import unittest
from auditforge.export import export_episode
from auditforge.generator import generate
from auditforge.proof import transform_for_proof, _session_for
from auditforge.policies import run_policy
from auditforge.realistic_audit import audit_realistic


class RealisticExportTests(unittest.TestCase):
    def test_export_separates_observed_world_and_pristine_evaluator_state(self):
        episode=generate(821070,{'profile':'realistic_v1','business_type':'trade','invoices':40})
        eid=episode['public']['manifest']['episode_id']
        with tempfile.TemporaryDirectory() as folder:
            export_episode(episode,folder)
            public=Path(folder)/'public'/eid
            world=json.loads((public/'business.json').read_text(encoding='utf8'))
            self.assertEqual(world,episode['public']['business'])
            private=Path(folder)/'evaluator_private'/eid
            self.assertEqual(json.loads((private/'pristine_business.json').read_text(encoding='utf8')),episode['pristine']['business'])
            for file in public.iterdir():
                text=file.read_text(encoding='utf8')
                for field in ('"truth"','"provenance"','"expected_amount_minor"'):
                    self.assertNotIn(field,text)

    def test_compact_export_has_no_extended_files(self):
        episode=generate(821070,{'invoices':40})
        with tempfile.TemporaryDirectory() as folder:
            export_episode(episode,folder)
            self.assertFalse(list(Path(folder).rglob('business.json')))
            self.assertFalse(list(Path(folder).rglob('pristine_business.json')))

    def test_renaming_and_permutation_preserve_business_graph_and_scoring(self):
        for business in ('logistics','trade','manufacturing','it','services'):
            episode=generate(821070,{'profile':'realistic_v1','business_type':business,'invoices':40,'interaction':2})
            changed=transform_for_proof(episode,783109)
            self.assertTrue(audit_realistic(changed)['valid'])
            reports=[]
            for fixture in (episode,changed):
                session,initial=_session_for(fixture)
                run_policy(session,initial,'reconciliation')
                reports.append(session.report)
            self.assertEqual(reports[0],reports[1])


if __name__=='__main__':
    unittest.main()
