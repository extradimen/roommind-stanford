"""Exercise archive preservation checks on isolated temporary evidence."""
import tempfile
import unittest
from pathlib import Path

from audit_research_archive import inventory, verify


class ArchiveTests(unittest.TestCase):
    def test_detects_modified_and_missing_evidence_without_changing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "research/experiments/old/transcript.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_bytes(b'{"frozen":true}\n')
            report = root / "docs/old.md"
            report.parent.mkdir()
            report.write_bytes(b"Original interpretation\n")
            saved = inventory(root)
            self.assertEqual(verify(root, saved), {
                "checked": 2, "missing": [], "changed": [], "passed": True,
            })
            # New additive documents do not invalidate old evidence.
            (report.parent / "addendum.md").write_bytes(b"Correction\n")
            self.assertTrue(verify(root, saved)["passed"])
            evidence.write_bytes(b'{"frozen":false}\n')
            report.unlink()
            result = verify(root, saved)
            self.assertFalse(result["passed"])
            self.assertEqual(result["missing"], ["docs/old.md"])
            self.assertEqual(result["changed"], ["research/experiments/old/transcript.json"])
            self.assertEqual(evidence.read_bytes(), b'{"frozen":false}\n')


if __name__ == "__main__":
    unittest.main()
