"""Fresh v6 freezes one repair contract across all structured interfaces."""
import unittest

from app.factorial_study import digest, verify_manifest
from app.g5.fresh_execution_v6 import execution_binding
from app.g5.structured_output import PROTOCOL


class FreshExecutionV6Tests(unittest.TestCase):
    def test_unified_repair_protocol_and_predecessor_are_hash_bound(self):
        value = execution_binding("a" * 40, authorization_id="test-authorization",
                                  predecessor_execution_sha256="b" * 64)
        verify_manifest(value["manifest"])
        self.assertEqual(value["reasoning_effort"], "low")
        self.assertEqual(value["max_structured_revisions"], 2)
        self.assertEqual(value["predecessor_execution_sha256"], "b" * 64)
        self.assertEqual(value["sha256"], digest({k: v for k, v in value.items()
                                                  if k != "sha256"}))
        design = value["manifest"]["design"]
        specs = [design["components"]["policy"], design["components"]["cognition"],
                 design["components"]["governance"], design["question_annotation"],
                 design["session_annotation"]]
        for spec in specs:
            self.assertEqual(spec["structured_repair"]["schema"], PROTOCOL)
            self.assertEqual(spec["structured_repair"]["max_revisions"], 2)


if __name__ == "__main__":
    unittest.main()
