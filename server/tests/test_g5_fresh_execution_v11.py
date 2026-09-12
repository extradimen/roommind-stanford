import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v11 import execution_binding


class FreshExecutionV11Tests(unittest.TestCase):
    def test_governance_exhaustion_recovery_is_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        governance = value["manifest"]["design"]["components"]["governance"]
        self.assertEqual(governance["audit_repair_exhaustion"], {
            "schema": "g5-conservative-governance-repair-exhaustion-v1",
            "action": "reject-candidate-and-let-runtime-revise-or-wait"})


if __name__ == "__main__":
    unittest.main()
