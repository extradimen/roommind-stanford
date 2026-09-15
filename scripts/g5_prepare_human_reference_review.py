"""Create local blinded human-reference packets; never contacts reviewers."""
import hashlib
import json
import os
from pathlib import Path
import secrets

from app.factorial_study import digest
from app.g5.reference_review import build_panel, reviewer_packet
from g5_run_development_calibration import read, save

INPUT = Path("research/experiments/2026-09-12-g5-catalog-evidence-calibration-inputs/inputs.json")
TARGET = Path("research/experiments/2026-09-12-g5-human-reference-review-preflight-v2")
INPUT_SHA = "55f0de1fb8f61691030b7055fd21b6dfe92267c6bba877279fe1a6f82f7edc9b"


def template(packet):
    rows = [{"task_id": task["task_id"], "task_sha256": task["sha256"], "label": None,
        "citations": [], "rationale": "", "condition_guess": None,
        "condition_guess_confidence": None} for task in packet["tasks"]]
    return {"schema": "g5-blinded-reference-submission-v1", "slot_id": packet["slot_id"],
        "reviewer": {"id": "", "kind": "human"}, "packet_sha256": packet["sha256"], "rows": rows,
        }


def main():
    source = read(INPUT)
    if source["sha256"] != INPUT_SHA or digest({key: value for key, value in source.items()
                                               if key != "sha256"}) != INPUT_SHA:
        raise ValueError("Frozen v4 input changed")
    TARGET.mkdir(exist_ok=True, mode=0o700)
    if {path.name for path in TARGET.iterdir()} - {"README.md"}:
        raise ValueError("Target already contains generated material")
    panel = build_panel(source["cases"], secrets.token_hex(32))
    packets = [reviewer_packet(panel, slot["slot_id"]) for slot in panel["slots"]]
    if len(panel["master"]) != 48 or any(len(packet["tasks"]) != 48 for packet in packets):
        raise ValueError("Incomplete human-reference panel")
    source_ids = {case["task"]["case_id"] for case in source["cases"]}
    for packet in packets:
        rendered = json.dumps(packet, ensure_ascii=False)
        if any(source_id in rendered for source_id in source_ids):
            raise ValueError("Source case identity leaked into reviewer packet")
    artifacts = {"coordinator.json": panel}
    for index, packet in enumerate(packets):
        letter = chr(ord("a") + index)
        artifacts[f"reviewer-{letter}.json"] = packet
        artifacts[f"reviewer-{letter}-response-template.json"] = template(packet)
    distribution = {"schema": "g5-human-reference-distribution-plan-v1",
        "status": "local-preflight-only", "source_input_sha256": INPUT_SHA,
        "coordinator_sha256": panel["sha256"],
        "share_rules": ["Assign two distinct qualified human reviewers.",
            "Give each reviewer only their own reviewer JSON and response template.",
            "Never share coordinator.json, the other reviewer packet, model predictions or source conditions.",
            "Reviewers work independently and return complete files before any disagreement is revealed.",
            "Only disagreements are sent to a distinct third human adjudicator."],
        "external_distribution_authorized": False, "human_reviewers_assigned": 0,
        "human_annotations_collected": 0, "qualification": "not_inferred"}
    distribution["sha256"] = digest(distribution)
    artifacts["distribution-plan.json"] = distribution
    for name, value in artifacts.items():
        save(TARGET / name, value)
    file_sha = {name: hashlib.sha256((TARGET / name).read_bytes()).hexdigest() for name in artifacts}
    manifest = {"schema": "g5-human-reference-preflight-manifest-v1",
        "source_input_sha256": INPUT_SHA, "cases": 48, "independent_reviewer_slots": 2,
        "adjudicator_slots": 1, "file_sha256": file_sha, "external_distribution_authorized": False,
        "human_reviewers_assigned": 0, "human_annotations_collected": 0,
        "contains_model_predictions_in_reviewer_packets": False,
        "contains_source_conditions_in_reviewer_packets": False,
        "research_quality_verified": False}
    manifest["sha256"] = digest(manifest)
    save(TARGET / "manifest.json", manifest)
    print(json.dumps({"cases": 48, "reviewer_packets": 2, "files": len(artifacts) + 1,
        "sha256": manifest["sha256"], "external_distribution_authorized": False,
        "human_annotations_collected": 0}))


if __name__ == "__main__":
    main()
