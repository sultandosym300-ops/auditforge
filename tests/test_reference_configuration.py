from pathlib import Path
import tempfile
import unittest

from scripts.jury_references import configure


class ReferenceConfigurationTests(unittest.TestCase):
    def test_fixed_seed_reference_targets_the_current_generator_signature(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'auditforge';target.mkdir()
            source=(root/'auditforge/generator.py').read_text(encoding='utf8')
            (target/'generator.py').write_text(source,encoding='utf8')
            configure(Path(folder),'A')
            changed=(target/'generator.py').read_text(encoding='utf8')
            self.assertIn('*, _quote_seed=None',changed)
            self.assertEqual(changed.replace('\n    seed = 1','',1),source)


if __name__=='__main__':unittest.main()
