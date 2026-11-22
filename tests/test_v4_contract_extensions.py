"""The extended world must not perturb the official compact data stream."""
import hashlib
import json
import unittest

from auditforge.generator import generate


class CompactCompatibilityTests(unittest.TestCase):
    def test_three_frozen_v3_companies_are_byte_identical(self):
        cases = [
            (7109441, {}, '8ad3a3f06a36bf980212af394b311d382ed673dd414373d58ceaf2d0fc59bd6b'),
            (8191731, {'interaction': 2, 'timezone': '+05:45', 'invoices': 84}, '32bbf573226aeb12a8d683bbe0e9baea68dca05e4c81943f0a9f3fba9d06842b'),
            (6021391, {'clean': True}, 'f066b7854944e95c371440d7201385e440f15b1118f37e6402be669d281b9289'),
        ]
        for seed, config, expected in cases:
            episode = generate(seed, config)
            serialized = json.dumps(episode, sort_keys=True, separators=(',', ':')).encode()
            self.assertEqual(hashlib.sha256(serialized).hexdigest(), expected)

    def test_unknown_profile_is_rejected(self):
        for profile in (None, True, 1, 'unknown'):
            with self.assertRaises(ValueError):
                generate(810193, {'profile': profile})


if __name__ == '__main__':
    unittest.main()
