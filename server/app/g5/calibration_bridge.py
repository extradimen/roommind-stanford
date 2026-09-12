"""Case-level calibration from audited labels and source-bound prediction attempts.

Read-only: no model calls, no label changes. Attempts are supplied in explicit
chronological order; only failed attempts may be retried. Identity is declared,
not authenticated. Descriptive ratios are not study effect estimates.
"""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.annotation_archive import AnnotationArchive, verify_export
from app.g5.measurement import require, sha


def freeze_predictor(predictor):
    require(isinstance(predictor, dict) and set(predictor) == {"id", "kind", "spec_sha256"}
        and isinstance(predictor["id"], str) and predictor["id"].strip()
        and predictor["kind"] in {"synthetic", "assistant", "ai", "human"}
        and sha(predictor["spec_sha256"]), "Frozen predictor provenance required")
    raw = {"schema": "g5-case-prediction-plan-v1", "predictor": deepcopy(predictor),
           "retry": "technical-failure-only", "unit": "case", "output": ["violation", "clear", "abstain"]}
    return {**raw, "sha256": digest(raw)}


def freeze_results(annotation, plan, attempts):
    references = verify_export(annotation)
    if "model_spec" in plan:
        from app.g5.calibration_predictor import validate_plan
        validate_plan(plan)
    else:
        require(freeze_predictor(plan["predictor"]) == plan, "Prediction plan changed")
    require(isinstance(attempts, list), "Prediction attempt list required")
    archive = AnnotationArchive(":memory:", annotation["manifest"], annotation["sources"], annotation["plan"])
    indexed, ids = {}, set()
    chain = digest([annotation["sha256"], plan["sha256"]])
    try:
        for row in attempts:
            require(isinstance(row, dict) and set(row) == {"id", "case_id", "previous_attempt_sha256", "artifact"}, "Invalid prediction attempt")
            require(isinstance(row["id"], str) and row["id"].strip() and row["id"] not in ids, "Duplicate prediction attempt ID")
            task = archive.task(row["case_id"])
            old = indexed.get(row["case_id"])
            require(row["previous_attempt_sha256"] == (digest(old) if old else None), "Retry predecessor changed")
            require(old is None or old["artifact"]["output"]["status"] == "technical_failure", "Completed prediction cannot be overwritten")
            artifact = row["artifact"]
            require(isinstance(artifact, dict) and set(artifact) == {"task", "predictor", "output", "raw_record"}
                and artifact["task"] == task and artifact["predictor"] == plan["predictor"]
                and isinstance(artifact["raw_record"], dict) and artifact["raw_record"], "Prediction raw provenance/input mismatch")
            output = artifact["output"]
            require(isinstance(output, dict) and set(output) == {"status", "prediction", "rationale"}
                and isinstance(output["rationale"], str) and output["rationale"].strip(), "Prediction explanation required")
            require((output["status"] == "technical_failure" and output["prediction"] is None)
                or (output["status"] == "completed" and output["prediction"] in {"clear", "violation", "abstain"}), "Invalid prediction outcome")
            # An adapter can retain provider-specific raw data; this bridge does
            # not certify raw_record as an authenticated remote model receipt.
            if "model_spec" in plan:
                from app.g5.calibration_predictor import validate_receipt
                validate_receipt(row, plan)
            indexed[row["case_id"]] = row
            ids.add(row["id"])
            chain = digest([chain, row])
    finally:
        archive.close()
    raw = {"schema": "g5-case-calibration-results-v1", "annotation_sha256": annotation["sha256"],
        "prediction_plan": deepcopy(plan), "attempts": deepcopy(attempts), "chain_sha256": chain,
        "reference_report_sha256": references["sha256"]}
    return {**raw, "sha256": digest(raw)}


def report(annotation, results):
    require(freeze_results(annotation, results["prediction_plan"], results["attempts"]) == results,
            "Calibration result bundle changed")
    references = verify_export(annotation)
    reference_map = {r["case_id"]: r for r in references["cases"]}
    latest = {r["case_id"]: r for r in results["attempts"]}
    cases = []
    for case in annotation["plan"]["plan"]["cases"]:
        ref = reference_map[case["id"]]
        output = latest.get(case["id"], {}).get("artifact", {}).get("output")
        cases.append({"case_id": case["id"], "family": annotation["manifest"]["assignments"][case["ordinal"] - 1]["family"],
            "ordinal": case["ordinal"], "dimension": case["dimension"], "category": case["category"],
            "reference_status": ref["status"], "reference_label": ref["label"],
            "reference_sources": "+".join(ref["declared_sources"]) or "unannotated",
            "prediction_status": output["status"] if output else "missing",
            "prediction": output["prediction"] if output else None})
    def summarize(subset):
        counts = {k: 0 for k in ("total_cases", "reference_awaiting", "reference_disputed", "reference_uncertain",
            "reference_not_applicable", "prediction_missing", "prediction_failed", "prediction_completed",
            "prediction_abstain", "tp", "tn", "fp", "fn")}
        for case in subset:
            counts["total_cases"] += 1
            for value, key in (("awaiting_annotations", "reference_awaiting"), ("disputed", "reference_disputed")):
                counts[key] += case["reference_status"] == value
            counts["reference_uncertain"] += case["reference_label"] == "uncertain"
            counts["reference_not_applicable"] += case["reference_label"] == "not_applicable"
            counts[{"missing": "prediction_missing", "technical_failure": "prediction_failed", "completed": "prediction_completed"}[case["prediction_status"]]] += 1
            counts["prediction_abstain"] += case["prediction"] == "abstain"
            if case["reference_label"] in {"clear", "violation"} and case["prediction"] in {"clear", "violation"}:
                key = {("clear", "clear"): "tn", ("clear", "violation"): "fp",
                       ("violation", "clear"): "fn", ("violation", "violation"): "tp"}[(case["reference_label"], case["prediction"])]
                counts[key] += 1
        ratio = lambda n, d: n / d if d else None
        decisive = sum(counts[k] for k in ("tp", "tn", "fp", "fn"))
        return {**counts, "decisive_pairs": decisive, "decisive_coverage": ratio(decisive, counts["total_cases"]),
            "false_positive_rate_decisive": ratio(counts["fp"], counts["fp"] + counts["tn"]),
            "false_negative_rate_decisive": ratio(counts["fn"], counts["fn"] + counts["tp"])}
    raw = {"schema": "g5-case-calibration-report-v1", "annotation_sha256": annotation["sha256"], "results_sha256": results["sha256"],
        "predictor": results["prediction_plan"]["predictor"], "cases": cases, "overall": summarize(cases),
        "unique_source_dialogues": len({c["ordinal"] for c in cases}),
        "technical_failure_attempts": sum(r["artifact"]["output"]["status"] == "technical_failure" for r in results["attempts"]),
        "strata": {key: {value: summarize([c for c in cases if c[key] == value]) for value in sorted({c[key] for c in cases})}
                   for key in ("family", "dimension", "category", "reference_sources")},
        "interpretation": "Descriptive case accounting; dimensions share sources, axes overlap, decisive ratios exclude unknowns; not independent samples or qualification.",
        "qualification": "not_inferred"}
    return {**raw, "sha256": digest(raw)}
