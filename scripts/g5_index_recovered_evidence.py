"""Bind recovered metadata to a NEW exclusion registry, never to confirmation data."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.family_registry import FamilyRegistry, holdout_audit, verify_export

ROOT = Path("research/experiments/2026-09-12-g5-legacy-server-recovery")
OLD = Path("docs/G5_LEGACY_REGISTRY_20260912/registry.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    old = json.loads(OLD.read_text())
    state = verify_export(old)
    audit = json.loads((ROOT / "audit.json").read_text())
    # The legacy audit uses the legacy canonical JSON algorithm.
    from app.research_protocol import sha256_json
    if audit["sha256"] != sha256_json({k: v for k, v in audit.items() if k != "sha256"}):
        raise ValueError("Audit changed")
    receipt_path = ROOT / "recovery-receipt.json"
    if sha(receipt_path) != audit["recovery_receipt_sha256"]:
        raise ValueError("Receipt changed")
    files = []
    for name in ("recovery-receipt.json", "invalid-audit-only-receipt.json"):
        receipt = json.loads((ROOT / name).read_text())
        for item in receipt["files"]:
            p = Path(item["path"])
            if ROOT.resolve() not in p.resolve().parents or p.is_symlink():
                raise ValueError("Unexpected source path")
            if item["status"] != "downloaded" or sha(p) != item["sha256"] or p.stat().st_size != item["bytes"]:
                raise ValueError("Recovered bytes changed")
            files.append({**item, "evidence_use": "invalid-audit-only" if name.startswith("invalid") else "development-history-only"})
    by_path = {f["path"]: f for f in files}
    if len(by_path) != len(files):
        raise ValueError("Duplicate file")
    batches, events = [], list(old["events"])
    for export in audit["exports"]:
        if export["path"] not in by_path:
            raise ValueError("Unbound export")
        if export["mode"] != "current-read-only-export":
            continue
        families = sorted({r["slug"] for r in export["runs"]})
        if not set(families) <= set(state["families"]) or export["manifest_hash_match"] is not True:
            raise ValueError("Unreviewed family or manifest")
        if len(export["runs"]) != 8 or not all(r["hash_match"] is True for r in export["runs"]):
            raise ValueError("Run audit mismatch")
        evidence = by_path[export["path"]]["sha256"]
        events.append({"id": "recovered-development:" + export["batch_uuid"], "kind": "exposure",
            "families": families, "purpose": "development",
            "observer": {"id": "g5-recovered-metadata-audit", "kind": "assistant"}, "artifact_sha256": evidence})
        batches.append({**export, "file_sha256": evidence, "evidence_use": "development-history-only"})
    if len(batches) != 18 or len({b["batch_uuid"] for b in batches}) != 18:
        raise ValueError("Unexpected recovered batch inventory")
    index = {"schema": "g5-recovered-evidence-index-v1", "prior_registry_sha256": old["sha256"],
        "prior_registry_file_sha256": sha(OLD), "audit_file_sha256": sha(ROOT / "audit.json"),
        "files": files, "batches": batches, "launch_authorized": False,
        "confirmation_eligible": False, "semantic_rereview_performed": False,
        "historical_completeness_verified": False,
        "fresh_debug_probes_are_original_version_results": False,
        "observer_scope": "current assistant metadata audit, not historical operator identity",
        "new_frozen_input_materials_registered": 0}
    index["sha256"] = digest(index)
    return old, events, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    old, events, index = build()
    target = Path(args.output_dir)
    target.mkdir(exist_ok=False)
    path = target / "registry.sqlite"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    registry_id = "g5-legacy-recovered-exposure-20260912"
    registry = FamilyRegistry(str(path), registry_id)
    try:
        for event in events:
            registry.append(event)
        exported = registry.export()
    finally:
        registry.close()
    registry = FamilyRegistry(str(path), registry_id)
    try:
        for event in events:
            registry.append(event)
        if registry.export() != exported:
            raise ValueError("Reconnect/replay mismatch")
    finally:
        registry.close()
    audit = holdout_audit(exported, sorted(verify_export(old)["families"]))
    if audit["registered_exposure_free"] or any(not r["exposure_event_ids"] for r in audit["families"]):
        raise ValueError("Exclusion failed")
    if build() != (old, events, index):
        raise ValueError("Source changed during indexing")
    for name, value in (("registry.json", exported), ("holdout-audit.json", audit), ("evidence-index.json", index)):
        fd = os.open(target / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
    print(json.dumps({"events": len(events), "indexed_files": len(index["files"]),
        "registry_sha256": exported["sha256"], "index_sha256": index["sha256"], "launch_authorized": False}))


if __name__ == "__main__":
    main()
