#!/usr/bin/env python3
"""Validate the blinded adjudication and freeze the final two-AI development reference."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-14-g5-fresh-family-v14-scorer-preflight")
ADJ = Path("research/experiments/2026-09-14-g5-fresh-family-v14-reference-adjudication-preflight")
PRED = Path("research/experiments/2026-09-14-g5-fresh-family-v14-scorer-predictions")
EXPECTED_INPUT_SHA = "3c6a948f396fa7d68426df10b506f342188eccf8b57088701c7e841e11744f48"
EXPECTED_FREEZE_SHA = "b9e403f1129a44a5bf222d127c4ae395fa4432e54fa6b6312bb735d1c9a7a045"
EXPECTED_PACKET_SHA = "7394c877cfc5ea5aa842070f6f8f77f013d9c805966230432257cc07b3609ea0"
CHOICES = {"X", "Y", "neither", "uncertain"}


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


def main():
    if PRED.exists():
        raise ValueError("Final reference must freeze before scorer output exists")
    inputs, panel = load(PRE / "inputs.json"), load(PRE / "coordinator.json")
    freeze, packet = load(ADJ / "summary.json"), load(ADJ / "packet.json")
    coordinator, submission = load(ADJ / "coordinator.json"), load(ADJ / "ai-adjudication-draft.json")
    for value, expected in ((inputs, EXPECTED_INPUT_SHA), (freeze, EXPECTED_FREEZE_SHA),
                            (packet, EXPECTED_PACKET_SHA)):
        if value.get("sha256") != expected or digest({k: v for k, v in value.items() if k != "sha256"}) != expected:
            raise ValueError("Frozen reference artifact changed")
    if (set(submission) != {"schema", "packet_sha256", "reviewer", "rows"}
            or submission["schema"] != "g5-fresh-v14-ai-reference-adjudication-submission-v1"
            or submission["packet_sha256"] != EXPECTED_PACKET_SHA
            or submission["reviewer"] != {"id": "codex-independent-v14-adjudicator", "kind": "ai"}):
        raise ValueError("Invalid AI adjudication submission")
    items = {item["adjudication_id"]: item for item in packet["items"]}
    mapping = {item["adjudication_id"]: item for item in coordinator["mapping"]}
    if set(items) != set(mapping) or len(items) != freeze["disagreements"]:
        raise ValueError("Adjudication coordinator mismatch")
    decisions, seen = {}, set()
    for row in submission["rows"]:
        if set(row) != {"adjudication_id", "item_sha256", "choice", "citations", "rationale"}:
            raise ValueError("Invalid adjudication row fields")
        aid, choice = row["adjudication_id"], row["choice"]
        item = items.get(aid)
        if item is None or aid in seen or row["item_sha256"] != item["sha256"] or choice not in CHOICES:
            raise ValueError("Invalid adjudication identity or choice")
        if not isinstance(row["rationale"], str) or not row["rationale"].strip() or not row["citations"]:
            raise ValueError("Incomplete adjudication decision")
        known = {entry["evidence_id"] for entry in item["task"]["evidence_catalog"]}
        cited = set()
        for citation in row["citations"]:
            if (set(citation) != {"evidence_id", "relevance"}
                    or citation["evidence_id"] not in known or citation["evidence_id"] in cited
                    or not isinstance(citation["relevance"], str) or not citation["relevance"].strip()):
                raise ValueError("Invalid adjudication citation")
            cited.add(citation["evidence_id"])
        if choice in {"X", "Y"}:
            label = item["assessments"][choice]["label"]
        else:
            label = "uncertain"
        decisions[mapping[aid]["blind_id"]] = {"label": label, "choice": choice,
            "adjudication_id": aid, "item_sha256": item["sha256"],
            "citations": row["citations"], "rationale": row["rationale"]}
        seen.add(aid)
    if seen != set(items):
        raise ValueError("Incomplete adjudication coverage")

    alias_to_blind = {}
    for slot in panel["slots"]:
        for assignment in slot["assignments"]:
            alias_to_blind[(slot["slot_id"], assignment["task_id"])] = assignment["blind_id"]
    references = [load(ADJ / f"ai-reference-{letter}.json") for letter in "ab"]
    by_blind = {}
    for reference in references:
        for row in reference["rows"]:
            blind = alias_to_blind[(reference["slot_id"], row["task_id"])]
            by_blind.setdefault(blind, []).append(row)
    master = {item["blind_id"]: item for item in panel["master"]}
    rows = []
    for blind in sorted(master):
        independent = by_blind[blind]
        labels = [row["label"] for row in independent]
        if labels[0] == labels[1]:
            label, basis, adjudication = labels[0], "independent_agreement", None
        else:
            result = decisions[blind]
            label, basis, adjudication = result["label"], "blinded_adjudication", result
        source_case_id = master[blind]["source_case_id"]
        dimension = next(case["task"]["dimension"] for case in inputs["cases"]
                         if case["task"]["case_id"] == source_case_id)
        rows.append({"case_id": source_case_id, "dimension": dimension, "label": label,
                     "basis": basis, "independent_label_hashes": sorted(digest(row) for row in independent),
                     "adjudication": adjudication})
    if len(rows) != 48 or len({row["case_id"] for row in rows}) != 48:
        raise ValueError("Final reference coverage mismatch")
    decisive_by_dimension = Counter(row["dimension"] for row in rows
                                    if row["label"] in {"clear", "violation"})
    raw = {"schema": "g5-fresh-v14-two-ai-development-reference-v1",
        "classification": "two-independent-ai-references-with-third-ai-adjudication",
        "source_input_sha256": EXPECTED_INPUT_SHA, "reference_freeze_sha256": EXPECTED_FREEZE_SHA,
        "adjudication_packet_sha256": EXPECTED_PACKET_SHA,
        "adjudication_submission_file_sha256": hashlib.sha256(
            (ADJ / "ai-adjudication-draft.json").read_bytes()).hexdigest(),
        "rows": rows, "label_counts": dict(sorted(Counter(row["label"] for row in rows).items())),
        "decisive_by_dimension": dict(sorted(decisive_by_dimension.items())),
        "condition_material_seen": False, "model_predictions_seen": False,
        "frozen_before_model_scoring": True, "human_reference": False,
        "human_accuracy_estimable": False, "confirmation_eligible": False}
    result = {**raw, "sha256": digest(raw)}
    save(ADJ / "final-ai-reference.json", result)
    print(json.dumps({"rows": 48, "label_counts": result["label_counts"],
                      "decisive_by_dimension": result["decisive_by_dimension"],
                      "sha256": result["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
