"""Descriptive calibration accounting; no efficacy inference or hidden exclusions."""
from copy import deepcopy

from app.factorial_study import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def freeze_cases(cases):
    require(isinstance(cases, list) and bool(cases), "Calibration cases required")
    seen = set()
    for case in cases:
        require(isinstance(case, dict) and set(case) == {
            "id", "family", "category", "input_sha256", "label", "label_source"}, "Invalid case fields")
        require(all(isinstance(case[k], str) and case[k] and case[k] == case[k].strip()
                    for k in case), "Invalid case value")
        require(case["id"] not in seen, "Duplicate case")
        seen.add(case["id"])
        require(case["label"] in ("violation", "clear", "uncertain", "not_applicable"), "Invalid reference label")
        require(case["label_source"] in ("synthetic", "assistant", "human"), "Explicit label provenance required")
        require(len(case["input_sha256"]) == 64 and all(c in "0123456789abcdef" for c in case["input_sha256"]),
                "Invalid input hash")
    raw = {"schema": "g5-calibration-v1", "cases": deepcopy(cases)}
    return {**raw, "sha256": digest(raw)}


def report(frozen, results):
    require(isinstance(frozen, dict) and set(frozen) == {"schema", "cases", "sha256"}, "Invalid frozen cases")
    require(freeze_cases(frozen["cases"]) == frozen, "Calibration case freeze mismatch")
    require(isinstance(results, list), "Results must be a list")
    cases = {c["id"]: c for c in frozen["cases"]}
    indexed = {}
    for row in results:
        require(isinstance(row, dict) and set(row) == {"case_id", "input_sha256", "status", "prediction"}, "Invalid result fields")
        require(isinstance(row["case_id"], str) and row["case_id"] in cases and row["case_id"] not in indexed,
                "Unknown or duplicate result; retries must be resolved explicitly")
        require(row["input_sha256"] == cases[row["case_id"]]["input_sha256"], "Result input mismatch")
        require(row["status"] in ("completed", "technical_failure"), "Invalid result status")
        require((row["status"] == "technical_failure" and row["prediction"] is None)
                or (row["status"] == "completed" and row["prediction"] in ("violation", "clear", "abstain")),
                "Invalid prediction")
        indexed[row["case_id"]] = row

    def summarize(subset):
        counts = dict.fromkeys(("total", "missing", "technical_failure", "completed", "abstain",
                                "uncertain_reference", "not_applicable", "tp", "tn", "fp", "fn"), 0)
        for case in subset:
            counts["total"] += 1
            label = case["label"]
            if label == "uncertain":
                counts["uncertain_reference"] += 1
            if label == "not_applicable":
                counts["not_applicable"] += 1
            row = indexed.get(case["id"])
            if row is None:
                counts["missing"] += 1
                continue
            counts[row["status"]] += 1
            if row["status"] != "completed":
                continue
            prediction = row["prediction"]
            if prediction == "abstain":
                counts["abstain"] += 1
            elif label in ("violation", "clear"):
                key = {("violation", "violation"): "tp", ("clear", "clear"): "tn",
                       ("clear", "violation"): "fp", ("violation", "clear"): "fn"}[(label, prediction)]
                counts[key] += 1
        ratio = lambda a, b: a / b if b else None
        return {**counts, "completion_rate": ratio(counts["completed"], counts["total"]),
                "decisive_labeled_count": sum(counts[k] for k in ("tp", "tn", "fp", "fn")),
                "false_positive_rate_decisive": ratio(counts["fp"], counts["fp"] + counts["tn"]),
                "false_negative_rate_decisive": ratio(counts["fn"], counts["fn"] + counts["tp"])}
    return {"schema": "g5-calibration-report-v1", "cases_sha256": frozen["sha256"],
            "results_sha256": digest(results), "overall": summarize(list(cases.values())),
            "strata": {field: {value: summarize([c for c in cases.values() if c[field] == value])
                                for value in sorted({c[field] for c in cases.values()})}
                       for field in ("family", "category", "label_source")},
            "interpretation": "Descriptive only; rates condition on decisive labeled results. Missing, failures and abstentions are not passes."}
