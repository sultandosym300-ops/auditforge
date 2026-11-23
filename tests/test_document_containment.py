import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from auditforge.agent_runner import container_command, run
from auditforge.document_policy import Network


class DocumentContainmentTests(unittest.TestCase):
    def test_image_retains_boundary_and_does_not_mount_host_data(self):
        command=container_command('document-test','document')
        self.assertEqual(command[-1],'auditforge-document-policy:2.2.0')
        for key,value in (('--network','none'),('--cap-drop','ALL'),('--security-opt','no-new-privileges'),
                          ('--memory','512m'),('--cpus','1'),('--pids-limit','64'),('--user','65534:65534')):
            self.assertEqual(command[command.index(key)+1],value)
        self.assertIn('--read-only',command)
        self.assertFalse({'-v','--volume','--mount','--privileged'} & set(command))

    def test_bad_models_rejected_before_any_process_launch(self):
        for parameters,budget,architecture in (([True]*len(Network().parameters),20,'linear'),
                                                ([math.nan],20,'linear'),([0],20,'mlp'),
                                                (Network().parameters,True,'linear'),
                                                (Network().parameters,20,'arbitrary')):
            with self.assertRaises(ValueError):
                run(1,policy='document',weights=parameters,budget=budget,architecture=architecture)
        with self.assertRaises(ValueError):
            run(1,isolated=False,policy='document',weights=Network().parameters,budget=20)

    def test_linear_and_mlp_inference_package_has_no_private_imports(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)/'auditforge';package.mkdir()
            for name in ('__init__.py','document_policy.py','documentary_decode.py'):
                (package/name).write_bytes((root/'auditforge'/name).read_bytes())
            code="import sys,importlib.util;sys.path.insert(0,sys.argv[1]);from auditforge.document_policy import Network;assert len(Network('mlp').parameters)>len(Network().parameters);assert all(importlib.util.find_spec('auditforge.'+n) is None for n in ('generator','env','matcher','document_world','document_training','independent_world'))"
            subprocess.run([sys.executable,'-I','-c',code,folder],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
