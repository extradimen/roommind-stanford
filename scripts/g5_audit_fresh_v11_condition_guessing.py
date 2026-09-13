#!/usr/bin/env python3
"""Audit blinded four-arm guesses at the dialogue level; no model calls."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-preflight")
PRED = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-predictions")
OUTPUT = PRED / "condition-guess-audit.json"
EXPECTED_GUESS_FILE_SHA = "1620ad6039e9ac6547acfb347c4e38348f535540d5311e05a5f48f68f67e4110"
ARM_MEANING = {"A": "neither_mechanism", "B": "cognition_only",
               "C": "governance_only", "D": "both_mechanisms"}
VALID_GUESSES = {*ARM_MEANING.values(), "uncertain"}


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
    guess_path = PRE / "ai-condition-guesses-a.json"
    if hashlib.sha256(guess_path.read_bytes()).hexdigest() != EXPECTED_GUESS_FILE_SHA:
        raise ValueError("Blinded condition guesses changed")
    guesses, coordinator = load(guess_path), load(PRE / "coordinator.json")
    inputs, packet = load(PRE / "inputs.json"), load(PRE / "reviewer-a.json")
    if (guesses.get("packet_sha256") != packet["sha256"]
            or guesses.get("condition_material_seen") is not False
            or guesses.get("model_predictions_seen") is not False
            or guesses.get("labels_already_frozen") is not True):
        raise ValueError("Condition-guess provenance changed")

    blind_to_source = {item["blind_id"]: item["source_case_id"]
                       for item in coordinator["master"]}
    slot = next(item for item in coordinator["slots"] if item["slot_id"] == packet["slot_id"])
    alias_to_source = {item["task_id"]: blind_to_source[item["blind_id"]]
                       for item in slot["assignments"]}
    cases = {case["task"]["case_id"]: case for case in inputs["cases"]}
    all_aliases, rows = set(), []
    for item in guesses["rows"]:
        if (set(item) != {"evidence_catalog_sha256", "task_ids", "guess", "confidence", "rationale"}
                or item["guess"] not in VALID_GUESSES
                or type(item["confidence"]) not in {int, float}
                or not 0 <= item["confidence"] <= 1
                or not isinstance(item["rationale"], str) or not item["rationale"].strip()
                or len(item["task_ids"]) != 6):
            raise ValueError("Invalid condition guess")
        if all_aliases & set(item["task_ids"]):
            raise ValueError("Repeated task in condition guesses")
        all_aliases.update(item["task_ids"])
        source_cases = [cases[alias_to_source[alias]] for alias in item["task_ids"]]
        scenarios = {case["source_run_id"] for case in source_cases}
        arms = {case["source_condition"] for case in source_cases}
        dimensions = {case["task"]["dimension"] for case in source_cases}
        if len(scenarios) != 1 or len(arms) != 1 or len(dimensions) != 6:
            raise ValueError("Guess does not cover exactly one complete dialogue")
        arm = arms.pop()
        actual = ARM_MEANING[arm]
        rows.append({"scenario_id": scenarios.pop(), "actual": actual,
            "guess": item["guess"], "confidence": item["confidence"],
            "correct": item["guess"] == actual})
    if all_aliases != {task["task_id"] for task in packet["tasks"]} or len(rows) != 8:
        raise ValueError("Condition-guess coverage incomplete")

    decisive = [row for row in rows if row["guess"] != "uncertain"]
    raw = {"schema": "g5-fresh-v11-condition-guess-audit-v1",
        "classification": "single-ai-expert-development-diagnostic",
        "guess_file_sha256": EXPECTED_GUESS_FILE_SHA, "dialogues": 8,
        "rows": sorted(rows, key=lambda row: row["scenario_id"]),
        "guess_counts": dict(sorted(Counter(row["guess"] for row in rows).items())),
        "decisive_guesses": len(decisive),
        "correct_all_dialogues": sum(row["correct"] for row in rows),
        "correct_decisive": sum(row["correct"] for row in decisive),
        "accuracy_all_dialogues": sum(row["correct"] for row in rows) / len(rows),
        "accuracy_decisive": (sum(row["correct"] for row in decisive) / len(decisive)
                               if decisive else None),
        "interpretation": "Descriptive residual-blinding diagnostic from one AI reviewer; eight dialogues are the units. Low-confidence guesses are not architecture-effect evidence.",
        "architecture_effect_estimable": False, "confirmation_eligible": False}
    result = {**raw, "sha256": digest(raw)}
    save(OUTPUT, result)
    print(json.dumps({key: result[key] for key in ("dialogues", "guess_counts",
        "decisive_guesses", "correct_all_dialogues", "correct_decisive",
        "accuracy_all_dialogues", "accuracy_decisive", "sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
