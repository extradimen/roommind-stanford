#!/usr/bin/env python3
"""Freeze a deterministic post-hoc diagnosis of the failed v17 scorer-v4 gate.

This command performs no model calls.  The category assignments are explicitly
post-hoc development diagnoses and cannot be used as validation evidence.
"""
from collections import Counter
import json
import os
from pathlib import Path

from app.factorial_study import digest


PRE = Path("research/experiments/2026-09-14-g5-fresh-family-v17-scorer-preflight")
REF = Path("research/experiments/2026-09-15-g5-fresh-family-v17-reference-adjudication-preflight")
PRED = Path("research/experiments/2026-09-15-g5-fresh-family-v17-scorer-predictions")
OUT = Path("research/experiments/2026-09-15-g5-fresh-family-v17-scorer-v4-failure-diagnosis")
EXPECTED_INPUT_SHA = "ea35300e0680a1146f0daf998a3d28ebfe786cdf587cd6e65430b97e589c68ea"
EXPECTED_REFERENCE_SHA = "a7b9dad9ede1d5cdab753be841b8c47551c89ed2eefdced2cc9797b892a89a30"
EXPECTED_AUDIT_SHA = "ea9a03c43c763487e6ee726c7c9142d9ccff4dffe2d00099a3ad9e812f17b64d"
EXPECTED_COMPARISON_SHA = "c8d4bff17e037d0eae0b1e0f4bbf2ccc04efdd7f29eb6a31373e31b2faf69080"


CATEGORIES = {
    "fresh-v17-archive-collection-transfer-v1-procedural_fidelity":
        "role_objection_vs_authoritative_workflow_boundary",
    "fresh-v17-archive-collection-transfer-v2-epistemic_fidelity":
        "role_objection_vs_authoritative_workflow_boundary",
    "fresh-v17-archive-collection-transfer-v2-temporal_coherence":
        "role_objection_vs_authoritative_workflow_boundary",
    "fresh-v17-orchard-frost-response-v1-procedural_fidelity":
        "operation_effect_mistaken_for_prerequisite",
    "fresh-v17-orchard-frost-response-v1-role_strategy":
        "operation_effect_mistaken_for_prerequisite",
    "fresh-v17-orchard-frost-response-v2-procedural_fidelity":
        "operation_effect_mistaken_for_prerequisite",
    "fresh-v17-orchard-frost-response-v2-role_strategy":
        "operation_effect_mistaken_for_prerequisite",
    "fresh-v17-satellite-ground-pass-v1-epistemic_fidelity":
        "unsupported_operational_availability_claim",
    "fresh-v17-satellite-ground-pass-v1-interaction_structure_fidelity":
        "interaction_progress_overridden_by_early_repetition",
    "fresh-v17-school-meal-allergen-recall-v1-epistemic_fidelity":
        "opaque_trace_overinterpreted",
    "fresh-v17-school-meal-allergen-recall-v1-interaction_structure_fidelity":
        "extended_repetition_or_fragmentation_missed",
    "fresh-v17-school-meal-allergen-recall-v2-epistemic_fidelity":
        "opaque_trace_overinterpreted",
    "fresh-v17-school-meal-allergen-recall-v2-interaction_structure_fidelity":
        "generic_request_overcalled_as_unanswered_obligation",
    "fresh-v17-school-meal-allergen-recall-v2-temporal_coherence":
        "post_receipt_stale_state_missed",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_digest(value, expected):
    actual = digest({key: item for key, item in value.items() if key != "sha256"})
    if value.get("sha256") != expected or actual != expected:
        raise ValueError(f"Frozen artifact changed: expected {expected}")


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    inputs = load(PRE / "inputs.json")
    reference = load(REF / "final-ai-reference.json")
    audit = load(PRED / "audit.json")
    comparison = load(PRED / "reference-comparison-and-gate.json")
    for value, expected in ((inputs, EXPECTED_INPUT_SHA),
                            (reference, EXPECTED_REFERENCE_SHA),
                            (audit, EXPECTED_AUDIT_SHA),
                            (comparison, EXPECTED_COMPARISON_SHA)):
        validate_digest(value, expected)
    if comparison["gate"]["passed"] or comparison["architecture_effect_estimable"]:
        raise ValueError("Diagnosis requires a failed development-only gate")

    coordinator = load(PRE / "coordinator.json")
    blind_to_case = {row["blind_id"]: row["source_case_id"]
                     for row in coordinator["master"]}
    aliases = {}
    for slot in coordinator["slots"]:
        for assignment in slot["assignments"]:
            aliases[(slot["slot_id"], assignment["task_id"])] = \
                blind_to_case[assignment["blind_id"]]

    raters = {}
    for name in ("a", "b"):
        submission = load(REF / f"ai-reference-{name}.json")
        raters[name] = {
            aliases[(submission["slot_id"], row["task_id"])]: row
            for row in submission["rows"]
        }
    cases = set(raters["a"])
    if cases != set(raters["b"]) or len(cases) != 48:
        raise ValueError("Independent reference coverage changed")

    pair_counts = Counter((raters["a"][case]["label"], raters["b"][case]["label"])
                          for case in cases)
    observed = sum(count for (left, right), count in pair_counts.items()
                   if left == right) / len(cases)
    left_counts = Counter(row["label"] for row in raters["a"].values())
    right_counts = Counter(row["label"] for row in raters["b"].values())
    expected = sum(left_counts[label] / len(cases) * right_counts[label] / len(cases)
                   for label in set(left_counts) | set(right_counts))
    kappa = (observed - expected) / (1 - expected)

    disagreements = comparison["decisive_disagreements_or_failures"]
    mismatch_ids = {row["case_id"] for row in disagreements}
    if mismatch_ids != set(CATEGORIES) or len(disagreements) != 14:
        raise ValueError("Frozen mismatch set changed")
    rows = []
    for row in disagreements:
        case_id = row["case_id"]
        scorer = load(PRED / f"{case_id}.1.result.json")
        if scorer["status"] != "completed":
            raise ValueError("Unexpected failed scorer result")
        rows.append({
            "case_id": case_id,
            "dimension": row["dimension"],
            "family": row["family"],
            "error_direction": "false_positive" if row["reference"] == "clear"
                               else "false_negative",
            "post_hoc_category": CATEGORIES[case_id],
            "reference_label": row["reference"],
            "reference_basis": row["reference_basis"],
            "reviewer_a": raters["a"][case_id],
            "reviewer_b": raters["b"][case_id],
            "scorer_prediction": row["prediction"],
            "scorer_rationale": scorer["protocol"]["output"]["rationale"],
            "scorer_citations": scorer["protocol"]["output"]["model_citations"],
        })

    category_counts = Counter(row["post_hoc_category"] for row in rows)
    raw = {
        "schema": "g5-fresh-v17-scorer-v4-failure-diagnosis-v1",
        "classification": "post-hoc-development-diagnosis-only",
        "source_input_sha256": inputs["sha256"],
        "reference_sha256": reference["sha256"],
        "scorer_audit_sha256": audit["sha256"],
        "comparison_sha256": comparison["sha256"],
        "independent_ai_reference_reliability": {
            "n": len(cases),
            "agreement": observed,
            "expected_agreement": expected,
            "cohen_kappa": kappa,
            "pair_counts": {f"{left}|{right}": count
                            for (left, right), count in sorted(pair_counts.items())},
        },
        "mismatch_count": len(rows),
        "false_positive_count": sum(row["error_direction"] == "false_positive" for row in rows),
        "false_negative_count": sum(row["error_direction"] == "false_negative" for row in rows),
        "category_counts": dict(sorted(category_counts.items())),
        "rows": sorted(rows, key=lambda row: row["case_id"]),
        "decision": {
            "scorer_v4_primary_measurement_qualified": False,
            "reuse_v17_to_qualify_a_revised_scorer": False,
            "screening_32_authorized": False,
            "next_measurement_step": "two_independent_human_reviews_of_all_48_cells_then_blinded_adjudication",
            "reason": "Two prospective untouched-set qualifications produced 70.8% agreement; further prompt tuning on v17 would be exposed development, and the current AI-only reference cannot establish human accuracy.",
        },
        "limitations": [
            "Categories were assigned after scorer outputs were revealed.",
            "The reference is based on two AI reviewers plus AI adjudication, not human gold labels.",
            "No architecture effect is estimable from these selected development dialogues.",
        ],
    }
    result = {**raw, "sha256": digest(raw)}
    OUT.mkdir(exist_ok=False, mode=0o700)
    save(OUT / "diagnosis.json", result)
    print(json.dumps({
        "mismatches": len(rows),
        "false_positives": result["false_positive_count"],
        "false_negatives": result["false_negative_count"],
        "reference_agreement": observed,
        "reference_kappa": kappa,
        "categories": result["category_counts"],
        "sha256": result["sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
