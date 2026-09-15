"""Bound scorer-v4 validation execution tests; no model or network calls."""
import unittest

from app.g5.fresh_execution_v15 import V14_GATE_RESULT_SHA, execution_binding
from app.g5.fresh_family_frame_v4 import fresh_family_frame_v4
from app.g5.fresh_family_roles_v4 import fresh_family_role_pack_v4
from app.g5.fresh_validation_plan_v4 import fresh_validation_plan_v4


class FreshExecutionV15Tests(unittest.TestCase):
    def test_binding_uses_new_material_and_reliable_structured_settings(self):
        value = execution_binding("a" * 40, authorization_id="fixture",
                                  predecessor_gate_result_sha256=V14_GATE_RESULT_SHA)
        self.assertEqual(value["schema"], "g5-fresh-family-v15-execution-binding-v1")
        self.assertEqual(value["frame_sha256"], fresh_family_frame_v4()["sha256"])
        self.assertEqual(value["role_pack_sha256"], fresh_family_role_pack_v4()["sha256"])
        self.assertEqual(value["validation_plan_sha256"], fresh_validation_plan_v4()["sha256"])
        self.assertEqual(value["reasoning_effort"], "low")
        self.assertEqual(value["max_structured_revisions"], 3)
        self.assertEqual(len(value["selected_assignments"]), 8)
        self.assertFalse(value["evaluation_authorized"])
        self.assertFalse(value["complete_block_screening_authorized"])

    def test_wrong_predecessor_or_revision_is_rejected(self):
        with self.assertRaises(ValueError):
            execution_binding("a" * 40, authorization_id="fixture",
                              predecessor_gate_result_sha256="0" * 64)
        with self.assertRaises(ValueError):
            execution_binding("branch", authorization_id="fixture",
                              predecessor_gate_result_sha256=V14_GATE_RESULT_SHA)


if __name__ == "__main__":
    unittest.main()
