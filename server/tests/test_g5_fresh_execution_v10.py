import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v10 import execution_binding


class FreshExecutionV10Tests(unittest.TestCase):
    def test_conservative_exhaustion_recovery_is_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["max_structured_revisions"], 3)
        self.assertEqual(value["recovery_reason"],
                         "conservative_plan_preservation_after_repair_exhaustion")
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        cognition = value["manifest"]["design"]["components"]["cognition"]
        self.assertEqual(cognition["plan_repair_exhaustion"], {
            "schema": "g5-conservative-plan-repair-exhaustion-v1",
            "action": "preserve-existing-plan", "requires_previous_plan": True})


if __name__ == "__main__":
    unittest.main()
