"""Opt-in v2 case report; retain v1 accounting and bound unresolved predictions.

Bounds concern possible binary completions, not confidence intervals, abstention
costs, unknown reference truth, or calibrated deployed population error rates.
"""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.calibration_bridge import report as legacy_report
from app.g5.measurement import require


def _reference_bounds(cases):
    result = {}
    for label, error_label in (("clear", "violation"), ("violation", "clear")):
        subset = [c for c in cases if c["reference_label"] == label]
        n = len(subset)
        errors = sum(c["prediction"] == error_label for c in subset)
        decisive = sum(c["prediction"] in {"clear", "violation"} for c in subset)
        unresolved = {"missing": sum(c["prediction_status"] == "missing" for c in subset),
            "technical_failure": sum(c["prediction_status"] == "technical_failure" for c in subset),
            "abstain": sum(c["prediction"] == "abstain" for c in subset)}
        m = sum(unresolved.values())
        require(decisive + m == n, "Unclassified reference-stratum prediction")
        result[label] = {"reference_total": n, "observed_errors": errors,
            "decisive_predictions": decisive, "unresolved_predictions": m, "unresolved_by_reason": unresolved,
            "decisive_coverage": decisive / n if n else None,
            "error_fraction_decisive": errors / decisive if decisive else None,
            "possible_binary_error_fraction_bounds": [errors / n, (errors + m) / n] if n else None}
    return result


def report(annotation, results):
    base = legacy_report(annotation, results)  # Full source/label/attempt revalidation.
    raw = deepcopy({k: v for k, v in base.items() if k != "sha256"})
    raw.update(schema="g5-case-calibration-report-v2", legacy_report_sha256=base["sha256"],
        bounds_interpretation="Bounds over possible binary completions among resolved clear/violation references, not confidence intervals. Unknown reference cases remain in overall accounting but are not assigned truth.")
    raw["overall"]["reference_strata"] = _reference_bounds(base["cases"])
    for axis, levels in raw["strata"].items():
        for level, summary in levels.items():
            summary["reference_strata"] = _reference_bounds([c for c in base["cases"] if c[axis] == level])
    return {**raw, "sha256": digest(raw)}
