"""Declared lineage, durable intake and tamper controls; no real calibration."""
import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_g5_annotation_archive as fixtures
from app.factorial_study import digest
from app.g5.family_registry import FamilyRegistry, holdout_audit, verify_export
from app.g5.material_intake import prepare_review, verify_bundle

WHO = {"id": "local-script", "kind": "synthetic"}

def family(name, parents=None):
    return {"id": "family-" + name, "kind": "family", "family_id": name, "parents": parents or [],
            "provenance": {"author": WHO, "artifact_sha256": digest(name)}}

def material(name, snapshot):
    return {"id": "material-" + name, "kind": "material", "family_id": name,
            "snapshot_sha256": snapshot, "provenance_sha256": digest(name)}

def exposure(name):
    return {"id": "use-" + name, "kind": "exposure", "families": [name], "purpose": "development",
            "observer": WHO, "artifact_sha256": digest(name)}

def register(registry, manifest):
    seen = set()
    for scenario in manifest["design"]["scenarios"]:
        name = scenario["family"]
        if name not in seen:
            registry.append(family(name)); seen.add(name)
        event = material(name, scenario["snapshot_sha256"])
        event["id"] += "-" + scenario["id"]
        registry.append(event)

class RegistryTests(unittest.TestCase):
    def test_lineage_siblings_exact_relabel_and_stale_snapshot(self):
        r = FamilyRegistry(":memory:", "fixture"); self.addCleanup(r.close)
        for event in [family("root"), family("child", ["root"]), family("sibling", ["root"]), family("alias"),
                      material("root", digest("shared")), exposure("child")]: r.append(event)
        before = r.export()
        self.assertFalse(holdout_audit(before, ["sibling"])["registered_exposure_free"])
        self.assertTrue(holdout_audit(before, ["alias"])["registered_exposure_free"])
        r.append(material("alias", digest("shared")))
        self.assertFalse(holdout_audit(r.export(), ["alias"])["registered_exposure_free"])
        with self.assertRaises(ValueError): holdout_audit(r.export(), ["alias"], expected_snapshot_sha256=before["sha256"])
        self.assertFalse(holdout_audit(before, ["alias"])["launch_authorized"])

    def test_reconnect_idempotency_conflict_and_immutability(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "registry.db")
            r = FamilyRegistry(path, "fixture"); r.append(family("a")); old = r.export(); r.close()
            r = FamilyRegistry(path, "fixture"); self.addCleanup(r.close)
            r.append(family("a")); self.assertEqual(old, r.export())
            bad = family("a"); bad["provenance"]["artifact_sha256"] = digest("changed")
            with self.assertRaises(ValueError): r.append(bad)
            with self.assertRaises(sqlite3.IntegrityError): r.db.execute("DELETE FROM family_events")
            self.assertEqual(old, r.export())

    def test_invalid_events_and_rehashed_chain_tamper(self):
        r = FamilyRegistry(":memory:", "fixture"); self.addCleanup(r.close)
        for event in [family("a", ["a"]), material("unknown", digest("x")), exposure("unknown")]:
            with self.assertRaises(ValueError): r.append(event)
        r.append(family("a")); exported = r.export()
        exported["events"][0]["family_id"] = "b"
        exported["sha256"] = digest({k:v for k,v in exported.items() if k != "sha256"})
        with self.assertRaises(ValueError): verify_export(exported)
        for names in ([{}], ["a", "a"], []):
            with self.assertRaises(ValueError): holdout_audit(r.export(), names)

    def test_process_loss_before_and_after_commit(self):
        with tempfile.TemporaryDirectory() as d:
            for committed in (False, True):
                path = str(Path(d) / str(committed))
                r = FamilyRegistry(path, "fixture"); r.close()
                script = """import os,sys,json
from app.g5.family_registry import FamilyRegistry
r=FamilyRegistry(sys.argv[1], 'fixture')
if sys.argv[2]=='False':
    r.db.set_trace_callback(lambda sql: os._exit(75) if sql=='COMMIT' else None)
r.append(json.loads(sys.argv[3]))
os._exit(74)
"""
                result = subprocess.run([sys.executable, "-c", script, path, str(committed), json.dumps(family("a"))])
                self.assertEqual(result.returncode, 74 if committed else 75)
                r = FamilyRegistry(path, "fixture")
                self.assertEqual(len(r.export()["events"]), int(committed))
                r.append(family("a")); self.assertEqual(len(r.export()["events"]), 1); r.close()

class IntakeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.AnnotationTests.asyncSetUp(self)
        self.registry = FamilyRegistry(":memory:", "intake-fixture")
        self.addCleanup(self.registry.close)
        register(self.registry, self.manifest)
        self.intake = {"id": "review-1", "observer": WHO, "source_kind": "synthetic",
                       "sampling": "constructed", "provenance_sha256": digest("fixture")}

    def prepare(self):
        return prepare_review(self.registry, self.manifest, self.sources, self.frozen, self.intake)

    async def test_full_panel_durable_exposure_replay_and_unlabelled_tasks(self):
        bundle = self.prepare()
        self.assertEqual(verify_bundle(bundle)["tasks"], 24)
        self.assertEqual(bundle, self.prepare())
        self.assertEqual(bundle["reference_labels"], "not_collected")
        for task in bundle["review_tasks"]:
            self.assertEqual(set(task), {"schema", "classification", "case_id", "dimension", "rubric", "context", "turns", "sha256"})
        self.assertFalse(holdout_audit(self.registry.export(), bundle["exposure"]["families"])["registered_exposure_free"])

    async def test_conflicting_intake_and_tampered_task_rejected(self):
        bundle = self.prepare(); old = self.registry.export()
        self.intake["provenance_sha256"] = digest("different")
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(old, self.registry.export())
        bad = copy.deepcopy(bundle); bad["review_tasks"][0]["rubric"] = "changed"
        bad["sha256"] = digest({k:v for k,v in bad.items() if k != "sha256"})
        with self.assertRaises(ValueError): verify_bundle(bad)

    async def test_unregistered_source_and_failed_exposure_return_no_bundle(self):
        empty = FamilyRegistry(":memory:", "empty"); self.addCleanup(empty.close)
        with self.assertRaises(ValueError): prepare_review(empty, self.manifest, self.sources, self.frozen, self.intake)
        self.assertEqual(empty.export()["events"], [])
        old = self.registry.export()
        self.registry.db.execute("CREATE TRIGGER deny_exposure BEFORE INSERT ON family_events BEGIN SELECT RAISE(ABORT,'blocked'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.prepare()
        self.assertEqual(old, self.registry.export())


if __name__ == "__main__":
    import argparse
    import hashlib
    import os
    from app.g5.world import canonical
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    source_path = Path("research/experiments/2026-09-12-g5-local-calibration-bridge/panel.json")
    original_bytes = source_path.read_bytes()
    annotation = json.loads(original_bytes)["annotation"]
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700, exist_ok=False)
    with tempfile.TemporaryDirectory() as temporary:
        registry = FamilyRegistry(str(Path(temporary) / "registry.db"), "synthetic-material-intake-control")
        register(registry, annotation["manifest"])
        before = registry.export()
        intake = {"id": "calibration-review-intake", "observer": WHO, "source_kind": "synthetic",
                  "sampling": "constructed", "provenance_sha256": hashlib.sha256(original_bytes).hexdigest()}
        bundle = prepare_review(registry, annotation["manifest"], annotation["sources"], annotation["plan"], intake)
        raw = {"schema": "g5-material-intake-audit-v1", "classification": "synthetic-engineering-only",
               "historical_exposure_completeness": "not_established",
               "input_path": str(source_path), "input_file_sha256": hashlib.sha256(original_bytes).hexdigest(),
               "registry_before": before, "bundle": bundle, "verification": verify_bundle(bundle),
               "holdout_after": holdout_audit(registry.export(), bundle["exposure"]["families"]),
               "real_model_calls": 0, "qualification": "not_inferred"}
        registry.close()
    if source_path.read_bytes() != original_bytes:
        raise ValueError("Historical input changed")
    raw["sha256"] = digest(raw)
    with os.fdopen(os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(canonical(raw)); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"sha256": raw["sha256"], "verification": raw["verification"]}))
