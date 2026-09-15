import copy
import json
from pathlib import Path
import tempfile
import unittest

from app.factorial_study import digest
from app.g5.local_handoff import create, verify, sources


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("server/app/g5/core.py", "server/app/factorial_study.py", "server/tests/test_factorial_study.py",
                     "research/experiments/old/frozen.json", "docs/G5_LOCAL_ACCEPTANCE_TEST.json"):
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("{}")
        self.path = "docs/G5_LOCAL_ACCEPTANCE_TEST.json"
        self.receipt = {"schema": "g5-local-acceptance-receipt-v1", "evidence_use": "synthetic-engineering-only",
            "qualification": "not_inferred", "engineering_checks_passed": True, "source_unchanged": True,
            "postgres_requested": True, "failures": [], "errors": [], "skipped": [], "unexpected_successes": [],
            "expected_failures": [], "tests": ["test.synthetic"], "tests_run": 1, "source_sha256": sources(self.root)}
        self.save()

    def save(self):
        raw = copy.deepcopy(self.receipt)
        (self.root / self.path).write_text(json.dumps({**raw, "sha256": digest(raw)}))

    def test_roundtrip_read_only_and_never_authorizes(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = verify(self.root, create(self.root, self.path))
        self.assertTrue(result["local_consistency_passed"])
        self.assertFalse(result["launch_authorized"])
        self.assertFalse(result["research_quality_verified"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_old_receipt_rejects_new_or_changed_source(self):
        new = self.root / "server/app/g5/new.py"; new.write_text("pass")
        with self.assertRaises(ValueError): create(self.root, self.path)
        new.unlink()
        (self.root / "server/app/g5/core.py").write_text("changed")
        with self.assertRaises(ValueError): create(self.root, self.path)

    def test_failed_or_skipped_receipts_and_duplicate_tests_rejected(self):
        original = copy.deepcopy(self.receipt)
        for key, value in (("skipped", ["test.synthetic"]), ("postgres_requested", False),
                           ("tests_run", 2), ("tests", ["a", "a"]), ("engineering_checks_passed", False)):
            self.receipt = {**copy.deepcopy(original), key: value}; self.save()
            with self.assertRaises(ValueError): create(self.root, self.path)

    def test_historical_deletion_change_and_addition_rejected(self):
        bundle = create(self.root, self.path)
        old = self.root / "research/experiments/old/frozen.json"
        old.write_text("changed")
        with self.assertRaises(ValueError): verify(self.root, bundle)
        old.unlink()
        with self.assertRaises(ValueError): verify(self.root, bundle)
        old.write_text("{}")
        (old.parent / "added.json").write_text("{}")
        with self.assertRaises(ValueError): verify(self.root, bundle)

    def test_forged_authority_and_symlink_rejected(self):
        bundle = create(self.root, self.path); bundle["launch_authorized"] = True
        bundle["sha256"] = digest({k: v for k, v in bundle.items() if k != "sha256"})
        with self.assertRaises(ValueError): verify(self.root, bundle)
        (self.root / "research/experiments/link").symlink_to(self.root / "docs")
        with self.assertRaises(ValueError): create(self.root, self.path)


if __name__ == "__main__": unittest.main()
