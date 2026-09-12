"""Recovery binding remains explicit and cannot overwrite its predecessor."""
import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v3 import execution_binding


class FreshExecutionV3Tests(unittest.TestCase):
    def test_low_reasoning_and_failed_predecessor_are_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["reasoning_effort"], "low")
        self.assertEqual(value["predecessor_execution_sha256"], "b" * 64)
        self.assertEqual(value["dialogue_count"], 8)
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        specs = str(value["manifest"]["design"]["components"])
        self.assertIn("g5-ollama-http-v2", specs)
        self.assertIn("reasoning_effort", specs)

    def test_predecessor_checksum_is_required(self):
        for value in ("", "x" * 64, "a" * 63):
            with self.assertRaises(ValueError):
                execution_binding("a" * 40, authorization_id="x",
                                  predecessor_execution_sha256=value)


if __name__ == "__main__":
    unittest.main()
