"""Offline, evidence-bound study preflight. Never executes or authorizes a study.

Scientific adequacy and independently verified provenance remain review gates;
hashes establish consistency, not truth. Legacy manifests are not rewritten.
"""
from copy import deepcopy
import math

from app.factorial_study import digest, verify_manifest
from app.g5.family_registry import verify_export, holdout_audit
from app.g5.measurement import DIMENSIONS, require, sha, verify_analysis
from app.g5.calibration_bounds import report as calibration_report


def freeze_contract(manifest, analysis, registry, sample_plan, calibration_requirements):
    verify_manifest(manifest); verify_analysis(analysis); verify_export(registry)
    require(isinstance(sample_plan, dict) and set(sample_plan) == {
        "family_count", "repetitions", "sampling_frame", "rationale", "scope"}, "Complete sample-plan specification required")
    require(type(sample_plan["family_count"]) is int and sample_plan["family_count"] > 0
        and type(sample_plan["repetitions"]) is int and sample_plan["repetitions"] > 0
        and all(isinstance(sample_plan[k], str) and sample_plan[k].strip() for k in ("sampling_frame", "rationale"))
        and sample_plan["scope"] in ("synthetic_control", "research_candidate"), "Invalid sample-plan specification")
    c = calibration_requirements
    require(isinstance(c, dict) and set(c) == {"annotation_plan_sha256", "prediction_plan_sha256",
        "minimum_references_per_label_per_dimension", "minimum_decisive_coverage", "maximum_binary_error_bound"},
        "Explicit calibration criteria required")
    require(sha(c["annotation_plan_sha256"]) and sha(c["prediction_plan_sha256"])
        and type(c["minimum_references_per_label_per_dimension"]) is int
        and c["minimum_references_per_label_per_dimension"] > 0, "Invalid calibration binding or denominator")
    require(all(type(c[k]) in (int, float) and math.isfinite(c[k]) and 0 <= c[k] <= 1
        for k in ("minimum_decisive_coverage", "maximum_binary_error_bound")), "Invalid calibration thresholds")
    require(manifest["design"]["analysis_plan_sha256"] == analysis["sha256"]
        and all(a["shared"]["evaluator_plan_sha256"] == analysis["sha256"] for a in manifest["design"]["arms"].values()),
        "Analysis not bound to every arm")
    require(manifest["design"]["sample_size_plan_sha256"] == digest(sample_plan)
        == analysis["config"]["sample_size_plan_sha256"], "Sample-plan binding differs")
    raw = {"schema": "g5-study-preflight-contract-v1", "manifest": deepcopy(manifest), "analysis": deepcopy(analysis),
        "registry_sha256": registry["sha256"], "sample_plan": deepcopy(sample_plan),
        "calibration_requirements": deepcopy(c)}
    return {**raw, "sha256": digest(raw)}


def inspect(contract, frozen_registry, current_registry, *, annotation=None, results=None):
    require(freeze_contract(contract["manifest"], contract["analysis"], frozen_registry,
        contract["sample_plan"], contract["calibration_requirements"]) == contract, "Preflight contract changed")
    state = verify_export(current_registry)
    design, sample = contract["manifest"]["design"], contract["sample_plan"]
    families = sorted({s["family"] for s in design["scenarios"]})
    checks = {}
    checks["registry_snapshot_current"] = current_registry["sha256"] == contract["registry_sha256"]
    checks["scenario_materials_registered"] = all(any(m["family_id"] == s["family"]
        and m["snapshot_sha256"] == s["snapshot_sha256"] for m in state["materials"]) for s in design["scenarios"])
    known = all(f in state["families"] for f in families)
    groups = {tuple(state["groups"][f]) for f in families} if known else set()
    checks["independent_declared_family_units"] = known and len(groups) == len(families)
    checks["sample_counts_match"] = len(families) == sample["family_count"] and design["repetitions"] == sample["repetitions"]
    target = contract["analysis"].get("sampling_target")
    fixed = target is not None and target["kind"] == "fixed-family-benchmark"
    checks["analysis_family_floor"] = fixed or len(groups) >= contract["analysis"]["config"]["minimum_families"]
    if target is not None:
        checks["sampling_frame_bound"] = target["frame_sha256"] == digest(sample["sampling_frame"])
    held_out = design["stage"] in ("screening", "confirmation")
    selected_linked = set().union(*groups) if groups else set()
    checks["declared_used_lineage_disjoint"] = not held_out or not (selected_linked & set(design["used_families"]))
    audit = holdout_audit(current_registry, families) if known else None
    checks["registered_holdout_unexposed"] = not held_out or (audit is not None and audit["registered_exposure_free"])
    summary = None
    checks["calibration_present"] = annotation is not None and results is not None
    if checks["calibration_present"]:
        summary = calibration_report(annotation, results)  # Revalidate full labels, sources and attempts, not a supplied score.
        requirements = contract["calibration_requirements"]
        checks["calibration_plan_bound"] = annotation["plan"]["sha256"] == requirements["annotation_plan_sha256"]
        checks["predictor_plan_bound"] = results["prediction_plan"]["sha256"] == requirements["prediction_plan_sha256"]
        checks["calibration_complete_reference_and_prediction"] = all(c["reference_label"] in ("clear", "violation", "not_applicable")
            and c["prediction_status"] == "completed" for c in summary["cases"])
        for dimension in DIMENSIONS:
            row = summary["strata"]["dimension"].get(dimension, {})
            for label in ("clear", "violation"):
                bound = row.get("reference_strata", {}).get(label, {})
                checks[f"calibration:{dimension}:{label}"] = (
                    bound.get("reference_total", 0) >= requirements["minimum_references_per_label_per_dimension"]
                    and bound.get("decisive_coverage") is not None
                    and bound["decisive_coverage"] >= requirements["minimum_decisive_coverage"]
                    and bound.get("possible_binary_error_fraction_bounds") is not None
                    and bound["possible_binary_error_fraction_bounds"][1] <= requirements["maximum_binary_error_bound"])
        calibration_scenarios = annotation["manifest"]["design"]["scenarios"]
        checks["calibration_materials_registered"] = all(any(m["family_id"] == s["family"]
            and m["snapshot_sha256"] == s["snapshot_sha256"] for m in state["materials"]) for s in calibration_scenarios)
        calibration_families = {s["family"] for s in calibration_scenarios}
        # Direct use in supplied calibration is exposure even if no explicit exposure event was recorded.
        checks["calibration_holdout_disjoint"] = not held_out or not (selected_linked & calibration_families)
    raw = {"schema": "g5-study-preflight-report-v1", "contract_sha256": contract["sha256"],
        "current_registry_sha256": current_registry["sha256"], "checks": checks,
        "blocking_checks": sorted(k for k,v in checks.items() if not v),
        "local_contract_checks_passed": all(checks.values()), "holdout_audit": audit,
        "calibration_report_sha256": summary["sha256"] if summary else None,
        "unverified_research_gates": ["historical_exposure_completeness", "semantic_family_novelty",
            "human_identity_and_reference_quality", "sampling_and_precision_adequacy", "calibration_threshold_adequacy",
            "scoring_judge_validation", "runtime_and_deployment_review", "explicit_external_authorization"],
        "launch_authorized": False, "qualification": "not_inferred"}
    return {**raw, "sha256": digest(raw)}


def require_local_contract(contract, frozen_registry, current_registry, **evidence):
    """Pure preflight boundary; passing is NOT permission to run a model or deploy."""
    report = inspect(contract, frozen_registry, current_registry, **evidence)
    require(report["local_contract_checks_passed"], "Study preflight blocked: " + ", ".join(report["blocking_checks"]))
    return report
