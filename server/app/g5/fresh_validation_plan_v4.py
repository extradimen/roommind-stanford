"""Pre-generation assignment plan for untouched scorer-v4 validation."""
from copy import deepcopy

from app.factorial_study import ARMS, digest
from app.g5.calibration_evidence_catalog import PROMPT
from app.g5.evaluation_semantics import semantic_contract_sha256
from app.g5.fresh_family_frame_v4 import fresh_family_frame_v4
from app.g5.fresh_family_roles_v4 import fresh_family_role_pack_v4
from app.g5.measurement import require


PROSPECTIVE_GATE_SHA = "7967fac8a92743fe17e457a54fa6d5d20f266032d24c6e9d3a344959959370f0"
_ASSIGNMENTS = {
    "orchard-frost-response-v1": "B", "orchard-frost-response-v2": "D",
    "archive-collection-transfer-v1": "A", "archive-collection-transfer-v2": "C",
    "satellite-ground-pass-v1": "D", "satellite-ground-pass-v2": "B",
    "school-meal-allergen-recall-v1": "C", "school-meal-allergen-recall-v2": "A",
}


def fresh_validation_plan_v4():
    frame, roles = fresh_family_frame_v4(), fresh_family_role_pack_v4()
    role_index = {scenario: digest(cards) for scenario, cards in roles["scenario_roles"].items()}
    worlds = {world["scenario_id"]: world for world in frame["worlds"]}
    assignments = [{"ordinal": ordinal, "scenario_id": scenario,
                    "family_id": worlds[scenario]["family_id"], "arm": arm,
                    "snapshot_sha256": worlds[scenario]["snapshot_sha256"],
                    "role_inputs_sha256": role_index[scenario]}
                   for ordinal, (scenario, arm) in enumerate(_ASSIGNMENTS.items(), 1)]
    raw = {"schema": "g5-fresh-scorer-validation-plan-v4",
        "classification": "development-validation-only",
        "purpose": "prospective_validation_of_scorer_v4_on_untouched_families",
        "prospective_gate_sha256": PROSPECTIVE_GATE_SHA,
        "prohibited_inferences": ["architecture_effect", "production_readiness",
                                  "human_level_accuracy", "confirmatory_evidence"],
        "frame_sha256": frame["sha256"], "role_pack_sha256": roles["sha256"],
        "scenario_role_inputs_sha256": role_index, "role_inputs_index_sha256": digest(role_index),
        "semantic_contract_sha256": semantic_contract_sha256(),
        "scoring_prompt_sha256": digest(PROMPT), "assignments": assignments,
        "blinding": {"scorer_sees_arm": False, "reference_sees_arm": False,
                     "condition_is_reference_label": False},
        "reference_lanes": {"minimum_independent_reviewers": 2,
            "adjudication_before_scorer_outputs": True,
            "ai_only_claim_scope": "development_diagnostic_only"},
        "analysis": {"unit": "scenario_dimension", "dimensions_per_scenario": 6,
            "expected_cases": 48, "pooled_score_is_primary": False,
            "architecture_effect_estimation": False},
        "source_revision": None, "model_binding": None, "dialogues_generated": 0,
        "external_execution_authorized": False, "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_validation_plan_v4(value):
    require(value == fresh_validation_plan_v4(), "Fresh validation plan v4 drift")
    require(len(value["assignments"]) == 8, "Eight validation dialogues required")
    counts = {arm: 0 for arm in ARMS}
    for row in value["assignments"]:
        counts[row["arm"]] += 1
        require(row["role_inputs_sha256"] == value["scenario_role_inputs_sha256"][row["scenario_id"]],
                "Assignment role hash mismatch")
    require(set(counts.values()) == {2}, "Validation arms must be balanced")
    require(value["analysis"]["expected_cases"] == 48
            and not value["analysis"]["architecture_effect_estimation"],
            "Scorer validation cannot estimate architecture effects")
    require(value["source_revision"] is None and value["model_binding"] is None
            and not value["external_execution_authorized"] and not value["launch_authorized"],
            "Pre-generation plan cannot imply execution authority")
    return deepcopy(value)
