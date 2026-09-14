#!/usr/bin/env python3
"""Freeze two blinded AI references and create an origin-blinded disagreement packet."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-14-g5-fresh-family-v14-scorer-preflight")
TARGET = Path("research/experiments/2026-09-14-g5-fresh-family-v14-reference-adjudication-preflight")
EXPECTED_INPUT_SHA = "3c6a948f396fa7d68426df10b506f342188eccf8b57088701c7e841e11744f48"
LABELS = {"clear", "violation", "uncertain", "not_applicable"}
GUESSES = {"baseline", "roommind", "uncertain"}


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


def validate_ai_submission(packet, submission):
    expected = {"schema", "slot_id", "reviewer", "packet_sha256", "rows"}
    if (set(submission) != expected
            or submission["schema"] != "g5-blinded-reference-submission-v1"
            or submission["slot_id"] != packet["slot_id"]
            or submission["packet_sha256"] != packet["sha256"]):
        raise ValueError("Invalid AI reference submission")
    reviewer = submission["reviewer"]
    if (set(reviewer) != {"id", "kind"} or reviewer["kind"] != "ai"
            or not isinstance(reviewer["id"], str) or not reviewer["id"].strip()):
        raise ValueError("Declared AI reviewer required")
    tasks = {task["task_id"]: task for task in packet["tasks"]}
    if len(tasks) != 48 or len(submission["rows"]) != 48:
        raise ValueError("Incomplete AI reference coverage")
    seen = set()
    for row in submission["rows"]:
        if set(row) != set(packet["response_contract"]["row_fields"]):
            raise ValueError("Invalid AI reference row fields")
        task = tasks.get(row["task_id"])
        if task is None or row["task_id"] in seen or row["task_sha256"] != task["sha256"]:
            raise ValueError("Unknown, duplicate, or changed AI reference task")
        seen.add(row["task_id"])
        if (row["label"] not in LABELS or not isinstance(row["rationale"], str)
                or not row["rationale"].strip() or row["condition_guess"] not in GUESSES
                or type(row["condition_guess_confidence"]) not in {int, float}
                or not 0 <= row["condition_guess_confidence"] <= 1):
            raise ValueError("Invalid AI reference decision")
        citations = row["citations"]
        known = {item["evidence_id"] for item in task["evidence_catalog"]}
        if (not isinstance(citations, list) or len(citations) > 10
                or (row["label"] in {"clear", "violation"} and not citations)):
            raise ValueError("Invalid AI reference evidence count")
        cited = set()
        for citation in citations:
            if (set(citation) != {"evidence_id", "relevance"}
                    or citation["evidence_id"] not in known
                    or citation["evidence_id"] in cited
                    or not isinstance(citation["relevance"], str)
                    or not citation["relevance"].strip()):
                raise ValueError("Invalid AI reference citation")
            cited.add(citation["evidence_id"])
    return deepcopy(submission)


def main():
    inputs = load(PRE / "inputs.json")
    if (inputs.get("sha256") != EXPECTED_INPUT_SHA
            or digest({k: v for k, v in inputs.items() if k != "sha256"}) != EXPECTED_INPUT_SHA):
        raise ValueError("V14 scorer inputs changed")
    if PRE.parent.joinpath("2026-09-14-g5-fresh-family-v14-scorer-predictions").exists():
        raise ValueError("References must freeze before scorer output exists")
    coordinator = load(PRE / "coordinator.json")
    if coordinator.get("sha256") != digest({k: v for k, v in coordinator.items() if k != "sha256"}):
        raise ValueError("Coordinator checksum mismatch")
    packets = [load(PRE / f"reviewer-{letter}.json") for letter in "ab"]
    drafts = [load(PRE / f"ai-reference-{letter}-draft.json") for letter in "ab"]
    submissions = [validate_ai_submission(packet, draft)
                   for packet, draft in zip(packets, drafts)]
    if len({submission["reviewer"]["id"] for submission in submissions}) != 2:
        raise ValueError("AI reviewers must be distinct")

    alias_to_blind = {}
    for slot in coordinator["slots"]:
        for assignment in slot["assignments"]:
            alias_to_blind[(slot["slot_id"], assignment["task_id"])] = assignment["blind_id"]
    by_blind = {}
    for submission in submissions:
        for row in submission["rows"]:
            blind = alias_to_blind[(submission["slot_id"], row["task_id"])]
            by_blind.setdefault(blind, []).append((submission["slot_id"], row))
    master = {item["blind_id"]: item for item in coordinator["master"]}
    if set(by_blind) != set(master) or any(len(rows) != 2 for rows in by_blind.values()):
        raise ValueError("Independent reference coverage mismatch")

    items, mapping = [], []
    for blind in sorted(by_blind):
        rows = by_blind[blind]
        if rows[0][1]["label"] == rows[1][1]["label"]:
            continue
        assessments = []
        for slot_id, row in rows:
            assessments.append({"origin": slot_id, "label": row["label"],
                                "citations": deepcopy(row["citations"]),
                                "rationale": row["rationale"]})
        random.Random(int(digest([EXPECTED_INPUT_SHA, blind, "reference-adjudication-v1"])[:16], 16)).shuffle(assessments)
        sides, origins = {}, {}
        for side, assessment in zip(("X", "Y"), assessments):
            origins[side] = assessment.pop("origin")
            sides[side] = assessment
        task = {k: deepcopy(v) for k, v in master[blind]["task"].items()
                if k not in {"task_id", "sha256"}}
        adjudication_id = f"D-{len(items) + 1:03d}"
        raw = {"adjudication_id": adjudication_id, "task": task, "assessments": sides}
        items.append({**raw, "sha256": digest(raw)})
        mapping.append({"adjudication_id": adjudication_id, "blind_id": blind,
                        "source_case_id": master[blind]["source_case_id"],
                        "side_origins": origins})

    raw_packet = {"schema": "g5-fresh-v14-ai-reference-adjudication-packet-v1",
        "classification": "internal-independent-ai-adjudication-candidate",
        "instructions": "Using only the task, evidence catalog, and anonymous assessments X and Y, choose X, Y, neither, or uncertain. Cite evidence and apply only the named dimension. Do not infer condition, reviewer identity, or assessment origin.",
        "choices": ["X", "Y", "neither", "uncertain"], "items": items,
        "contains_conditions": False, "contains_reviewer_identities": False,
        "contains_model_predictions": False, "external_distribution_authorized": False}
    packet = {**raw_packet, "sha256": digest(raw_packet)}
    raw_coord = {"schema": "g5-fresh-v14-ai-reference-adjudication-coordinator-v1",
        "classification": "internal-coordinator-only", "input_sha256": EXPECTED_INPUT_SHA,
        "panel_sha256": coordinator["sha256"], "packet_sha256": packet["sha256"],
        "mapping": mapping}
    adjudication_coordinator = {**raw_coord, "sha256": digest(raw_coord)}
    template = {"schema": "g5-fresh-v14-ai-reference-adjudication-submission-v1",
        "packet_sha256": packet["sha256"], "reviewer": {"id": "", "kind": "ai"},
        "rows": [{"adjudication_id": item["adjudication_id"], "item_sha256": item["sha256"],
                  "choice": None, "citations": [], "rationale": ""} for item in items]}

    TARGET.mkdir(exist_ok=False, mode=0o700)
    for letter, submission in zip("ab", submissions):
        save(TARGET / f"ai-reference-{letter}.json", submission)
    for name, value in (("packet.json", packet), ("coordinator.json", adjudication_coordinator),
                        ("response-template.json", template)):
        save(TARGET / name, value)
    file_sha = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(TARGET.glob("*.json"))}
    counts = {letter: dict(sorted(Counter(row["label"] for row in submission["rows"]).items()))
              for letter, submission in zip("ab", submissions)}
    raw_summary = {"schema": "g5-fresh-v14-ai-reference-freeze-v1",
        "classification": "two-independent-ai-development-references",
        "source_input_sha256": EXPECTED_INPUT_SHA, "reference_rows_each": 48,
        "label_counts": counts, "agreements": 48 - len(items), "disagreements": len(items),
        "frozen_before_model_scoring": True, "condition_material_seen": False,
        "model_predictions_seen": False, "human_reference": False,
        "accuracy_claim_permitted": False, "confirmation_eligible": False,
        "file_sha256": file_sha}
    summary = {**raw_summary, "sha256": digest(raw_summary)}
    save(TARGET / "summary.json", summary)
    print(json.dumps({"label_counts": counts, "agreements": 48 - len(items),
                      "disagreements": len(items), "packet_sha256": packet["sha256"],
                      "freeze_sha256": summary["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
