#!/usr/bin/env python3
"""Validate and freeze the independent AI development reference; no model calls."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest


DIRECTORY = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-preflight")
PACKET = DIRECTORY / "reviewer-a.json"
REFERENCE = DIRECTORY / "ai-reference-a.json"
FREEZE = DIRECTORY / "ai-reference-freeze.json"
EXPECTED_PACKET_SHA = "bd53cfb2ec789c08dec0a2e44a85b0a3c9281f850e012c518f5c5d55e080028d"
EXPECTED_REFERENCE_FILE_SHA = "96f289023dbb2fa60cb1fd9d49b292802753d9342cc78723e4af0ef415fb5dc0"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def validate():
    packet, reference = load(PACKET), load(REFERENCE)
    if (packet.get("sha256") != EXPECTED_PACKET_SHA
            or digest({key: value for key, value in packet.items() if key != "sha256"})
            != EXPECTED_PACKET_SHA):
        raise ValueError("Anonymous review packet changed")
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest() != EXPECTED_REFERENCE_FILE_SHA:
        raise ValueError("AI reference file changed")
    if set(reference) != {"schema", "slot_id", "reviewer", "packet_sha256", "rows",
            "classification", "condition_material_seen", "model_predictions_seen",
            "confirmation_eligible"}:
        raise ValueError("Unexpected AI reference fields")
    if (reference["schema"] != "g5-blinded-ai-development-reference-v1"
            or reference["slot_id"] != packet["slot_id"]
            or reference["packet_sha256"] != EXPECTED_PACKET_SHA
            or reference["reviewer"] != {
                "id": "codex-independent-ai-reference-20260913", "kind": "ai"}
            or reference["classification"] != "single-ai-expert-development-diagnostic"
            or reference["condition_material_seen"] is not False
            or reference["model_predictions_seen"] is not False
            or reference["confirmation_eligible"] is not False):
        raise ValueError("AI reference provenance or scope changed")

    tasks = {task["task_id"]: task for task in packet["tasks"]}
    if len(reference["rows"]) != len(tasks) or len(tasks) != 48:
        raise ValueError("AI reference coverage changed")
    seen = set()
    for row in reference["rows"]:
        if set(row) != set(packet["response_contract"]["row_fields"]):
            raise ValueError("Unexpected AI reference row")
        task = tasks.get(row["task_id"])
        if task is None or row["task_id"] in seen or row["task_sha256"] != task["sha256"]:
            raise ValueError("Unknown, duplicate or changed reference task")
        seen.add(row["task_id"])
        if (row["label"] not in packet["response_contract"]["labels"]
                or not isinstance(row["rationale"], str) or not row["rationale"].strip()
                or row["condition_guess"] not in packet["response_contract"]["condition_guesses"]
                or type(row["condition_guess_confidence"]) not in {int, float}
                or not 0 <= row["condition_guess_confidence"] <= 1):
            raise ValueError("Invalid reference decision")
        known = {item["evidence_id"] for item in task["evidence_catalog"]}
        citations = row["citations"]
        if (not isinstance(citations, list)
                or (row["label"] in {"clear", "violation"} and not citations)):
            raise ValueError("Decisive AI reference requires evidence")
        cited = set()
        for citation in citations:
            if (set(citation) != set(packet["response_contract"]["citation_fields"])
                    or citation["evidence_id"] not in known
                    or citation["evidence_id"] in cited
                    or not isinstance(citation["relevance"], str)
                    or not citation["relevance"].strip()):
                raise ValueError("Invalid reference citation")
            cited.add(citation["evidence_id"])
    return packet, reference


def main():
    packet, reference = validate()
    prediction_directory = DIRECTORY.parent / "2026-09-13-g5-fresh-family-v11-scorer-predictions"
    if prediction_directory.exists():
        raise ValueError("Reference must freeze before model scoring starts")
    counts = dict(sorted(Counter(row["label"] for row in reference["rows"]).items()))
    raw = {"schema": "g5-blinded-ai-development-reference-freeze-v1",
        "classification": "single-ai-expert-development-diagnostic",
        "source_thread_id": "01a09ae5-1e84-70a2-bb97-ba6848b6f42d",
        "packet_sha256": packet["sha256"],
        "reference_file_sha256": EXPECTED_REFERENCE_FILE_SHA,
        "reference_content_sha256": digest(reference), "rows": 48,
        "label_counts": counts, "condition_material_seen": False,
        "model_predictions_seen": False, "frozen_before_model_scoring": True,
        "human_reference": False, "accuracy_claim_permitted": False,
        "confirmation_eligible": False}
    result = {**raw, "sha256": digest(raw)}
    save(FREEZE, result)
    print(json.dumps({"rows": 48, "label_counts": counts,
        "reference_file_sha256": EXPECTED_REFERENCE_FILE_SHA,
        "freeze_sha256": result["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
