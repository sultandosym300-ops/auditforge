import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.package_submission import prepare_tree
from scripts.submission_check import check_directory, check_archive
from scripts.run_baselines import evaluate_baseline


class SubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='submission-test-')
        cls.root=Path(cls.temporary.name)/'AuditForge'
        cls.result=prepare_tree(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_complete_content_replays_all_public_train_trajectories(self):
        self.assertTrue(self.result['passed'])
        self.assertEqual((self.result['train'],self.result['dev'],self.result['trajectory_runs']),(10,10,30))
        self.assertEqual(len(self.result['baseline_results']),4)
        self.assertEqual(check_directory(self.root)['trajectory_steps'],self.result['trajectory_steps'])

    def test_missing_and_changed_public_material_fail(self):
        path=next((self.root/'datasets/train/public').glob('*/manifest.json'))
        before=path.read_bytes()
        try:
            path.write_bytes(before+b' ')
            with self.assertRaisesRegex(ValueError,'Manifest digest'):check_directory(self.root)
            path.write_bytes(before)
            path.unlink()
            with self.assertRaisesRegex(ValueError,'Manifest file set'):check_directory(self.root)
        finally:path.write_bytes(before)

    def test_semantically_modified_trajectory_fails_even_without_hash_check(self):
        path=self.root/'trajectories/trajectories.jsonl';before=path.read_bytes()
        try:
            rows=[json.loads(s) for s in before.decode().splitlines()]
            rows[0]['observation']['steps_remaining']=7
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'Trajectory replay'):check_directory(self.root,verify_manifest=False)
            rows[0]['observation']['truth']=[]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'Private evaluator key'):check_directory(self.root,verify_manifest=False)
        finally:path.write_bytes(before)

    def test_incomplete_split_and_missing_trajectory_runs_fail(self):
        path=self.root/'configs/dev.json';before=path.read_bytes()
        try:
            value=json.loads(before);value['episodes'].pop();path.write_text(json.dumps(value),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'exactly ten'):check_directory(self.root,verify_manifest=False)
        finally:path.write_bytes(before)
        path=self.root/'trajectories/trajectories.jsonl';before=path.read_bytes()
        try:
            path.write_text('',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'Trajectories missing'):check_directory(self.root,verify_manifest=False)
        finally:path.write_bytes(before)

    def test_traversal_duplicate_and_cache_archives_fail_before_extraction(self):
        archive=Path(self.temporary.name)/'bad.zip'
        for name in ('../outside','/absolute','C:/absolute','AuditForge/__pycache__/fake.pyc'):
            with zipfile.ZipFile(archive,'w') as target:target.writestr(name,'unsafe')
            with self.assertRaises(ValueError):check_archive(archive)

    def test_oracle_requires_trusted_host_authorization(self):
        with self.assertRaisesRegex(ValueError,'trusted-evaluator'):evaluate_baseline(17,{},'oracle')
        self.assertEqual(evaluate_baseline(17,{},'oracle',allow_evaluator_oracle=True)['report']['f1'],1)


if __name__=='__main__':unittest.main()
