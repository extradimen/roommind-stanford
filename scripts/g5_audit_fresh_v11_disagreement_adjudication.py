#!/usr/bin/env python3
"""Validate and unblind the frozen v11 disagreement adjudication; no model calls."""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-13-g5-fresh-family-v11-disagreement-preflight")
PRED = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-predictions")
OUTPUT = PRED / "disagreement-adjudication-audit.json"
EXPECTED_PACKET_SHA = "62182130e5232f2bf80d022098a1783a64d5152e0f2b11ed99fc128ababaea93"
EXPECTED_SUBMISSION_FILE_SHA = "bab875c550063f85aa94fc4edd589ee80ec4f97e52881ea6bb8dee41e429e884"
EXPECTED_COMPARISON_SHA = "546b1f973b5dfbd8c01341c36776095f25c65e6d6c511c1c1e7819be0ff62529"
VALID_CHOICES = {"X", "Y", "neither", "uncertain"}


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


def main():
    packet_path = PRE / "packet.json"
    submission_path = PRE / "ai-adjudication.json"
    packet, coordinator = load(packet_path), load(PRE / "coordinator.json")
    submission, comparison = load(submission_path), load(PRED / "reference-comparison.json")
    if packet.get("sha256") != EXPECTED_PACKET_SHA or digest(
            {key: value for key, value in packet.items() if key != "sha256"}) != EXPECTED_PACKET_SHA:
        raise ValueError("Adjudication packet changed")
    if hashlib.sha256(submission_path.read_bytes()).hexdigest() != EXPECTED_SUBMISSION_FILE_SHA:
        raise ValueError("Adjudication submission changed")
    if comparison.get("sha256") != EXPECTED_COMPARISON_SHA:
        raise ValueError("Reference comparison changed")
    if (submission.get("schema") != "g5-fresh-v11-disagreement-submission-v1"
            or submission.get("packet_sha256") != EXPECTED_PACKET_SHA
            or submission.get("classification") != "single-ai-development-adjudication"
            or submission.get("condition_material_seen") is not False
            or submission.get("assessment_origins_seen") is not False
            or submission.get("confirmation_eligible") is not False):
        raise ValueError("Adjudication provenance changed")

    packet_items = {item["adjudication_id"]: item for item in packet["items"]}
    mappings = {item["adjudication_id"]: item for item in coordinator["mapping"]}
    disagreements = {item["case_id"]: item for item in comparison["decisive_disagreements"]}
    if set(packet_items) != set(mappings) or len(packet_items) != 14:
        raise ValueError("Coordinator coverage mismatch")

    rows, seen = [], set()
    for row in submission.get("rows", []):
        if set(row) != {"adjudication_id", "item_sha256", "choice", "citations", "rationale"}:
            raise ValueError("Unexpected adjudication row fields")
        aid = row["adjudication_id"]
        if aid in seen or aid not in packet_items or row["choice"] not in VALID_CHOICES:
            raise ValueError("Invalid adjudication identity or choice")
        seen.add(aid)
        item = packet_items[aid]
        if row["item_sha256"] != item["sha256"] or not row["rationale"].strip() or not row["citations"]:
            raise ValueError("Incomplete adjudication row")
        evidence_ids = {entry["evidence_id"] for entry in item["task"]["evidence_catalog"]}
        for citation in row["citations"]:
            if (set(citation) != {"evidence_id", "relevance"}
                    or citation["evidence_id"] not in evidence_ids
                    or not citation["relevance"].strip()):
                raise ValueError("Invalid adjudication citation")
        mapping = mappings[aid]
        conflict = disagreements[mapping["source_case_id"]]
        supported_origin = (mapping["side_origins"][row["choice"]]
                            if row["choice"] in {"X", "Y"} else row["choice"])
        rows.append({"adjudication_id": aid, "case_id": mapping["source_case_id"],
                     "dimension": conflict["dimension"], "family": conflict["family"],
                     "reference": conflict["reference"], "prediction": conflict["prediction"],
                     "choice": row["choice"], "supported_origin": supported_origin})
    if seen != set(packet_items):
        raise ValueError("Adjudication coverage incomplete")

    origin_counts = Counter(row["supported_origin"] for row in rows)
    direction_counts = defaultdict(Counter)
    dimension_counts = defaultdict(Counter)
    for row in rows:
        direction = f"reference_{row['reference']}_scorer_{row['prediction']}"
        direction_counts[direction][row["supported_origin"]] += 1
        dimension_counts[row["dimension"]][row["supported_origin"]] += 1
    resolved = origin_counts["frozen_ai_reference"] + origin_counts["ollama_scorer"]
    initial_agreements = comparison["overall"]["exact_agreement_decisive"]
    raw = {"schema": "g5-fresh-v11-disagreement-adjudication-audit-v1",
        "classification": "single-ai-development-adjudication-audit",
        "submission_file_sha256": EXPECTED_SUBMISSION_FILE_SHA,
        "packet_sha256": EXPECTED_PACKET_SHA, "comparison_sha256": EXPECTED_COMPARISON_SHA,
        "adjudicator_task_id": "01a09b01-80ab-73c1-bf9a-52bba9fd37dd",
        "trace_review": {"only_packet_read": True, "network_calls": 0,
                         "condition_material_seen": False, "assessment_origins_seen": False},
        "conflicts": len(rows), "resolved_directionally": resolved,
        "supported_origin_counts": dict(sorted(origin_counts.items())),
        "by_error_direction": {key: dict(sorted(value.items()))
                               for key, value in sorted(direction_counts.items())},
        "by_dimension": {key: dict(sorted(value.items()))
                         for key, value in sorted(dimension_counts.items())},
        "rows": sorted(rows, key=lambda item: item["adjudication_id"]),
        "descriptive_combined": {
            "initial_agreements": initial_agreements,
            "directionally_resolved_cells": initial_agreements + resolved,
            "scorer_aligned_cells": initial_agreements + origin_counts["ollama_scorer"],
            "reference_aligned_cells": initial_agreements + origin_counts["frozen_ai_reference"],
        },
        "decision": "revise_scorer_and_clarify_labeling_guidance_then_validate_on_untouched_material",
        "interpretation": "One condition- and origin-blinded AI adjudicator favored the frozen AI reference in 12 of 13 directional decisions. This is strong development evidence of scorer semantic errors, not human accuracy or confirmatory evidence.",
        "architecture_effect_estimable": False, "human_accuracy_estimable": False,
        "confirmation_eligible": False, "launch_32_dialogue_screen": False}
    result = {**raw, "sha256": digest(raw)}
    save(OUTPUT, result)
    print(json.dumps({key: result[key] for key in ("conflicts", "resolved_directionally",
        "supported_origin_counts", "by_error_direction", "by_dimension",
        "descriptive_combined", "decision", "sha256")}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
