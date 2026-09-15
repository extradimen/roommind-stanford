import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v12 import execution_binding as v12_execution_binding
from app.g5.fresh_execution_v13 import execution_binding
from app.g5.fresh_family_frame_v3 import fresh_family_frame_v3
from app.g5.fresh_family_roles_v3 import fresh_family_role_pack_v3
from app.g5.fresh_validation_plan_v3 import fresh_validation_plan_v3
from app.g5.structured_output import PROTOCOL


class FreshExecutionV13Tests(unittest.TestCase):
    def test_revision_budget_recovery_is_hash_bound_without_changing_materials(self):
        predecessor = "b" * 64
        old = v12_execution_binding("a" * 40,
                                    authorization_id="historical-v12-fixture")
        self.assertNotIn("reasoning_effort", old)
        self.assertNotIn("max_structured_revisions", old)

        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256=predecessor)
        verify_manifest(value["manifest"])
        self.assertEqual(value["schema"], "g5-fresh-family-v13-execution-binding-v1")
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
                         "restore_qualified_structured_revision_budget_for_untouched_families")
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        design = value["manifest"]["design"]
        for spec in (design["components"]["policy"], design["components"]["cognition"],
                     design["components"]["governance"], design["question_annotation"],
                     design["session_annotation"]):
            self.assertEqual(spec["structured_repair"], {
                "schema": PROTOCOL, "max_revisions": 3,
                "rejected_content": "internal-attempt-journal-only"})

    def test_predecessor_must_be_exact_sha256(self):
        for invalid in (None, "", "b" * 63, "B" * 64, "z" * 64):
            with self.assertRaises(ValueError):
                execution_binding("a" * 40, authorization_id="test",
                                  predecessor_execution_sha256=invalid)


if __name__ == "__main__":
    unittest.main()
