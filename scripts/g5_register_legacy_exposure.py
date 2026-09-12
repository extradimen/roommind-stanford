"""Register known legacy exposure in a NEW local registry; never edit old ones."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.family_registry import FamilyRegistry, holdout_audit, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    source = Path("docs/G5_LEGACY_LOCAL_CENSUS_20260912_COMPLETE_FORMATS.json")
    census = json.loads(source.read_text())
    if census["sha256"] != digest({k:v for k,v in census.items() if k != "sha256"}):
        raise ValueError("Census checksum changed")
    for name, sha in census["legacy_artifact_sha256"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha: raise ValueError("Legacy source changed")
    bases = ["candidate-panel-interview", "incident-response-command", "market-launch-go-no-go", "supply-chain-negotiation"]
    expected = set(bases + [s + "-world-v3" for s in bases])
    if set(census["slug_exposure_generations"]) != expected: raise ValueError("Unreviewed slug set")
    author = {"id": "g5-local-legacy-metadata-audit", "kind": "assistant"}
    events = []
    for base in bases:
        for slug, parents in ((base, []), (base + "-world-v3", [base])):
            events.append({"id": "family:" + slug, "kind": "family", "family_id": slug, "parents": parents,
                "provenance": {"author": author, "artifact_sha256": census["sha256"]}})
            events.append({"id": "exposure:" + slug, "kind": "exposure", "families": [slug],
                "purpose": "development", "observer": author, "artifact_sha256": census["sha256"]})
    for batch in census["batches"]:
        for entry in batch["frozen_inputs"]:
            if entry["hash_match"] is not True or entry["slug"] not in expected:
                raise ValueError("Unverified frozen material")
            events.append({"id": "material:" + entry["sha256"], "kind": "material", "family_id": entry["slug"],
                "snapshot_sha256": entry["sha256"], "provenance_sha256": census["sha256"]})
    target = Path(args.output_dir)
    target.mkdir(parents=False, exist_ok=False)
    path = target / "registry.sqlite"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(fd)
    registry = FamilyRegistry(str(path), "g5-legacy-known-exposure-20260912")
    try:
        for event in events: registry.append(event)
        exported = registry.export()
    finally: registry.close()
    registry = FamilyRegistry(str(path), "g5-legacy-known-exposure-20260912")
    try:
        if registry.export() != exported: raise ValueError("Registry reconnect mismatch")
        for event in events: registry.append(event)
        if registry.export() != exported: raise ValueError("Idempotent replay changed registry")
    finally: registry.close()
    state = verify_export(exported)
    audit = holdout_audit(exported, sorted(expected), expected_snapshot_sha256=exported["sha256"])
    if audit["registered_exposure_free"] or len(state["materials"]) != 4: raise ValueError("Exposure exclusion failed")
    for row in audit["families"]:
        if len(row["linked_families"]) != 2 or not row["exposure_event_ids"]: raise ValueError("Lineage exclusion failed")
    for name, value in (("registry.json", exported), ("holdout-audit.json", audit)):
        fd = os.open(target / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"events": len(events), "families": len(state["families"]), "materials": len(state["materials"]),
        "registered_exposure_free": audit["registered_exposure_free"], "registry_sha256": exported["sha256"],
        "audit_sha256": audit["sha256"], "launch_authorized": False}))


if __name__ == "__main__": main()
