"""Offline preflight for the authorized fresh-family execution binding."""
import copy
import unittest

from app.factorial_study import ARMS, digest, verify_manifest
from app.g5.fresh_execution_v2 import execution_binding


class FreshExecutionV2Tests(unittest.TestCase):
    def setUp(self):
        self.value = execution_binding("a" * 40, authorization_id="test-authorization")

    def test_exact_eight_balanced_selected_assignments_and_full_manifest(self):
        verify_manifest(self.value["manifest"])
        self.assertEqual(len(self.value["selected_assignments"]), 8)
        self.assertEqual({arm: sum(row["arm"] == arm for row in self.value["selected_assignments"])
                          for arm in ARMS}, {arm: 2 for arm in ARMS})
        self.assertEqual(len({row["scenario_id"] for row in self.value["selected_assignments"]}), 8)
        self.assertEqual(self.value["manifest"]["expected_dialogues"], 32)
        self.assertFalse(self.value["evaluation_authorized"])
        self.assertFalse(self.value["complete_block_screening_authorized"])

    def test_binding_contains_no_url_or_credential_and_is_checksummed(self):
        self.assertEqual(self.value["sha256"], digest({k: v for k, v in self.value.items()
                                                       if k != "sha256"}))
        self.assertNotIn("https://", str(self.value))
        self.assertNotIn("api_key", str(self.value).lower())
        self.assertFalse(self.value["credential_serialized"])

    def test_revision_and_authorization_are_required(self):
        with self.assertRaises(ValueError):
            execution_binding("main", authorization_id="x")
        with self.assertRaises(ValueError):
            execution_binding("a" * 40, authorization_id="")
        changed = copy.deepcopy(self.value)
        changed["model"] = "other"
        self.assertNotEqual(changed["sha256"], digest({k: v for k, v in changed.items()
                                                       if k != "sha256"}))


if __name__ == "__main__":
    unittest.main()
