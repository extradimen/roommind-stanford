"""Local read-only legacy evidence census; no model/database/registry writes.

Explicitly not semantic review, family independence certification or a new
qualification result. Output is exclusive and contains metadata/hashes only.
"""
import argparse
import hashlib
import gzip
import json
import os
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def scan(root):
    rows, files, issues = [], {}, []
    base = root / "research/experiments"
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or "-g5-" in folder.name: continue
        if folder.is_symlink(): raise ValueError("Symlink directory")
        for path in sorted(folder.rglob("*")):
            if path.is_symlink(): raise ValueError("Symlink artifact")
            if path.is_file(): files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted([*folder.glob("*transcripts.json"), *folder.glob("*transcripts.json.gz")]):
            if path.suffix == ".gz":
                with gzip.open(path, "rt") as stream: data = json.load(stream)
            else:
                data = json.loads(path.read_text())
            if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
                issues.append({"path": str(path.relative_to(root)), "issue": "unsupported-export-schema"}); continue
            manifest = data.get("research_manifest") or {}
            frozen = (data.get("config") or {}).get("frozen_inputs") or {}
            record = {"path": str(path.relative_to(root)), "batch_uuid": data.get("batch_uuid"),
                "status": data.get("batch_status"), "generation": manifest.get("generation_id"),
                "phase": manifest.get("study_phase"), "declared_evidence_use": manifest.get("evidence_use"),
                "manifest_hash_match": manifest.get("manifest_sha256") == digest({k:v for k,v in manifest.items() if k != "manifest_sha256"}) if manifest else None,
                "frozen_input_aggregate_match": manifest.get("frozen_inputs_sha256") == digest(frozen) if frozen else None,
                "frozen_inputs": [], "runs": [], "g5_holdout_eligible": False}
            for key, entry in frozen.items():
                inputs = entry.get("inputs", {})
                scenario = inputs.get("scenario", {})
                record["frozen_inputs"].append({"scenario_id": key, "slug": scenario.get("slug"),
                    "sha256": entry.get("sha256"), "hash_match": entry.get("sha256") == digest(inputs)})
            for run in data["runs"]:
                session = run.get("session") or {}
                public = [{key:m.get(key) for key in ("sequence_no", "turn_id", "speaker_id", "speaker_type", "speaker_source", "content", "created_at")}
                          for m in session.get("messages", []) if m.get("speaker_type") in ("user", "npc")]
                public.sort(key=lambda m:(int(m.get("sequence_no") or 0), int(m.get("turn_id") or 0)))
                recorded = (run.get("run_result") or {}).get("transcript_sha256")
                scenario = session.get("scenario") or {}
                record["runs"].append({"run_id": run.get("run_id"), "scenario_id": run.get("scenario_id"),
                    "slug": scenario.get("slug"), "condition": run.get("condition"), "repetition": run.get("repetition"),
                    "status": run.get("run_status"), "public_messages": len(public), "computed_sha256": digest(public),
                    "recorded_sha256": recorded, "hash_match": digest(public) == recorded if recorded else None})
            rows.append(record)
    docs = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "docs").glob("EXPERIMENT_G*.md"))}
    slugs = {}
    for row in rows:
        for run in row["runs"]:
            if run["slug"]: slugs.setdefault(run["slug"], set()).add(row["generation"] or "unknown")
    raw = {"schema": "g5-legacy-local-census-v1", "scope": "repository-research-directory-and-experiment-documents",
        "legacy_artifact_sha256": files, "experiment_document_sha256": docs, "batches": rows, "issues": issues,
        "slug_exposure_generations": {k:sorted(v) for k,v in sorted(slugs.items())},
        "limitations": ["not-all-storage-locations", "no-server-access", "no-semantic-transcript-review",
                        "slugs-not-independent-families", "missing-hash-is-unknown-not-pass"],
        "historical_completeness_verified": False, "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--root", default="."); p.add_argument("--output", required=True)
    args = p.parse_args(); root = Path(args.root).resolve(); result = scan(root)
    # Repeat the full census before publishing, detecting ordinary concurrent edits.
    if scan(root) != result: raise ValueError("History changed during census")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(result, f, ensure_ascii=False, sort_keys=True); f.flush(); os.fsync(f.fileno())
    print(json.dumps({"batches": len(result["batches"]), "files": len(result["legacy_artifact_sha256"]),
                      "documents": len(result["experiment_document_sha256"]), "sha256": result["sha256"]}))


if __name__ == "__main__": main()
