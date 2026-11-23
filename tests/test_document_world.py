import json
import unittest
from unittest.mock import patch

from auditforge.generator import generate
from auditforge.env import Session
from auditforge.financial_audit import audit_episode
from auditforge.documentary_decode import decode
from auditforge.matcher import evaluate


class DocumentWorldTests(unittest.TestCase):
    def test_both_families_have_independent_valid_financial_histories(self):
        for family in ('procurement', 'service_milestone'):
            for seed in range(12):
                with self.subTest(family=family, seed=seed):
                    config = dict(profile='investigation_v2', family=family, cases=4)
                    episode = generate(seed, config)
                    self.assertEqual(episode, generate(seed, config))
                    result = audit_episode(episode)
                    self.assertTrue(result['valid'], result['errors'])
                    public = episode['public']
                    score = evaluate(public['manifest']['episode_id'], episode['truth'],
                                     dict(episode_id=public['manifest']['episode_id'], findings=decode(public)), 0)
                    self.assertEqual(score['f1'], 1)

    def test_one_action_exposes_one_source_and_complete_acquisition_fits_budget(self):
        for family in ('procurement', 'service_milestone'):
            session = Session()
            initial, _ = session.reset(713, dict(profile='investigation_v2', family=family), 'train')
            index = initial['manifest']['document_index']
            self.assertLess(len(index), 100)
            recovered = dict(manifest=initial['manifest'], policy=initial['policy'], ledger=[], invoices=[], payments=[], fx=[])
            for entry in index:
                observation, _, ended, truncated, _ = session.step(dict(tool='get_document', doc_id=entry['document_id']))
                self.assertFalse(ended or truncated)
                document = observation['result']
                self.assertLessEqual(len(document['records']), 1)
                self.assertLessEqual(sum(map(len, document['records'].values())), 2)
                for table, rows in document['records'].items():
                    recovered[table].extend(rows)
            session.step(dict(tool='submit', findings=dict(episode_id=initial['manifest']['episode_id'], findings=decode(recovered))))
            self.assertEqual(session.report['f1'], 1)

    def test_bulk_table_requests_cannot_bypass_document_cost(self):
        session = Session()
        session.reset(1, dict(profile='investigation_v2'), 'train')
        result = session.step(dict(tool='list_records', table='ledger', limit=50))[0]
        self.assertLessEqual(len(result['result']['records']), 2)
        self.assertEqual(session.steps, 1)

    def test_clean_world_has_no_findings_or_private_observation_fields(self):
        for family in ('procurement', 'service_milestone'):
            session = Session()
            initial, _ = session.reset(37, dict(profile='investigation_v2', family=family, clean=True), 'train')
            self.assertEqual(session.episode['truth'], [])
            self.assertEqual(decode(session.public), [])
            for forbidden in ('truth', 'provenance', 'pristine', 'expected_amount_minor'):
                self.assertNotIn(forbidden, json.dumps(initial))

    def test_invalid_configuration_is_rejected(self):
        for patch in (dict(cases=True), dict(cases=5), dict(family='bad'), dict(clean='yes'), dict(secret=True)):
            with self.assertRaises(ValueError):
                generate(1, dict(profile='investigation_v2', **patch))

    def test_service_economics_do_not_call_procurement_construction(self):
        with patch('auditforge.document_world.procurement_events', side_effect=AssertionError('shared procurement economics')):
            episode = generate(121, dict(profile='investigation_v2', family='service_milestone'))
        self.assertTrue(audit_episode(episode)['valid'])

    def test_nine_source_kinds_and_normal_structural_variation(self):
        required={'contract','invoice','payment','bank_confirmation','journal_entry',
                  'exchange_quote','refund','allocation_document','fulfillment_confirmation'}
        for family in ('procurement','service_milestone'):
            counts=set()
            for seed in range(20):
                episode=generate(seed,dict(profile='investigation_v2',family=family,clean=True))
                index=episode['public']['manifest']['document_index']
                self.assertEqual({d['kind'] for d in index},required)
                counts.add(sum(d['kind']=='journal_entry' for d in index))
            # Extra journal sources are not a deterministic duplicate-error flag.
            self.assertGreater(len(counts),1)


if __name__ == '__main__':
    unittest.main()
