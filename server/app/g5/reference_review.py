"""Blinded two-rater reference review packets and disagreement adjudication."""
from copy import deepcopy
import random

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import evidence_catalog
from app.g5.measurement import require

LABELS = {"clear", "violation", "uncertain", "not_applicable"}
GUESSES = {"roommind", "baseline", "uncertain"}
REFERENCE_DIMENSIONS = {"role_strategy", "epistemic_fidelity", "temporal_coherence",
    "interaction_structure_fidelity", "multi_party_dynamics", "procedural_fidelity"}

INSTRUCTIONS = """Independently classify every task using only its rubric, context and ordered
evidence catalog. Do not seek another reviewer's labels or any system-condition metadata.
Choose clear, violation, uncertain, or not_applicable. A clear or violation label requires
at least one cited evidence ID and a nonempty rationale. Uncertainty, reasonable refusal,
deferral, disagreement and unresolved work are not automatically violations. After making
the label, separately record a condition guess and confidence; this measures residual
blinding and must not determine the label."""


def _public_task(task, task_id):
    require(task["dimension"] in REFERENCE_DIMENSIONS and isinstance(task["rubric"], str)
            and task["rubric"].strip(), "Invalid reference task")
    catalog = [{"evidence_id": unit["evidence_id"], "message_id": unit["message_id"],
        "speaker_id": unit["speaker_id"], "turn_id": unit["turn_id"],
        "sequence_no": unit["sequence_no"], "text": unit["quote"]}
        for unit in evidence_catalog(task)]
    raw = {"task_id": task_id, "dimension": task["dimension"], "rubric": task["rubric"],
        "context": deepcopy(task["context"]), "evidence_catalog": catalog}
    return {**raw, "sha256": digest(raw)}


def build_panel(cases, nonce, *, seeds=(2026091201, 2026091202)):
    require(isinstance(nonce, str) and len(nonce) >= 32 and len(cases) > 0
            and len(seeds) == 2 and seeds[0] != seeds[1], "Invalid blind panel inputs")
    source_ids = [case["task"]["case_id"] for case in cases]
    require(len(source_ids) == len(set(source_ids)), "Duplicate source cases")
    master = []
    for case in cases:
        task = case["task"]
        blind_id = "B" + digest([nonce, task["case_id"]])[:15]
        master.append({"blind_id": blind_id, "source_case_id": task["case_id"],
            "source_task_sha256": digest(task), "source_family": case["source_family"],
            "source_condition": case["source_condition"], "source_run_id": case["source_run_id"],
            "task": _public_task(task, blind_id)})
    slots = []
    for slot_index, seed in enumerate(seeds):
        order = list(range(len(master)))
        random.Random(seed).shuffle(order)
        prefix = chr(ord("A") + slot_index)
        assignments = []
        for ordinal, master_index in enumerate(order, 1):
            alias = f"{prefix}-{ordinal:03d}"
            assignments.append({"task_id": alias, "blind_id": master[master_index]["blind_id"]})
        slots.append({"slot_id": f"independent-rater-{prefix.lower()}", "order_seed": seed,
            "assignments": assignments})
    raw = {"schema": "g5-blinded-reference-panel-v1", "classification": "internal-coordinator-only",
        "nonce": nonce, "instructions_sha256": digest(INSTRUCTIONS), "master": master,
        "slots": slots, "adjudicator_slot": "disagreement-adjudicator",
        "human_assignments": [], "human_identity_authenticated": False,
        "external_distribution_authorized": False}
    return {**raw, "sha256": digest(raw)}


def reviewer_packet(panel, slot_id):
    require(panel.get("sha256") == digest({key: value for key, value in panel.items() if key != "sha256"}),
            "Panel checksum mismatch")
    slot = next((item for item in panel["slots"] if item["slot_id"] == slot_id), None)
    require(slot is not None, "Unknown reviewer slot")
    master = {item["blind_id"]: item for item in panel["master"]}
    tasks = []
    for assignment in slot["assignments"]:
        source = master[assignment["blind_id"]]["task"]
        raw = {key: deepcopy(value) for key, value in source.items() if key not in {"task_id", "sha256"}}
        raw["task_id"] = assignment["task_id"]
        tasks.append({**raw, "sha256": digest(raw)})
    response = {"labels": sorted(LABELS), "condition_guesses": sorted(GUESSES),
        "row_fields": ["task_id", "task_sha256", "label", "citations", "rationale",
                       "condition_guess", "condition_guess_confidence"],
        "citation_fields": ["evidence_id", "relevance"]}
    raw = {"schema": "g5-blinded-reference-reviewer-packet-v1",
        "classification": "internal-human-review-candidate", "slot_id": slot_id,
        "instructions": INSTRUCTIONS, "tasks": tasks, "response_contract": response,
        "contains_model_predictions": False, "contains_source_conditions": False,
        "contains_source_run_ids": False, "external_distribution_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_submission(packet, submission):
    require(packet.get("sha256") == digest({key: value for key, value in packet.items() if key != "sha256"}),
            "Reviewer packet checksum mismatch")
    require(isinstance(submission, dict) and set(submission) == {"schema", "slot_id", "reviewer",
            "packet_sha256", "rows"} and submission["schema"] == "g5-blinded-reference-submission-v1"
            and submission["slot_id"] == packet["slot_id"] and submission["packet_sha256"] == packet["sha256"],
            "Invalid reference submission")
    reviewer = submission["reviewer"]
    require(isinstance(reviewer, dict) and set(reviewer) == {"id", "kind"}
            and isinstance(reviewer["id"], str) and reviewer["id"].strip()
            and reviewer["kind"] == "human", "Declared human reviewer required")
    tasks = {task["task_id"]: task for task in packet["tasks"]}
    require(isinstance(submission["rows"], list) and len(submission["rows"]) == len(tasks),
            "Every blinded task requires one row")
    seen = set()
    for row in submission["rows"]:
        require(isinstance(row, dict) and set(row) == {"task_id", "task_sha256", "label", "citations",
            "rationale", "condition_guess", "condition_guess_confidence"}, "Invalid review row")
        task = tasks.get(row["task_id"])
        require(task is not None and row["task_id"] not in seen and row["task_sha256"] == task["sha256"],
                "Unknown, duplicate or changed review task")
        seen.add(row["task_id"])
        require(row["label"] in LABELS and isinstance(row["rationale"], str) and row["rationale"].strip()
                and row["condition_guess"] in GUESSES
                and type(row["condition_guess_confidence"]) in {int, float}
                and 0 <= row["condition_guess_confidence"] <= 1, "Invalid review decision")
        known = {unit["evidence_id"] for unit in task["evidence_catalog"]}
        require(isinstance(row["citations"], list) and len(row["citations"]) <= 10
                and (row["label"] in {"uncertain", "not_applicable"} or bool(row["citations"])),
                "Invalid review evidence count")
        cited = set()
        for citation in row["citations"]:
            require(isinstance(citation, dict) and set(citation) == {"evidence_id", "relevance"}
                    and citation["evidence_id"] in known and citation["evidence_id"] not in cited
                    and isinstance(citation["relevance"], str) and citation["relevance"].strip(),
                    "Invalid review evidence")
            cited.add(citation["evidence_id"])
    return deepcopy({**submission, "sha256": digest(submission)})


def adjudication_packet(panel, packets, submissions):
    require(panel.get("sha256") == digest({key: value for key, value in panel.items() if key != "sha256"}),
            "Panel checksum mismatch")
    require(len(packets) == len(submissions) == 2, "Two independent submissions required")
    validated = [validate_submission(packet, submission) for packet, submission in zip(packets, submissions)]
    require(len({item["reviewer"]["id"] for item in submissions}) == 2, "Reviewers must be distinct")
    alias_to_blind = {}
    for slot in panel["slots"]:
        for assignment in slot["assignments"]:
            alias_to_blind[(slot["slot_id"], assignment["task_id"])] = assignment["blind_id"]
    labels = {}
    for submission in submissions:
        for row in submission["rows"]:
            blind_id = alias_to_blind[(submission["slot_id"], row["task_id"])]
            labels.setdefault(blind_id, []).append(deepcopy(row))
    master = {item["blind_id"]: item for item in panel["master"]}
    disagreements = []
    for blind_id, rows in labels.items():
        require(len(rows) == 2, "Both reviewers must cover every source case")
        if len({row["label"] for row in rows}) > 1:
            disagreements.append({"adjudication_id": "D-" + blind_id[1:],
                "task": master[blind_id]["task"], "independent_rows": rows,
                "based_on": sorted(digest(row) for row in rows)})
    raw = {"schema": "g5-blinded-reference-adjudication-packet-v1",
        "classification": "internal-human-adjudicator-only", "panel_sha256": panel["sha256"],
        "submission_sha256": sorted(item["sha256"] for item in validated),
        "disagreements": sorted(disagreements, key=lambda item: item["adjudication_id"])}
    return {**raw, "sha256": digest(raw)}
