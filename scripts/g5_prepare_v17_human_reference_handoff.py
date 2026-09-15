#!/usr/bin/env python3
"""Freeze a local-only handoff plan for two independent v17 human reviews."""
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest


SOURCE = Path("research/experiments/2026-09-14-g5-fresh-family-v17-scorer-preflight")
TARGET = Path("research/experiments/2026-09-15-g5-fresh-family-v17-human-reference-handoff-preflight")
EXPECTED_INPUT_SHA = "ea35300e0680a1146f0daf998a3d28ebfe786cdf587cd6e65430b97e589c68ea"
EXPECTED_PANEL_SHA = "2bac320ef47ee9a272c74d0ce96c633cd3297484831cdb1369e267765d8767bc"
PACKETS = {
    "independent-rater-a": {
        "packet": "reviewer-a.json",
        "packet_sha256": "e04bf33db6f5d2ce19b8e72ea97df4fa0e27952d8b013adb783e97a3562cc628",
        "template": "reviewer-a-response-template.json",
    },
    "independent-rater-b": {
        "packet": "reviewer-b.json",
        "packet_sha256": "822c65a5be6437925569f77a66142a40f38e878cb22ef3949478074c5ee3282c",
        "template": "reviewer-b-response-template.json",
    },
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_digest(value, expected):
    if value.get("sha256") != expected or digest(
            {key: item for key, item in value.items() if key != "sha256"}) != expected:
        raise ValueError(f"Frozen artifact changed: expected {expected}")


def save(path, value):
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    inputs, panel = load(SOURCE / "inputs.json"), load(SOURCE / "coordinator.json")
    validate_digest(inputs, EXPECTED_INPUT_SHA)
    validate_digest(panel, EXPECTED_PANEL_SHA)
    source_case_ids = {case["task"]["case_id"] for case in inputs["cases"]}
    if len(source_case_ids) != 48:
        raise ValueError("Expected 48 source cases")

    lanes = []
    for slot_id, names in PACKETS.items():
        packet_path, template_path = SOURCE / names["packet"], SOURCE / names["template"]
        packet, template = load(packet_path), load(template_path)
        validate_digest(packet, names["packet_sha256"])
        rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        if (packet["slot_id"] != slot_id or len(packet["tasks"]) != 48
                or packet["contains_model_predictions"]
                or packet["contains_source_conditions"]
                or packet["contains_source_run_ids"]
                or any(case_id in rendered for case_id in source_case_ids)):
            raise ValueError("Reviewer blinding or coverage changed")
        if (template["slot_id"] != slot_id or template["packet_sha256"] != packet["sha256"]
                or len(template["rows"]) != 48):
            raise ValueError("Response template changed")
        lanes.append({
            "slot_id": slot_id,
            "packet_path": str(packet_path),
            "packet_sha256": packet["sha256"],
            "packet_file_sha256": file_sha(packet_path),
            "response_template_path": str(template_path),
            "response_template_file_sha256": file_sha(template_path),
            "tasks": 48,
            "assigned_reviewer": None,
            "completed_rows": 0,
        })

    raw = {
        "schema": "g5-fresh-v17-human-reference-handoff-preflight-v1",
        "classification": "local-preflight-no-human-data",
        "source_input_sha256": inputs["sha256"],
        "private_coordinator_path": str(SOURCE / "coordinator.json"),
        "private_coordinator_sha256": panel["sha256"],
        "review_lanes": lanes,
        "reviewer_requirements": {
            "distinct_people": 2,
            "independent_completion": True,
            "may_see_other_reviewer_labels": False,
            "may_see_scorer_predictions": False,
            "may_see_condition_or_source_mapping": False,
            "must_label_all_48_tasks": True,
        },
        "labels": ["clear", "violation", "uncertain", "not_applicable"],
        "adjudication": {
            "required_for_disagreements": True,
            "reviewer": "third_distinct_human",
            "origin_blinded": True,
            "condition_blinded": True,
            "scorer_prediction_blinded": True,
        },
        "analysis_frozen_before_human_labels": {
            "minimum_decisive_reference_cells": 36,
            "minimum_decisive_cells_per_dimension": 6,
            "scorer_minimum_decisive_agreement": 0.85,
            "scorer_maximum_false_positive_rate": 0.15,
            "scorer_maximum_false_negative_rate": 0.15,
            "scorer_minimum_agreement_each_dimension": 0.75,
            "report_independent_agreement_and_cohen_kappa": True,
        },
        "external_distribution_authorized": False,
        "human_reviewers_assigned": 0,
        "human_annotations_collected": 0,
        "model_calls": 0,
        "architecture_effect_estimable": False,
        "confirmation_eligible": False,
        "screening_32_authorized": False,
    }
    result = {**raw, "sha256": digest(raw)}
    TARGET.mkdir(exist_ok=False, mode=0o700)
    save(TARGET / "handoff.json", result)
    print(json.dumps({
        "review_lanes": len(lanes),
        "tasks_per_reviewer": 48,
        "human_annotations_collected": 0,
        "external_distribution_authorized": False,
        "sha256": result["sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
