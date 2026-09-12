"""Internal offline evidence bundle, not authorization to deploy or a pass verdict."""
from copy import deepcopy
import json
import os

from app.factorial_study import digest
from app.g5.artifacts import verify_source
from app.g5.evaluation import packet_from_source
from app.g5.evaluation_archive import EvaluationArchive
from app.g5.measurement import DIMENSIONS, index_scores, require
from app.g5.world import canonical


def evidence_bundle(sources, evaluation_export):
    raw = {"schema": "g5-internal-release-evidence-v1", "classification": "internal-audit-only",
           "sources": deepcopy(sources), "evaluation": deepcopy(evaluation_export)}
    bundle = {**raw, "sha256": digest(raw)}
    verify_evidence(bundle)
    return bundle


def verify_evidence(bundle):
    require(isinstance(bundle, dict) and set(bundle) == {"schema", "classification", "sources", "evaluation", "sha256"}
        and bundle["schema"] == "g5-internal-release-evidence-v1" and bundle["classification"] == "internal-audit-only",
        "Invalid release evidence envelope")
    require(bundle["sha256"] == digest({k: v for k, v in bundle.items() if k != "sha256"}), "Evidence checksum mismatch")
    exported = bundle["evaluation"]
    manifest, plan, packets = exported["manifest"], exported["plan"], exported["packets"]
    # Reuse the same archive validation without creating or modifying any file.
    archive = EvaluationArchive(":memory:", manifest, plan, packets, control=exported.get("control"))
    try:
        for result in exported["results"]:
            archive.append(result)
        require(archive.export() == exported, "Evaluation export does not reproduce its complete chain")
    finally:
        archive.close()
    require(isinstance(bundle["sources"], list) and len(bundle["sources"]) == len(packets), "Missing assigned source")
    sources, world_ids = {}, set()
    for source in bundle["sources"]:
        verify_source(source, manifest)
        ordinal = source["binding"]["assignment"]["ordinal"]
        require(ordinal not in sources and source["world_id"] not in world_ids, "Duplicate source assignment/identity")
        sources[ordinal] = source
        world_ids.add(source["world_id"])
    for packet in packets:
        ordinal = packet["transcript"]["ordinal"]
        require(ordinal in sources and packet_from_source(sources[ordinal], manifest) == packet,
                "Evaluation input does not match complete source events")
    attempts = [r["attempt"] for r in exported["results"]]
    _, indexed = index_scores(manifest, plan, [p["transcript"] for p in packets], attempts)
    counts = {k: 0 for k in ("completed", "not_applicable", "technical_failure", "missing")}
    for packet in packets:
        for dimension in DIMENSIONS:
            row = indexed.get((packet["transcript"]["ordinal"], dimension))
            counts[row["status"] if row is not None else "missing"] += 1
    return {"schema": "g5-evidence-verification-summary-v1", "evidence_sha256": bundle["sha256"],
        "assigned_dialogues": len(packets), "sealed_sources": len(sources), "dimension_outcomes": counts,
        "technical_failure_attempts": sum(a["status"] == "technical_failure" for a in attempts),
        "evaluation_terminal": counts["missing"] == counts["technical_failure"] == 0,
        "qualification": "not_inferred", "deployment_authorized": False,
        **({"evaluation_scope": "one-control-cell-not-complete-panel", "control": exported["control"]}
           if exported.get("control") is not None else {})}


def write_evidence(path, bundle):
    """Exclusive private file. Interrupted partial files are retained, never replaced."""
    summary = verify_evidence(bundle)
    content = canonical(bundle).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", help="Existing internal evidence JSON; read only")
    args = parser.parse_args()
    with open(args.evidence, encoding="utf-8") as stream:
        summary = verify_evidence(json.load(stream))
    # Do not print private role cards, transcripts or raw evaluator responses.
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
