"""Fresh v4 binds bounded plan repair to the failed v3 predecessor."""
import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v4 import execution_binding


class FreshExecutionV4Tests(unittest.TestCase):
    def test_repair_protocol_and_predecessor_are_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["reasoning_effort"], "low")
        self.assertEqual(value["max_plan_revisions"], 2)
        self.assertEqual(value["predecessor_execution_sha256"], "b" * 64)
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        cognition = value["manifest"]["design"]["components"]["cognition"]
        self.assertEqual(cognition["plan_repair"]["max_revisions"], 2)


if __name__ == "__main__":
    unittest.main()
