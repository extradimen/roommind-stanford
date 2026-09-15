"""Metadata/hash audit of separately preserved old bytes and current GET views."""
import gzip
import hashlib
import json
import os
from pathlib import Path
from app.research_protocol import transcript_provenance, sha256_json

ROOT = Path("research/experiments/2026-09-12-g5-legacy-server-recovery")


def main():
    receipt = json.loads((ROOT / "recovery-receipt.json").read_text())
    exports = []
    for item in receipt["files"]:
        if item["status"] != "downloaded": continue
        path = Path(item["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]: raise ValueError("Recovered bytes changed")
        if not path.name.endswith(("transcripts.json", "transcripts.json.gz")): continue
        with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as f: data = json.load(f)
        manifest = data.get("research_manifest") or {}
        runs = []
        for r in data.get("runs", []):
            session = r.get("session") or {}
            sha = transcript_provenance(session)["transcript_sha256"]
            recorded = (r.get("run_result") or {}).get("transcript_sha256")
            runs.append({"run_id": r["run_id"], "status": r["run_status"], "condition": r["condition"],
                "scenario_id": r["scenario_id"], "slug": (session.get("scenario") or {}).get("slug"),
                "computed_sha256": sha, "recorded_sha256": recorded,
                "hash_match": sha == recorded if recorded else None})
        exports.append({"path": item["path"], "mode": item["mode"], "batch_uuid": data["batch_uuid"],
            "generation": manifest.get("generation_id"), "batch_status": data.get("batch_status"),
            "manifest_hash_match": manifest.get("manifest_sha256") == sha256_json({k:v for k,v in manifest.items() if k != "manifest_sha256"}),
            "runs": runs})
    comparisons = []
    for old in exports:
        if old["mode"] != "historical-file": continue
        for new in exports:
            if new["mode"] == "current-read-only-export" and new["batch_uuid"] == old["batch_uuid"]:
                project = lambda x: {r["run_id"]:r["computed_sha256"] for r in x["runs"]}
                comparisons.append({"historical_path": old["path"], "current_path": new["path"],
                    "batch_uuid": old["batch_uuid"], "same_run_ids_and_public_transcript_hashes": project(old) == project(new)})
    report = {"scope": "hash-and-metadata-not-semantic-qualification", "exports": exports,
              "historical_current_comparisons": comparisons, "recovery_receipt_sha256": hashlib.sha256((ROOT / "recovery-receipt.json").read_bytes()).hexdigest(),
              "historical_completeness_verified": False, "launch_authorized": False}
    report["sha256"] = sha256_json(report)
    fd = os.open(ROOT / "audit.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(report, f, sort_keys=True); f.flush(); os.fsync(f.fileno())
    current = [e for e in exports if e["mode"] == "current-read-only-export"]
    print(json.dumps({"current_batches": len(current), "current_runs": sum(len(e["runs"]) for e in current),
        "current_hash_mismatches": sum(r["hash_match"] is False for e in current for r in e["runs"]),
        "current_missing_recorded_hash": sum(r["hash_match"] is None for e in current for r in e["runs"]),
        "old_current_comparisons": comparisons, "sha256": report["sha256"]}))


if __name__ == "__main__": main()
