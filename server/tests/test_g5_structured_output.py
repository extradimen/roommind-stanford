import unittest

from app.factorial_study import digest
from app.g5.structured_output import (StructuredOutputError, capsule, feedback,
                                      repair_spec, validate_failure)


class StructuredOutputTests(unittest.TestCase):
    def test_capsule_retains_rejected_body_and_machine_feedback(self):
        row = capsule("cognition.planning", 1, "a" * 64, '{"updates":[]}',
                      "Task transition needs observed evidence",
                      allowed_values=["event:1"])
        validate_failure(row)
        self.assertEqual(row["response_sha256"], digest(row["response_content"]))
        self.assertEqual(row["error_code"], "transition_evidence")
        self.assertEqual(row["field_path"], "$.updates[*].status_source_ids")
        note = feedback(row, 2)
        self.assertEqual(note["error"]["field_path"], row["field_path"])
        self.assertEqual(note["error"]["invariant"], "Task transition needs observed evidence")
        self.assertEqual(note["allowed_values"], ["event:1"])
        error = StructuredOutputError(row["message"], [row])
        self.assertEqual(error.structured_failures, [row])

    def test_revision_limit_is_bounded(self):
        self.assertEqual(repair_spec(2)["max_revisions"], 2)
        for value in (-1, 5, True, 1.5):
            with self.assertRaises(ValueError):
                repair_spec(value)

    def test_plan_identity_and_new_terminal_paths_are_precise(self):
        identity = capsule("cognition.planning", 0, "a" * 64, "{}",
                           "Task identity cannot silently change; retain old task and create a new one")
        terminal = capsule("cognition.planning", 1, "b" * 64, "{}",
                           "Do not retroactively create completed intentions")
        self.assertEqual((identity["error_code"], identity["field_path"]),
                         ("identity", "$.updates[*]"))
        self.assertEqual((terminal["error_code"], terminal["field_path"]),
                         ("transition", "$.updates[*].status"))


if __name__ == "__main__":
    unittest.main()
