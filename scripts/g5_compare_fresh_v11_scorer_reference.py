#!/usr/bin/env python3
"""Compare v11 scorer outputs with the pre-scoring frozen AI reference."""
from collections import Counter
import json
import os
from pathlib import Path

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-preflight")
PRED = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-predictions")
OUTPUT = PRED / "reference-comparison.json"
EXPECTED_INPUT_SHA = "ac09d92494c00ad9994b547017b113b344eafbed7a645e331d756db8b7f89ae0"
EXPECTED_PACKET_SHA = "bd53cfb2ec789c08dec0a2e44a85b0a3c9281f850e012c518f5c5d55e080028d"
EXPECTED_REFERENCE_FILE_SHA = "96f289023dbb2fa60cb1fd9d49b292802753d9342cc78723e4af0ef415fb5dc0"
EXPECTED_REFERENCE_FREEZE_SHA = "b254e54a449da39985de12c633c045ba4b340b3a8b0416b2cc374172ff1f4b7a"
EXPECTED_SCORER_AUDIT_SHA = "38de69a28d83d21ef523b388385e99a47a337e180716b958c9b9f3c7602a151a"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_digest(value, expected):
    if value.get("sha256") != expected or digest({k: v for k, v in value.items()
                                                  if k != "sha256"}) != expected:
        raise ValueError("Frozen artifact changed")


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def summarize(rows):
    decisive = [row for row in rows if row["reference"] in {"clear", "violation"}]
    pairs = Counter((row["reference"], row["prediction"]) for row in decisive)
    tp, tn = pairs[("violation", "violation")], pairs[("clear", "clear")]
    fp, fn = pairs[("clear", "violation")], pairs[("violation", "clear")]
    ratio = lambda n, d: n / d if d else None
    return {"total": len(rows), "decisive_reference": len(decisive),
        "uncertain_reference": sum(row["reference"] == "uncertain" for row in rows),
        "not_applicable_reference": sum(row["reference"] == "not_applicable" for row in rows),
        "prediction_clear": sum(row["prediction"] == "clear" for row in rows),
        "prediction_violation": sum(row["prediction"] == "violation" for row in rows),
        "prediction_abstain": sum(row["prediction"] == "abstain" for row in rows),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "exact_agreement_decisive": tp + tn,
        "agreement_rate_decisive": ratio(tp + tn, len(decisive)),
        "false_positive_rate_decisive": ratio(fp, fp + tn),
        "false_negative_rate_decisive": ratio(fn, fn + tp)}


def main():
    inputs, coordinator = load(PRE / "inputs.json"), load(PRE / "coordinator.json")
    packet, reference = load(PRE / "reviewer-a.json"), load(PRE / "ai-reference-a.json")
    freeze, audit = load(PRE / "ai-reference-freeze.json"), load(PRED / "audit.json")
    validate_digest(inputs, EXPECTED_INPUT_SHA)
    validate_digest(packet, EXPECTED_PACKET_SHA)
    validate_digest(freeze, EXPECTED_REFERENCE_FREEZE_SHA)
    validate_digest(audit, EXPECTED_SCORER_AUDIT_SHA)
    import hashlib
    if hashlib.sha256((PRE / "ai-reference-a.json").read_bytes()).hexdigest() \
            != EXPECTED_REFERENCE_FILE_SHA:
        raise ValueError("Reference file changed")
    if reference["packet_sha256"] != packet["sha256"] or not freeze["frozen_before_model_scoring"]:
        raise ValueError("Reference was not properly frozen")

    blind_to_source = {item["blind_id"]: item["source_case_id"]
                       for item in coordinator["master"]}
    slot = next(item for item in coordinator["slots"] if item["slot_id"] == packet["slot_id"])
    alias_to_source = {item["task_id"]: blind_to_source[item["blind_id"]]
                       for item in slot["assignments"]}
    references = {alias_to_source[row["task_id"]]: row["label"] for row in reference["rows"]}
    if len(references) != 48:
        raise ValueError("Reference mapping incomplete")
    case_info = {case["task"]["case_id"]: case for case in inputs["cases"]}
    final = {row["case_id"]: row for row in audit["final_cases"]}
    if set(references) != set(case_info) or set(final) != set(case_info):
        raise ValueError("Comparison coverage differs")

    rows = []
    for case_id in sorted(case_info):
        case, prediction = case_info[case_id], final[case_id]
        if prediction["status"] != "completed":
            raise ValueError("Final scorer result missing")
        rows.append({"case_id": case_id, "family": case["source_family"],
            "scenario_id": case["source_run_id"], "dimension": case["task"]["dimension"],
            "reference": references[case_id], "prediction": prediction["prediction"],
            "agreement": references[case_id] == prediction["prediction"]})

    overall = summarize(rows)
    by_dimension = {value: summarize([row for row in rows if row["dimension"] == value])
                    for value in sorted({row["dimension"] for row in rows})}
    by_family = {value: summarize([row for row in rows if row["family"] == value])
                 for value in sorted({row["family"] for row in rows})}
    disagreements = [row for row in rows
                     if row["reference"] in {"clear", "violation"} and not row["agreement"]]
    raw = {"schema": "g5-fresh-v11-ai-reference-comparison-v1",
        "classification": "single-ai-expert-development-diagnostic",
        "input_sha256": inputs["sha256"], "reference_freeze_sha256": freeze["sha256"],
        "scorer_audit_sha256": audit["sha256"], "rows": rows, "overall": overall,
        "by_dimension": by_dimension, "by_family": by_family,
        "decisive_disagreements": disagreements,
        "condition_guessing_assessed_separately": True,
        "architecture_effect_estimable": False, "human_accuracy_estimable": False,
        "gate_threshold_pre_frozen": False, "qualification": "not_inferred",
        "interpretation": "Agreement with one independent AI development reference; dimensions share eight dialogues. No threshold was frozen before outputs, so this report cannot retrospectively pass a gate or estimate human accuracy."}
    result = {**raw, "sha256": digest(raw)}
    save(OUTPUT, result)
    print(json.dumps({"overall": overall,
        "dimension_agreement": {key: value["agreement_rate_decisive"]
                                for key, value in by_dimension.items()},
        "disagreements": len(disagreements), "sha256": result["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
