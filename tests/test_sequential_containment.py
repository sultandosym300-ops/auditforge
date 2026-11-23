import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from auditforge.agent_runner import container_command,run
from auditforge.sequential_policy import INITIAL_WEIGHTS


class SequentialContainmentTests(unittest.TestCase):
    def test_container_retains_every_safety_flag_and_rejects_bad_parameters(self):
        command=container_command('test-only','sequential')
        for flag in ('--network','--read-only','--cap-drop','--security-opt','--memory','--cpus','--pids-limit','--user'):
            self.assertIn(flag,command)
        self.assertEqual(command[-1],'auditforge-sequential-policy:1.0')
        with self.assertRaises(ValueError):container_command('name','unknown')
        for weights,budget in (([True]*len(INITIAL_WEIGHTS),10),(INITIAL_WEIGHTS,True),([0],10)):
            with self.assertRaises(ValueError):run(1,policy='sequential',weights=weights,budget=budget)

    def test_inference_package_imports_without_private_generator_or_evaluator(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)/'auditforge';package.mkdir()
            for name in ('__init__.py','sequential_policy.py','documentary_decode.py'):
                (package/name).write_bytes((root/'auditforge'/name).read_bytes())
            code="import sys; sys.path.insert(0,sys.argv[1]); from auditforge.sequential_policy import investigate; import importlib.util; assert importlib.util.find_spec('auditforge.generator') is None; assert importlib.util.find_spec('auditforge.env') is None; assert importlib.util.find_spec('auditforge.matcher') is None"
            subprocess.run([sys.executable,'-I','-c',code,folder],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
