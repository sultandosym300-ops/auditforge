import unittest


class DocumentStudyTests(unittest.TestCase):
    def test_micro_and_macro_are_distinct_and_clean_fp_is_retained(self):
        from scripts.document_benchmark import summarize
        rows = [dict(company=0, checkpoint=0, reward=.9, f1=1., precision=1., recall=1.,
                     tp=1, fp=0, fn=0, steps=3, seconds=.01, clean=False),
                dict(company=1, checkpoint=0, reward=-1., f1=0., precision=0., recall=0.,
                     tp=0, fp=2, fn=0, steps=5, seconds=.02, clean=True)]
        got = summarize(rows)
        self.assertEqual(got['macro_f1'], .5)
        self.assertEqual(got['micro_f1'], .5)
        self.assertEqual(got['clean_fp'], 2)
        self.assertEqual(got['independent_companies'], 2)

    def test_bootstrap_averages_checkpoints_within_company(self):
        from scripts.document_benchmark import paired
        rows = []
        for company, differences in [(0, [1., 1., 1.]), (1, [-1.])]:
            for checkpoint, difference in enumerate(differences):
                for policy, reward in [('learned', difference), ('blind', 0.)]:
                    rows.append(dict(company=company, checkpoint=checkpoint, policy=policy,
                                     budget=20, reward=reward, f1=(reward+1)/2))
        result = paired(rows, 20, 'learned', 'blind', 'reward', 100, 3)
        self.assertEqual(result['companies'], 2)
        self.assertEqual(result['difference'], 0.)


if __name__ == '__main__':
    unittest.main()
