"""Pre-generation plan for fresh-family scorer validation.

This is deliberately not a factorial-effect manifest.  It samples one arm per
world to validate the blinded scoring protocol without treating condition as a
gold label or estimating architecture effects.  A later complete-block study
must use a separately frozen factorial manifest.
"""
from copy import deepcopy

from app.factorial_study import ARMS, digest
from app.g5.evaluation import PROMPT
from app.g5.evaluation_semantics import semantic_contract_sha256
from app.g5.fresh_family_frame import fresh_family_frame
from app.g5.fresh_family_roles import fresh_family_role_pack
from app.g5.measurement import require


_ASSIGNMENTS = {
    "library-space-allocation-v1": "A",
    "library-space-allocation-v2": "B",
    "research-data-release-v1": "C",
    "research-data-release-v2": "D",
    "museum-loan-conservation-v1": "B",
    "museum-loan-conservation-v2": "A",
    "community-transit-adjustment-v1": "D",
    "community-transit-adjustment-v2": "C",
}


def fresh_validation_plan():
    frame, roles = fresh_family_frame(), fresh_family_role_pack()
    role_index = {scenario: digest(cards)
                  for scenario, cards in roles["scenario_roles"].items()}
    worlds = {world["scenario_id"]: world for world in frame["worlds"]}
    assignments = [{"ordinal": ordinal, "scenario_id": scenario,
                    "family_id": worlds[scenario]["family_id"], "arm": arm,
                    "snapshot_sha256": worlds[scenario]["snapshot_sha256"],
                    "role_inputs_sha256": role_index[scenario]}
                   for ordinal, (scenario, arm) in enumerate(_ASSIGNMENTS.items(), 1)]
    raw = {
        "schema": "g5-fresh-scorer-validation-plan-v1",
        "classification": "development-validation-only",
        "purpose": "validate_dimension_scoped_scorer_on_unseen_families",
        "prohibited_inferences": ["architecture_effect", "production_readiness",
                                  "human_level_accuracy", "confirmatory_evidence"],
        "frame_sha256": frame["sha256"],
        "role_pack_sha256": roles["sha256"],
        "scenario_role_inputs_sha256": role_index,
        "role_inputs_index_sha256": digest(role_index),
        "semantic_contract_sha256": semantic_contract_sha256(),
        "scoring_prompt_sha256": digest(PROMPT),
        "assignments": assignments,
        "blinding": {"scorer_sees_arm": False, "reference_sees_arm": False,
                     "condition_is_reference_label": False},
        "reference_lanes": {
            "development": {"kind": "single_ai_expert", "permitted": True,
                            "claim_scope": "diagnostic_only"},
            "confirmatory": {"kind": "two_independent_humans_plus_adjudicator",
                             "permitted": False, "status": "not_authorized"},
        },
        "analysis": {"unit": "scenario_dimension", "dimensions_per_scenario": 6,
                     "expected_cases": 48, "pooled_score_is_primary": False,
                     "report": ["per_dimension_confusion", "decisive_agreement",
                                "abstentions", "technical_failures", "condition_guessing"],
                     "architecture_effect_estimation": False},
        "next_stage": {"kind": "complete_block_factorial_screening",
                       "expected_dialogues": 32, "requires_this_gate": True},
        "source_revision": None,
        "model_binding": None,
        "dialogues_generated": 0,
        "external_execution_authorized": False,
        "launch_authorized": False,
    }
    return {**raw, "sha256": digest(raw)}


def validate_fresh_validation_plan(value):
    require(isinstance(value, dict) and value == fresh_validation_plan(),
            "Fresh validation plan drift")
    require(len(value["assignments"]) == 8, "Eight validation dialogues required")
    counts = {arm: 0 for arm in ARMS}
    for row in value["assignments"]:
        counts[row["arm"]] += 1
        require(row["role_inputs_sha256"] ==
                value["scenario_role_inputs_sha256"][row["scenario_id"]],
                "Assignment role hash mismatch")
    require(set(counts.values()) == {2}, "Validation arms must be balanced")
    require(value["analysis"]["expected_cases"] == 48 and
            not value["analysis"]["architecture_effect_estimation"],
            "Scorer validation cannot estimate architecture effects")
    require(value["source_revision"] is None and value["model_binding"] is None and
            not value["external_execution_authorized"] and not value["launch_authorized"],
            "Pre-generation plan cannot imply execution authority")
    return deepcopy(value)
