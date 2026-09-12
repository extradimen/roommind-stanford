"""Offline evidence-bound six-dimension accounting and family-paired contrasts.

No model execution, production imports, composite realism score, or automatic
qualification. Bootstrap intervals are approximate, conditional on a frozen
plan and exchangeable sampled families; synthetic data never confirm efficacy.
"""
from copy import deepcopy
import math
import random
from statistics import mean

from app.factorial_study import digest, verify_manifest

DIMENSIONS = ("role_strategic_fidelity", "epistemic_fidelity", "temporal_coherence",
              "interaction_structure_fidelity", "multi_party_dynamics_fidelity", "procedural_fidelity")
WEIGHTS = {"C": {"A": -.5, "B": .5, "C": -.5, "D": .5},
           "G": {"A": -.5, "B": -.5, "C": .5, "D": .5},
           "interaction": {"A": 1., "B": -1., "C": -1., "D": 1.}}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def freeze_analysis(config, *, version=1, sampling_target=None):
    require(type(version) is int and version in (1, 2, 3), "Unknown analysis schema version")
    if version == 3:
        require(isinstance(sampling_target, dict) and set(sampling_target) == {"kind", "frame_sha256"}
            and sampling_target["kind"] in ("fixed-family-benchmark", "independent-family-population")
            and sha(sampling_target["frame_sha256"]), "Explicit sampling target required")
    else:
        require(sampling_target is None, "Sampling target requires a new v3 plan")
    require(isinstance(config, dict) and set(config) - {"interval_method", "evaluation_controls"} == {"alpha", "resamples", "seed", "minimum_families",
        "meaningful_differences", "judge", "rubric_sha256", "sample_size_plan_sha256"}, "Invalid analysis config")
    if "evaluation_controls" in config:
        from app.g5.evaluation_controls import validate
        validate(config["evaluation_controls"])
    require(type(config["alpha"]) in (float, int) and 0 < config["alpha"] < .5, "Invalid alpha")
    require(type(config["resamples"]) is int and config["resamples"] >= 1000, "Insufficient bootstrap resamples")
    require(config["resamples"] * config["alpha"] / 36 >= 20, "Too few draws in adjusted interval tails")
    require(type(config["seed"]) is int, "Explicit analysis seed required")
    require(type(config["minimum_families"]) is int and config["minimum_families"] >= 10, "At least ten families for interval gate")
    require(isinstance(config["meaningful_differences"], dict) and set(config["meaningful_differences"]) == set(DIMENSIONS), "Six separate practical thresholds required")
    require(all(type(x) in (int, float) and math.isfinite(x) and 0 < x <= 4
                for x in config["meaningful_differences"].values()), "Invalid practical threshold")
    judge = config["judge"]
    require(isinstance(judge, dict) and set(judge) == {"id", "kind", "spec_sha256"}, "Explicit judge provenance required")
    require(isinstance(judge["id"], str) and judge["id"].strip()
        and judge["kind"] in {"synthetic", "assistant", "ai", "human"} and sha(judge["spec_sha256"]), "Invalid judge")
    require(sha(config["rubric_sha256"]) and sha(config["sample_size_plan_sha256"]), "Frozen rubric and sample plan required")
    require(config.get("interval_method", "family-percentile-bootstrap-v1") in {
        "family-percentile-bootstrap-v1", "bounded-family-hoeffding-v1"}, "Unknown frozen interval method")
    raw = {"schema": "g5-six-dimension-family-analysis-v1", "config": deepcopy(config),
        "dimensions": list(DIMENSIONS), "score_range": [1, 5], "estimands": deepcopy(WEIGHTS),
        "unit": "equal-family_then_equal-paired-block", "multiplicity": "bonferroni-18",
        "missing": "retain-all-assignments_bounds-no-imputation", "interval": "family-percentile-bootstrap"}
    if version in (2, 3):
        method = config.get("interval_method", "family-percentile-bootstrap-v1")
        raw.update(schema="g5-six-dimension-family-analysis-v2", interval=method,
            resamples_role="used" if method == "family-percentile-bootstrap-v1" else "unused-retained-config-field")
    if version == 3:
        raw.update(schema="g5-six-dimension-family-analysis-v3", sampling_target=deepcopy(sampling_target))
        if sampling_target["kind"] == "fixed-family-benchmark":
            raw.update(interval="none-fixed-benchmark-descriptive", resamples_role="unused-retained-config-field")
    return {**raw, "sha256": digest(raw)}


def verify_analysis(plan):
    require(isinstance(plan, dict) and plan.get("schema") in {
        "g5-six-dimension-family-analysis-v1", "g5-six-dimension-family-analysis-v2",
        "g5-six-dimension-family-analysis-v3"}, "Unknown analysis schema")
    version = int(plan["schema"][-1])
    require(freeze_analysis(plan["config"], version=version, sampling_target=plan.get("sampling_target")) == plan, "Analysis plan drift")


def freeze_transcript(manifest, ordinal, turns):
    verify_manifest(manifest)
    require(type(ordinal) is int and 1 <= ordinal <= manifest["expected_dialogues"], "Unknown assignment")
    require(isinstance(turns, list), "Transcript turns required")
    seen = set()
    for row in turns:
        require(isinstance(row, dict) and set(row) == {"id", "actor", "text"}, "Public transcript fields only")
        require(all(isinstance(v, str) and v for v in row.values()) and row["id"] not in seen, "Invalid public turn")
        seen.add(row["id"])
    raw = {"manifest_sha256": manifest["manifest_sha256"], "ordinal": ordinal, "turns": deepcopy(turns)}
    return {**raw, "sha256": digest(raw)}


def validate_quotes(quotes, transcript):
    require(isinstance(quotes, list) and quotes, "Evidence quotes required")
    turns = {t["id"]: t for t in transcript["turns"]}
    for quote in quotes:
        require(isinstance(quote, dict) and set(quote) == {"turn_id", "start", "end", "text"}, "Invalid quote fields")
        require(isinstance(quote["turn_id"], str) and quote["turn_id"] in turns, "Unknown quoted turn")
        text = turns[quote["turn_id"]]["text"]
        require(type(quote["start"]) is int and type(quote["end"]) is int
            and 0 <= quote["start"] < quote["end"] <= len(text)
            and text[quote["start"]:quote["end"]] == quote["text"], "Quote does not match frozen transcript")


def freeze_labels(manifest, rows):
    """Archive reference labels with exact evidence; provenance is not proof of a human."""
    require(isinstance(rows, list) and rows, "Reference labels required")
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"id", "family", "category", "transcript", "label",
            "label_source", "annotator_id", "annotation_artifact_sha256", "quotes", "rationale"}, "Invalid reference label")
        require(all(isinstance(row[k], str) and row[k].strip() for k in ("id", "family", "category", "annotator_id", "rationale")),
                "Reference identity and explanation required")
        require(row["id"] not in seen, "Duplicate reference identity")
        seen.add(row["id"])
        require(row["label"] in ("violation", "clear", "uncertain", "not_applicable")
            and row["label_source"] in ("synthetic", "assistant", "human")
            and sha(row["annotation_artifact_sha256"]), "Reference provenance required")
        tx = row["transcript"]
        require(isinstance(tx, dict) and freeze_transcript(manifest, tx["ordinal"], tx["turns"]) == tx,
                "Reference transcript changed")
        require(manifest["assignments"][tx["ordinal"] - 1]["family"] == row["family"], "Reference family mismatch")
        validate_quotes(row["quotes"], tx)
    raw = {"schema": "g5-evidence-calibration-set-v1", "manifest_sha256": manifest["manifest_sha256"], "labels": deepcopy(rows)}
    return {**raw, "sha256": digest(raw)}


def index_scores(manifest, plan, transcripts, attempts):
    verify_analysis(plan)
    verify_manifest(manifest)
    require(manifest["design"]["analysis_plan_sha256"] == plan["sha256"]
        and manifest["design"]["sample_size_plan_sha256"] == plan["config"]["sample_size_plan_sha256"], "Unbound analysis/sample plan")
    require(all(a["shared"]["evaluator_plan_sha256"] == plan["sha256"]
                for a in manifest["design"]["arms"].values()), "Unbound common evaluator")
    require(isinstance(transcripts, list) and isinstance(attempts, list), "Artifact lists required")
    tx = {}
    for transcript in transcripts:
        require(isinstance(transcript, dict) and set(transcript) == {"manifest_sha256", "ordinal", "turns", "sha256"}, "Invalid transcript")
        ordinal = transcript["ordinal"]
        require(type(ordinal) is int and ordinal not in tx and freeze_transcript(manifest, ordinal, transcript["turns"]) == transcript,
                "Changed or duplicated transcript")
        tx[ordinal] = transcript
    indexed, seen = {}, set()
    for row in attempts:
        require(isinstance(row, dict) and set(row) == {"id", "ordinal", "dimension", "judge", "transcript_sha256",
            "status", "score", "quotes", "rationale", "artifact_sha256"}, "Invalid score attempt")
        require(isinstance(row["id"], str) and row["id"] and row["id"] not in seen, "Duplicate attempt identity")
        seen.add(row["id"])
        require(type(row["ordinal"]) is int and 1 <= row["ordinal"] <= manifest["expected_dialogues"]
            and row["dimension"] in DIMENSIONS and row["judge"] == plan["config"]["judge"], "Assignment/dimension/judge mismatch")
        require(sha(row["artifact_sha256"]), "Source evaluation artifact hash required")
        transcript = tx.get(row["ordinal"])
        require(row["transcript_sha256"] == (transcript["sha256"] if transcript else None), "Score transcript mismatch")
        require(row["status"] in {"completed", "technical_failure", "not_applicable"}, "Invalid evaluation outcome")
        require(isinstance(row["rationale"], str) and row["rationale"].strip(), "Explicit rationale required")
        if row["status"] == "completed":
            require(transcript is not None and type(row["score"]) in (int, float)
                and math.isfinite(row["score"]) and 1 <= row["score"] <= 5, "Invalid score")
            validate_quotes(row["quotes"], transcript)
        else:
            require(row["score"] is None and row["quotes"] == [], "Non-score outcomes are not numeric passes")
        key = (row["ordinal"], row["dimension"])
        require(key not in indexed or indexed[key]["status"] == "technical_failure", "Never overwrite a completed or not-applicable dimension")
        indexed[key] = deepcopy(row)
    return tx, indexed


def bounded_family_interval(family_values, alpha, estimand):
    """Conservative simultaneous-18 bound for independent bounded family scores.

For family contrast range length R, Hoeffding gives 2 exp(-2 n e^2/R^2).
Set this to alpha/18. No normality or observed-variance assumption; independence
and a valid family sampling target are still required. Not a power guarantee.
"""
    require(estimand in WEIGHTS and 0 < alpha < .5 and bool(family_values), "Invalid bounded interval inputs")
    bound = 4 if estimand in {"C", "G"} else 8
    require(all(type(v) in (int, float) and math.isfinite(v) and -bound <= v <= bound for v in family_values),
            "Family contrast outside bounded score range")
    radius = 2 * bound * math.sqrt(math.log(36 / alpha) / (2 * len(family_values)))
    point = mean(family_values)
    return [max(-bound, point - radius), min(bound, point + radius)]


def family_bootstrap_interval(family_values, config, dimension, estimand):
    """Shared approximate algorithm, also exercised by offline coverage diagnostics."""
    require(len(family_values) >= config["minimum_families"], "Insufficient independent families")
    require(dimension in DIMENSIONS and estimand in WEIGHTS, "Unknown contrast")
    require(all(type(v) in (int, float) and math.isfinite(v) for v in family_values), "Invalid family effects")
    require(type(config["resamples"]) is int and config["resamples"] * config["alpha"] / 36 >= 20,
            "Insufficient adjusted-tail resolution")
    rng = random.Random(digest([config["seed"], dimension, estimand]))
    samples = sorted(mean(rng.choices(family_values, k=len(family_values))) for _ in range(config["resamples"]))
    tail = config["alpha"] / (2 * len(DIMENSIONS) * len(WEIGHTS))
    return [samples[int(tail * (len(samples) - 1))], samples[math.ceil((1 - tail) * (len(samples) - 1))]]


def report(manifest, plan, transcripts, attempts):
    tx, scores = index_scores(manifest, plan, transcripts, attempts)
    config = plan["config"]
    assignments = manifest["assignments"]
    blocks = {}
    for a in assignments:
        blocks.setdefault((a["family"], a["block_id"]), {})[a["arm"]] = a["ordinal"]
    output = {}
    for dimension in DIMENSIONS:
        counts = {s: 0 for s in ("completed", "technical_failure", "not_applicable", "missing")}
        for a in assignments:
            counts[scores.get((a["ordinal"], dimension), {}).get("status", "missing")] += 1
        estimates = {}
        for estimand, weights in WEIGHTS.items():
            families = {}
            complete_blocks = 0
            for (family, block), arms in blocks.items():
                values = {arm: scores.get((ordinal, dimension), {}).get("score") for arm, ordinal in arms.items()}
                complete = all(v is not None for v in values.values())
                complete_blocks += int(complete)
                lo = sum(w * (values[arm] if values[arm] is not None else (1 if w > 0 else 5)) for arm, w in weights.items())
                hi = sum(w * (values[arm] if values[arm] is not None else (5 if w > 0 else 1)) for arm, w in weights.items())
                families.setdefault(family, []).append((lo, hi, complete))
            lower = mean(mean(r[0] for r in rows) for rows in families.values())
            upper = mean(mean(r[1] for r in rows) for rows in families.values())
            bounds = [lower, upper] if counts["not_applicable"] == 0 else None
            all_complete = complete_blocks == len(blocks)
            point = lower if all_complete else None
            interval, reason = None, "incomplete-assigned-blocks"
            if counts["not_applicable"]:
                reason = "not-applicable-estimand-undefined"
            if all_complete:
                reason = "too-few-independent-families"
                if plan.get("sampling_target", {}).get("kind") == "fixed-family-benchmark":
                    reason = "fixed-benchmark-descriptive-no-population-interval"
                elif len(families) >= config["minimum_families"]:
                    family_values = [mean(r[0] for r in families[f]) for f in sorted(families)]
                    if config.get("interval_method") == "bounded-family-hoeffding-v1":
                        interval = bounded_family_interval(family_values, config["alpha"], estimand)
                        reason = "bounded-independent-family-hoeffding-bonferroni-18"
                    else:
                        interval = family_bootstrap_interval(family_values, config, dimension, estimand)
                        reason = "approximate-family-bootstrap-bonferroni-18"
            estimates[estimand] = {"estimate": point, "missing_score_bounds": bounds,
                "interval": interval, "interval_status": reason, "complete_blocks": complete_blocks,
                "assigned_blocks": len(blocks), "families": len(families),
                "meaningful_difference": config["meaningful_differences"][dimension]}
        output[dimension] = {"denominators": counts, "contrasts": estimates}
    result = {"schema": "g5-six-dimension-report-v1", "manifest_sha256": manifest["manifest_sha256"],
        "plan_sha256": plan["sha256"], "transcripts_sha256": digest(transcripts), "attempts_sha256": digest(attempts),
        "judge": deepcopy(config["judge"]), "evidence_use": manifest["evidence_use"],
        "assigned_dialogues": len(assignments), "available_transcripts": len(tx),
        "attempt_count": len(attempts), "technical_failure_attempts": sum(r["status"] == "technical_failure" for r in attempts),
        "dimensions": output, "qualification": "not_inferred",
        "limitations": "No composite score. Bounds are not confidence intervals. Missing/N-A scores retain the assignment denominator. Judge provenance is declared, not authenticated. Synthetic/assistant data do not establish real-model or human-calibrated efficacy."}
    if plan["schema"] in ("g5-six-dimension-family-analysis-v2", "g5-six-dimension-family-analysis-v3"):
        result.update(schema=plan["schema"].replace("family-analysis", "report"), interval_method=plan["interval"],
                      resamples_role=plan["resamples_role"])
    if "sampling_target" in plan:
        result.update(sampling_target=deepcopy(plan["sampling_target"]),
            sampling_assumptions_verified=False,
            target_interpretation="Fixed benchmark estimates describe the observed equal-family/equal-block scores only; no uncertainty for future runs is inferred. Population intervals require independent families and a justified sampling frame; declarations do not establish either.")
    return result
