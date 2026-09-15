import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v8 import execution_binding
from app.g5.structured_output import PROTOCOL


class FreshExecutionV8Tests(unittest.TestCase):
    def test_actor_excluding_repair_recovery_is_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["max_structured_revisions"], 3)
        self.assertEqual(value["recovery_reason"],
                         "exclude_actor_from_question_repair_targets")
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        design = value["manifest"]["design"]
        for spec in (design["components"]["policy"], design["components"]["cognition"],
                     design["components"]["governance"], design["question_annotation"],
                     design["session_annotation"]):
            self.assertEqual(spec["structured_repair"], {
                "schema": PROTOCOL, "max_revisions": 3,
                "rejected_content": "internal-attempt-journal-only"})


if __name__ == "__main__":
    unittest.main()
