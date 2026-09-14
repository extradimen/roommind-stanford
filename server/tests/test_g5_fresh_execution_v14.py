import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v14 import execution_binding
from app.g5.fresh_family_frame_v3 import fresh_family_frame_v3
from app.g5.fresh_family_roles_v3 import fresh_family_role_pack_v3
from app.g5.fresh_validation_plan_v3 import fresh_validation_plan_v3
from app.g5.structured_output import PROTOCOL


class FreshExecutionV14Tests(unittest.TestCase):
    def test_exact_annotation_feedback_recovery_is_hash_bound(self):
        predecessor = "b" * 64
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256=predecessor)
        verify_manifest(value["manifest"])
        self.assertEqual(value["schema"], "g5-fresh-family-v14-execution-binding-v1")
        self.assertEqual(value["predecessor_execution_sha256"], predecessor)
        self.assertEqual(value["reasoning_effort"], "low")
        self.assertEqual(value["max_structured_revisions"], 3)
        self.assertEqual(value["dialogue_count"], 8)
        self.assertEqual(value["max_steps"], 16)
        self.assertFalse(value["evaluation_authorized"])
        self.assertFalse(value["complete_block_screening_authorized"])
        self.assertEqual(value["frame_sha256"], fresh_family_frame_v3()["sha256"])
        self.assertEqual(value["role_pack_sha256"], fresh_family_role_pack_v3()["sha256"])
        self.assertEqual(value["validation_plan_sha256"], fresh_validation_plan_v3()["sha256"])
        self.assertEqual(value["recovery_reason"],
                         "exact_question_annotation_field_repair_feedback")
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
