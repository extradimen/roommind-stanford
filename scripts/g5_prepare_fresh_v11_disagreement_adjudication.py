#!/usr/bin/env python3
"""Prepare a source-blinded adjudication packet for v11 scorer disagreements."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-preflight")
PRED = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-predictions")
TARGET = Path("research/experiments/2026-09-13-g5-fresh-family-v11-disagreement-preflight")
EXPECTED_COMPARISON_SHA = "546b1f973b5dfbd8c01341c36776095f25c65e6d6c511c1c1e7819be0ff62529"


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
    comparison = load(PRED / "reference-comparison.json")
    if (comparison.get("sha256") != EXPECTED_COMPARISON_SHA
            or digest({key: value for key, value in comparison.items() if key != "sha256"})
            != EXPECTED_COMPARISON_SHA):
        raise ValueError("Comparison changed")
    inputs, coordinator = load(PRE / "inputs.json"), load(PRE / "coordinator.json")
    packet, reference = load(PRE / "reviewer-a.json"), load(PRE / "ai-reference-a.json")
    blind_to_source = {item["blind_id"]: item["source_case_id"]
                       for item in coordinator["master"]}
    slot = next(item for item in coordinator["slots"] if item["slot_id"] == packet["slot_id"])
    alias_to_source = {item["task_id"]: blind_to_source[item["blind_id"]]
                       for item in slot["assignments"]}
    source_to_alias = {value: key for key, value in alias_to_source.items()}
    tasks = {task["task_id"]: task for task in packet["tasks"]}
    reference_rows = {alias_to_source[row["task_id"]]: row for row in reference["rows"]}
    input_cases = {case["task"]["case_id"]: case for case in inputs["cases"]}

    items, mapping = [], []
    for index, disagreement in enumerate(comparison["decisive_disagreements"], 1):
        case_id = disagreement["case_id"]
        alias, reference_row = source_to_alias[case_id], reference_rows[case_id]
        task = tasks[alias]
        result = None
        for attempt in (1, 2):
            path = PRED / f"{case_id}.{attempt}.result.json"
            if path.exists():
                candidate = load(path)
                if candidate["status"] == "completed":
                    result = candidate
                    break
        if result is None:
            raise ValueError("Completed scorer result missing")
        scorer = result["protocol"]["output"]
        assessments = [
            {"label": reference_row["label"], "citations": deepcopy(reference_row["citations"]),
             "rationale": reference_row["rationale"], "origin": "frozen_ai_reference"},
            {"label": scorer["prediction"],
             "citations": [{"evidence_id": item["evidence_id"],
                              "relevance": item["relevance"]} for item in scorer["evidence"]],
             "rationale": scorer["rationale"], "origin": "ollama_scorer"},
        ]
        random.Random(int(digest([EXPECTED_COMPARISON_SHA, case_id])[:16], 16)).shuffle(assessments)
        public_assessments, origins = {}, {}
        for side, assessment in zip(("X", "Y"), assessments):
            origins[side] = assessment.pop("origin")
            public_assessments[side] = assessment
        public_task = {key: deepcopy(value) for key, value in task.items()
                       if key not in {"task_id", "sha256"}}
        adjudication_id = f"D-{index:03d}"
        raw_item = {"adjudication_id": adjudication_id, "task": public_task,
                    "assessments": public_assessments}
        items.append({**raw_item, "sha256": digest(raw_item)})
        mapping.append({"adjudication_id": adjudication_id, "source_case_id": case_id,
                        "side_origins": origins})
    if len(items) != 14:
        raise ValueError("Unexpected disagreement count")

    raw_packet = {"schema": "g5-fresh-v11-blinded-disagreement-packet-v1",
        "classification": "internal-independent-ai-adjudication-candidate",
        "instructions": "Using only the task and evidence catalog, compare assessments X and Y. Choose X, Y, neither, or uncertain. Preserve reasonable refusal, disagreement, and unresolved work. Cite evidence IDs and explain the dimension-specific decision. Do not infer experimental condition or assessment origin.",
        "choices": ["X", "Y", "neither", "uncertain"], "items": items,
        "contains_conditions": False, "contains_assessment_origins": False,
        "external_distribution_authorized": False, "model_calls": 0}
    public_packet = {**raw_packet, "sha256": digest(raw_packet)}
    raw_coordinator = {"schema": "g5-fresh-v11-disagreement-coordinator-v1",
        "classification": "internal-coordinator-only", "comparison_sha256": comparison["sha256"],
        "packet_sha256": public_packet["sha256"], "mapping": mapping}
    coordinator_output = {**raw_coordinator, "sha256": digest(raw_coordinator)}
    template = {"schema": "g5-fresh-v11-disagreement-submission-v1",
        "packet_sha256": public_packet["sha256"],
        "reviewer": {"id": "", "kind": "ai"},
        "rows": [{"adjudication_id": item["adjudication_id"], "item_sha256": item["sha256"],
                  "choice": None, "citations": [], "rationale": ""} for item in items]}
    TARGET.mkdir(exist_ok=False, mode=0o700)
    for name, value in (("packet.json", public_packet), ("coordinator.json", coordinator_output),
                        ("response-template.json", template)):
        save(TARGET / name, value)
    files = {name: hashlib.sha256((TARGET / name).read_bytes()).hexdigest()
             for name in ("packet.json", "coordinator.json", "response-template.json")}
    raw_summary = {"schema": "g5-fresh-v11-disagreement-preflight-summary-v1",
        "disagreements": 14, "model_calls": 0, "adjudications": 0,
        "contains_conditions_in_packet": False, "contains_origins_in_packet": False,
        "external_distribution_authorized": False, "file_sha256": files}
    summary = {**raw_summary, "sha256": digest(raw_summary)}
    save(TARGET / "summary.json", summary)
    print(json.dumps({"disagreements": 14, "packet_sha256": public_packet["sha256"],
        "summary_sha256": summary["sha256"], "model_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
