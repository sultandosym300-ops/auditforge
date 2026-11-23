from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.package_submission import source_commit


class SubmissionUnicodeTests(unittest.TestCase):
    def test_utf8_git_path_retains_clean_commit_under_a_cp1251_host(self):
        # Git emits UTF-8 paths even when Python's Windows preferred encoding is
        # CP1251. Emulate that transport independently of the CI host locale/Git.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'проект';root.mkdir()
            sha='a'*40
            def git_path(args,**options):
                raw=(root.as_posix()+'\n').encode('utf8')
                return subprocess.CompletedProcess(args,0,raw.decode(options.get('encoding') or 'cp1251'))
            with patch('scripts.package_submission.subprocess.run',side_effect=git_path),patch(
                    'scripts.package_submission.subprocess.check_output',side_effect=[sha+'\n','']):
                self.assertEqual(source_commit(root),dict(commit=sha,dirty=False))


if __name__=='__main__':unittest.main()
