import unittest

from auditforge.generator import generate
from auditforge.reconcile import validate,reconcile
from auditforge.matcher import evaluate


class BatchInvestigationTests(unittest.TestCase):
    def test_batch_payments_are_real_balanced_multi_obligation_sources(self):
        for seed in (41,81,171):
            episode=generate(seed,dict(profile='investigation_v1',family='batch_transfer',cases=4))
            self.assertTrue(validate(episode))
            payments=episode['public']['payments']
            self.assertTrue(any(len(p['invoice_refs'])>1 for p in payments))
            for payment in payments:
                self.assertEqual(sum(r['allocated_minor'] for r in payment['invoice_refs']),payment['amount_minor'])
            result=evaluate(episode['public']['manifest']['episode_id'],episode['truth'],
                            dict(episode_id=episode['public']['manifest']['episode_id'],findings=reconcile(episode['public'])),0)
            self.assertEqual(result['f1'],1)

    def test_clean_batch_company_has_no_false_claims(self):
        episode=generate(41,dict(profile='investigation_v1',family='batch_transfer',clean=True))
        self.assertTrue(validate(episode))
        self.assertEqual(reconcile(episode['public']),[])

    def test_batch_training_checkpoint_roundtrip(self):
        from auditforge.sequential_training import SequentialTrainer
        model=SequentialTrainer(seed=31,family='batch_transfer')
        model.train_episode()
        checkpoint=model.checkpoint()
        restored=SequentialTrainer.from_checkpoint(checkpoint)
        self.assertEqual(restored.family,'batch_transfer')
        self.assertEqual(restored.checkpoint(),checkpoint)


if __name__=='__main__':unittest.main()
