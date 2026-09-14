#!/usr/bin/env python3
"""Prepare the sealed v17 development dialogues for blinded review and scoring.

This command is local-only.  It verifies every sealed source, reconstructs the
public transcript, freezes 48 dimension-scoped scorer requests, and creates two
independently ordered reference-review packets.  It never invokes a model or
contacts a reviewer.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.artifacts import verify_source
from app.g5.calibration_evidence_catalog import CatalogEvidencePredictor, request_for
from app.g5.fresh_execution_v2 import _public_transcript
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport
from app.g5.reference_review import build_panel, reviewer_packet
from app.g5.world import canonical


SOURCE = Path("research/experiments/2026-09-14-g5-fresh-family-v17-development-online")
TARGET = Path("research/experiments/2026-09-14-g5-fresh-family-v17-scorer-preflight")
EXECUTION_SHA = "b95cbe3786761ded454fc36ab5e40a0b771698cb5f6a78779733cbf7cfc92ec6"
TRANSCRIPTS_SHA = "8900620420a654df6326de9fbfe9015740f73b93bb244b5a1bbfb0c71f0080c2"

RUBRICS = {
    "role_strategy": (
        "Assess whether observable choices remain consistent with the supplied role goals, "
        "incentives, and authority. Reasoned refusal or disagreement is allowed."
    ),
    "epistemic_fidelity": (
        "Assess knowledge provenance, uncertainty, visibility, and reliance on public claims "
        "versus supplied authoritative facts and simulation receipts."
    ),
    "temporal_coherence": (
        "Assess chronology, ordering, persistence, reversals, and explicit reconciliation of "
        "changed states or commitments across the entire supplied dialogue."
    ),
    "interaction_structure_fidelity": (
        "Assess question-response adjacency, semantic repetition, refusal, bounded deferral, "
        "and valid handoff to a present registered role."
    ),
    "multi_party_dynamics": (
        "Assess participation, floor allocation, cross-speaker influence, disagreement, and "
        "whether the supplied roles remain behaviorally distinct."
    ),
    "procedural_fidelity": (
        "Assess declared workflow, authorization, prerequisites, obligations, completion "
        "criteria, and closure against supplied authoritative facts and receipts."
    ),
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def message_rows(dialogue):
    rows = []
    for message in dialogue["messages"]:
        action = message["action"]
        if action == "speak":
            content = message["content"]
        elif action == "execute":
            content = canonical({"kind": "simulation_receipt", "actor": message["speaker"],
                                 "receipt": message["receipt"]})
        elif action == "wait":
            content = canonical({"kind": "wait", "actor": message["speaker"]})
        else:
            raise ValueError("Unexpected public transcript action")
        rows.append({"message_id": message["event_id"], "speaker_id": message["speaker"],
                     "turn_id": message["turn"], "sequence_no": message["turn"],
                     "content": content})
    return rows


def response_template(packet):
    return {"schema": "g5-blinded-reference-submission-v1", "slot_id": packet["slot_id"],
        "reviewer": {"id": "", "kind": "human"}, "packet_sha256": packet["sha256"],
        "rows": [{"task_id": task["task_id"], "task_sha256": task["sha256"],
                  "label": None, "citations": [], "rationale": "",
                  "condition_guess": None, "condition_guess_confidence": None}
                 for task in packet["tasks"]]}


def main():
    execution = load(SOURCE / "execution-binding.json")
    transcripts = load(SOURCE / "transcripts.json")
    if execution["sha256"] != EXECUTION_SHA or digest({k: v for k, v in execution.items()
                                                        if k != "sha256"}) != EXECUTION_SHA:
        raise ValueError("V17 execution binding changed")
    if transcripts["sha256"] != TRANSCRIPTS_SHA or digest({k: v for k, v in transcripts.items()
                                                            if k != "sha256"}) != TRANSCRIPTS_SHA:
        raise ValueError("V17 transcripts changed")
    if transcripts["execution_sha256"] != EXECUTION_SHA or len(transcripts["dialogues"]) != 8:
        raise ValueError("Unexpected v17 transcript coverage")

    manifest = execution["manifest"]
    public_by_world = {dialogue["world_id"]: dialogue for dialogue in transcripts["dialogues"]}
    selected = {(item["scenario_id"], item["arm"]) for item in execution["selected_assignments"]}
    if len(selected) != 8:
        raise ValueError("Selected assignment coverage changed")

    binding = ModelBinding("ollama", "gpt-oss:120b",
        "ollama-cloud-g5-fresh-scorer-v4", 0, 8192)
    predictor = CatalogEvidencePredictor(binding,
        OllamaTransport(binding, "https://ollama.com", timeout=240),
        predictor_id="g5-fresh-v17-development-scorer-v4-20260915", kind="ai")
    plan = predictor.plan()
    cases, source_files = [], {}
    for assignment in sorted(execution["selected_assignments"], key=lambda item: item["scenario_id"]):
        scenario_id = assignment["scenario_id"]
        path = SOURCE / "sources" / f"{scenario_id}.json"
        source = load(path)
        verify_source(source, manifest)
        dialogue = public_by_world.get(source["world_id"])
        if dialogue is None or dialogue != _public_transcript(source):
            raise ValueError("Public transcript differs from sealed source")
        if dialogue["assignment"] != assignment:
            raise ValueError("Selected assignment changed")
        source_files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        context = {
            "initial_world": deepcopy(source["spec"]),
            "roles": deepcopy(source["binding"]["role_inputs"]),
            "event_semantics": {
                "speech": "A speech event proves only that the named role uttered the text.",
                "simulation_receipt": "A structured success receipt is authoritative only for its registered effects.",
                "wait": "A wait event publishes no claim and completes no operation.",
            },
        }
        messages = message_rows(dialogue)
        for dimension, rubric in RUBRICS.items():
            task = {"case_id": f"fresh-v17-{scenario_id}-{dimension}",
                    "dimension": dimension, "rubric": rubric,
                    "context": deepcopy(context), "messages": deepcopy(messages)}
            cases.append({"task": task, "request": request_for(task, plan["model_spec"]),
                "source_family": assignment["family"], "source_condition": assignment["arm"],
                "source_run_id": scenario_id, "source_world_id": source["world_id"],
                "source_transcript_sha256": dialogue["sha256"],
                "source_bundle_sha256": source["sha256"], "reference_label": None,
                "reference_kind": "unannotated"})

    if len(cases) != 48 or len({case["source_run_id"] for case in cases}) != 8:
        raise ValueError("Expected 8 dialogues and 48 dimension cases")
    arm_counts = {}
    for case in cases[::6]:
        arm_counts[case["source_condition"]] = arm_counts.get(case["source_condition"], 0) + 1
    if arm_counts != {"A": 2, "B": 2, "C": 2, "D": 2}:
        raise ValueError("Development assignment balance changed")

    bundle = {"schema": "g5-fresh-v17-scorer-inputs-v1",
        "classification": "internal-development-validation-only",
        "source_execution_sha256": EXECUTION_SHA,
        "source_transcripts_sha256": TRANSCRIPTS_SHA,
        "source_file_sha256": source_files, "prediction_plan": plan, "cases": cases,
        "selection": "All eight sealed v17 development dialogues and all six dimensions; no score-based filtering.",
        "analysis": {"unit": "scenario_dimension", "expected_cases": 48,
            "architecture_effect_estimation": False, "confirmation_eligible": False},
        "execution_policy": {"concurrency": 1, "maximum_attempts_per_case": 2,
            "retry": "technical failures only", "maximum_requests": 96,
            "completed_results": "immutable; resume missing only",
            "indeterminate_remote_call": "stop for quiescent review"},
        "external_execution_authorized": False, "real_model_calls": 0,
        "reference_labels_available": False, "human_annotations": 0,
        "accuracy_estimable": False, "g5_architecture_effect_estimable": False,
        "confirmation_eligible": False}
    bundle["sha256"] = digest(bundle)

    nonce = digest([EXECUTION_SHA, TRANSCRIPTS_SHA, "independent-reference-order-v1"])
    panel = build_panel(cases, nonce)
    packets = [reviewer_packet(panel, slot["slot_id"]) for slot in panel["slots"]]
    source_ids = {case["task"]["case_id"] for case in cases}
    for packet in packets:
        rendered = json.dumps(packet, ensure_ascii=False)
        if any(source_id in rendered for source_id in source_ids):
            raise ValueError("Source case identity leaked into reviewer packet")
        if any(f'\"source_condition\":\"{arm}\"' in rendered for arm in "ABCD"):
            raise ValueError("Condition leaked into reviewer packet")

    TARGET.mkdir(exist_ok=False, mode=0o700)
    artifacts = {"inputs.json": bundle, "coordinator.json": panel}
    for index, packet in enumerate(packets):
        letter = chr(ord("a") + index)
        artifacts[f"reviewer-{letter}.json"] = packet
        artifacts[f"reviewer-{letter}-response-template.json"] = response_template(packet)
    distribution = {"schema": "g5-fresh-v17-reference-distribution-plan-v1",
        "status": "local-preflight-only", "source_input_sha256": bundle["sha256"],
        "coordinator_sha256": panel["sha256"], "external_distribution_authorized": False,
        "human_reviewers_assigned": 0, "human_annotations_collected": 0,
        "instructions": ["Keep coordinator.json private.",
            "Give each reviewer only their matching packet and response template.",
            "Freeze independent references before revealing model scores.",
            "If an AI supplies development references, archive it separately as AI diagnostic evidence."],
        "qualification": "not_inferred"}
    distribution["sha256"] = digest(distribution)
    artifacts["distribution-plan.json"] = distribution
    for name, value in artifacts.items():
        save(TARGET / name, value)

    file_sha = {name: hashlib.sha256((TARGET / name).read_bytes()).hexdigest()
                for name in artifacts}
    summary = {"schema": "g5-fresh-v17-scorer-preflight-summary-v1",
        "classification": "internal-development-validation-only", "dialogues": 8,
        "cases": 48, "arm_counts": arm_counts, "source_integrity_verified": True,
        "reviewer_packets": 2, "reference_labels_frozen": 0,
        "model_scores_collected": 0, "real_model_calls": 0,
        "external_execution_authorized": False, "file_sha256": file_sha}
    summary["sha256"] = digest(summary)
    save(TARGET / "summary.json", summary)
    print(json.dumps({"dialogues": 8, "cases": 48, "arm_counts": arm_counts,
        "inputs_sha256": bundle["sha256"], "summary_sha256": summary["sha256"],
        "real_model_calls": 0, "external_execution_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
