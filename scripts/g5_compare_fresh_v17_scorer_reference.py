#!/usr/bin/env python3
"""Apply the prospectively frozen scorer-v4 gate to the v17 validation."""
from collections import Counter
import json
import os
from pathlib import Path

from app.factorial_study import digest


PLAN = Path("research/experiments/2026-09-14-g5-scorer-v4-prospective-plan/plan.json")
PRE = Path("research/experiments/2026-09-14-g5-fresh-family-v17-scorer-preflight")
REF = Path("research/experiments/2026-09-15-g5-fresh-family-v17-reference-adjudication-preflight/final-ai-reference.json")
PRED = Path("research/experiments/2026-09-15-g5-fresh-family-v17-scorer-predictions")
OUTPUT = PRED / "reference-comparison-and-gate.json"
EXPECTED_PLAN_SHA = "7967fac8a92743fe17e457a54fa6d5d20f266032d24c6e9d3a344959959370f0"
EXPECTED_INPUT_SHA = "ea35300e0680a1146f0daf998a3d28ebfe786cdf587cd6e65430b97e589c68ea"
EXPECTED_REFERENCE_SHA = "a7b9dad9ede1d5cdab753be841b8c47551c89ed2eefdced2cc9797b892a89a30"
EXPECTED_AUDIT_SHA = "ea9a03c43c763487e6ee726c7c9142d9ccff4dffe2d00099a3ad9e812f17b64d"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_digest(value, expected):
    if value.get("sha256") != expected or digest(
            {key: item for key, item in value.items() if key != "sha256"}) != expected:
        raise ValueError(f"Frozen artifact changed: expected {expected}")


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(rows):
    decisive = [row for row in rows if row["reference"] in {"clear", "violation"}]
    pairs = Counter((row["reference"], row["prediction"]) for row in decisive)
    tp, tn = pairs[("violation", "violation")], pairs[("clear", "clear")]
    fp, fn = pairs[("clear", "violation")], pairs[("violation", "clear")]
    return {
        "total": len(rows),
        "decisive_reference": len(decisive),
        "completed_predictions": sum(row["status"] == "completed" for row in rows),
        "technical_failures": sum(row["status"] == "technical_failure" for row in rows),
        "prediction_clear": sum(row["prediction"] == "clear" for row in rows),
        "prediction_violation": sum(row["prediction"] == "violation" for row in rows),
        "prediction_abstain": sum(row["prediction"] == "abstain" for row in rows),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "exact_agreement_decisive": tp + tn,
        # A missing prediction cannot agree. The separate zero-failure rule also fails it.
        "agreement_rate_decisive": ratio(tp + tn, len(decisive)),
        "false_positive_rate_decisive": ratio(fp, sum(
            row["reference"] == "clear" for row in decisive)),
        "false_negative_rate_decisive": ratio(fn, sum(
            row["reference"] == "violation" for row in decisive)),
        "scorer_abstention_rate": ratio(sum(
            row["prediction"] == "abstain" for row in rows), len(rows)),
    }


def main():
    plan, inputs, reference, audit = (load(PLAN), load(PRE / "inputs.json"),
                                      load(REF), load(PRED / "audit.json"))
    for value, expected in ((plan, EXPECTED_PLAN_SHA), (inputs, EXPECTED_INPUT_SHA),
                            (reference, EXPECTED_REFERENCE_SHA), (audit, EXPECTED_AUDIT_SHA)):
        validate_digest(value, expected)
    if not reference["frozen_before_model_scoring"] or reference["model_predictions_seen"]:
        raise ValueError("Reference was not blinded and frozen before scorer calls")
    if reference["source_input_sha256"] != inputs["sha256"] \
            or audit["input_sha256"] != inputs["sha256"]:
        raise ValueError("Inputs, reference, and predictions are not bound to one artifact")

    case_info = {case["task"]["case_id"]: case for case in inputs["cases"]}
    references = {row["case_id"]: row for row in reference["rows"]}
    finals = {row["case_id"]: row for row in audit["final_cases"]}
    if len(case_info) != 48 or set(case_info) != set(references) or set(case_info) != set(finals):
        raise ValueError("Comparison coverage differs")

    rows = []
    for case_id in sorted(case_info):
        case, ref, prediction = case_info[case_id], references[case_id], finals[case_id]
        if ref["dimension"] != case["task"]["dimension"]:
            raise ValueError("Reference dimension differs")
        rows.append({
            "case_id": case_id,
            "family": case["source_family"],
            "scenario_id": case["source_run_id"],
            "dimension": case["task"]["dimension"],
            "reference": ref["label"],
            "reference_basis": ref["basis"],
            "status": prediction["status"],
            "prediction": prediction["prediction"],
            "agreement": prediction["status"] == "completed"
                         and ref["label"] == prediction["prediction"],
        })

    overall = summarize(rows)
    by_dimension = {dimension: summarize([row for row in rows
                                          if row["dimension"] == dimension])
                    for dimension in sorted({row["dimension"] for row in rows})}
    by_family = {family: summarize([row for row in rows if row["family"] == family])
                 for family in sorted({row["family"] for row in rows})}
    threshold = plan["acceptance_gate"]
    checks = {
        "final_completed_cells": overall["completed_predictions"]
            == threshold["final_completed_cells"],
        "technical_failure_after_retry": overall["technical_failures"]
            <= threshold["maximum_technical_failure_after_retry"],
        "decisive_reference_cells": overall["decisive_reference"]
            >= threshold["minimum_decisive_reference_cells"],
        "decisive_agreement": overall["agreement_rate_decisive"]
            >= threshold["minimum_decisive_agreement"],
        "false_positive_rate": overall["false_positive_rate_decisive"]
            <= threshold["maximum_false_positive_rate"],
        "false_negative_rate": overall["false_negative_rate_decisive"]
            <= threshold["maximum_false_negative_rate"],
        "decisive_cells_each_dimension": all(
            item["decisive_reference"] >= threshold["minimum_decisive_cells_per_dimension"]
            for item in by_dimension.values()),
        "agreement_each_dimension": all(
            item["agreement_rate_decisive"] >= threshold["minimum_agreement_each_dimension"]
            for item in by_dimension.values()),
        "scorer_abstention_rate": overall["scorer_abstention_rate"]
            <= threshold["maximum_scorer_abstention_rate"],
    }
    passed = all(checks.values())
    disagreements = [row for row in rows if not row["agreement"]]
    raw = {
        "schema": "g5-fresh-v17-ai-reference-comparison-and-prospective-gate-v1",
        "classification": "two-ai-reference-development-qualification",
        "prospective_plan_sha256": plan["sha256"],
        "input_sha256": inputs["sha256"],
        "reference_sha256": reference["sha256"],
        "scorer_audit_sha256": audit["sha256"],
        "rows": rows,
        "overall": overall,
        "by_dimension": by_dimension,
        "by_family": by_family,
        "decisive_disagreements_or_failures": disagreements,
        "gate": {"all_must_hold": True, "checks": checks,
                 "passed": passed, "decision": "qualify" if passed else "fail"},
        "architecture_effect_estimable": False,
        "human_accuracy_estimable": False,
        "confirmation_eligible": False,
        "screening_32_authorized": False,
        "interpretation": "Prospective scorer qualification against a frozen two-AI development reference with third-AI adjudication. It does not estimate human accuracy or an architecture effect.",
    }
    result = {**raw, "sha256": digest(raw)}
    save(OUTPUT, result)
    print(json.dumps({
        "overall": overall,
        "dimension_agreement": {key: value["agreement_rate_decisive"]
                                for key, value in by_dimension.items()},
        "failed_checks": [key for key, value in checks.items() if not value],
        "gate_passed": passed,
        "disagreements_or_failures": len(disagreements),
        "sha256": result["sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
