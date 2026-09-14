"""v16 recovery binding tests; no model or network calls."""
import unittest

from app.g5.fresh_execution_v16 import execution_binding
from app.g5.fresh_validation_plan_v4 import fresh_validation_plan_v4


class FreshExecutionV16Tests(unittest.TestCase):
    def test_recovery_is_bound_and_uses_four_structured_revisions(self):
        value = execution_binding("a" * 40, authorization_id="fixture",
                                  predecessor_execution_sha256="b" * 64)
        self.assertEqual(value["schema"], "g5-fresh-family-v16-execution-binding-v1")
        self.assertEqual(value["predecessor_execution_sha256"], "b" * 64)
        self.assertEqual(value["max_structured_revisions"], 4)
        self.assertEqual(value["validation_plan_sha256"], fresh_validation_plan_v4()["sha256"])
        self.assertFalse(value["evaluation_authorized"])
        self.assertFalse(value["complete_block_screening_authorized"])

    def test_invalid_predecessor_is_rejected(self):
        with self.assertRaises(ValueError):
            execution_binding("a" * 40, authorization_id="fixture",
                              predecessor_execution_sha256="not-a-hash")


if __name__ == "__main__":
    unittest.main()
