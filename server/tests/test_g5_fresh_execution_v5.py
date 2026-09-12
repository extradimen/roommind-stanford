"""Fresh v5 binds question repair to the failed v4 predecessor."""
import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v5 import execution_binding


class FreshExecutionV5Tests(unittest.TestCase):
    def test_both_repair_protocols_and_predecessor_are_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["reasoning_effort"], "low")
        self.assertEqual(value["max_plan_revisions"], 2)
        self.assertEqual(value["max_question_revisions"], 2)
        self.assertEqual(value["predecessor_execution_sha256"], "b" * 64)
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        design = value["manifest"]["design"]
        self.assertEqual(design["components"]["cognition"]["plan_repair"]["max_revisions"], 2)
        self.assertEqual(design["question_annotation"]["question_repair"]["max_revisions"], 2)


if __name__ == "__main__":
    unittest.main()
