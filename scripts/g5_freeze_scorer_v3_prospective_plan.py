#!/usr/bin/env python3
"""Freeze prospective gates for scorer v3 before creating any validation material."""
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import PROMPT
from app.g5.evaluation_semantics import semantic_contract_sha256


TARGET = Path("research/experiments/2026-09-13-g5-scorer-v3-prospective-plan")


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    raw = {
        "schema": "g5-scorer-v3-prospective-validation-plan-v1",
        "classification": "internal-development-validation-plan",
        "status": "thresholds_frozen_materials_not_created",
        "parent_development_evidence": {
            "v11_reference_comparison_sha256": "546b1f973b5dfbd8c01341c36776095f25c65e6d6c511c1c1e7819be0ff62529",
            "v11_adjudication_audit_sha256": "eca7f32b653dc4539a7f1282637bce623700398be4f168567215d0427fc86293",
            "v11_material_status": "exposed_development_only_excluded_from_v3_qualification",
        },
        "candidate_scorer": {
            "semantic_contract_schema": "g5-evaluation-semantic-contract-v3",
            "semantic_contract_sha256": semantic_contract_sha256(),
            "catalog_prompt_sha256": digest(PROMPT),
            "model": "gpt-oss:120b",
            "temperature": 0,
            "max_tokens": 8192,
        },
        "untouched_material": {
            "families": 4, "worlds_per_family": 2, "dialogues": 8,
            "dimensions_per_dialogue": 6, "scoring_cells": 48,
            "family_relation": "new domains and obligations; no v11 names, numbers, templates, or event sequences",
            "assignment": "one dialogue per world; A/B/C/D balanced at two each",
            "generation_model": "gpt-oss:120b", "maximum_steps_per_dialogue": 16,
            "material_hashes": None,
        },
        "reference_protocol": {
            "minimum_independent_reviewers": 2,
            "reviewers_see_conditions": False, "reviewers_see_scorer_outputs": False,
            "source_identity_randomized": True,
            "reference_freezes_before_scorer_calls": True,
            "disagreement_resolution": "independent blinded adjudication before scorer outputs are revealed",
            "ai_only_reference_classification": "development_diagnostic_not_human_gold",
        },
        "acceptance_gate": {
            "all_must_hold": True,
            "final_completed_cells": 48,
            "maximum_technical_failure_after_retry": 0,
            "minimum_decisive_reference_cells": 36,
            "minimum_decisive_agreement": 0.85,
            "maximum_false_positive_rate": 0.15,
            "maximum_false_negative_rate": 0.15,
            "minimum_decisive_cells_per_dimension": 6,
            "minimum_agreement_each_dimension": 0.75,
            "maximum_scorer_abstention_rate": 0.15,
        },
        "decision_rules": {
            "pass": "freeze scorer v3 unchanged and prepare a separate authorization for the 32-dialogue screen",
            "fail": "retain all outputs, keep the 32-dialogue screen paused, revise only from development evidence, and validate the next scorer on another untouched set",
            "no_retroactive_threshold_change": True,
            "no_v11_reuse_for_qualification": True,
        },
        "authorization": {
            "local_plan_only": True, "new_dialogue_generation_authorized": False,
            "external_reference_distribution_authorized": False,
            "external_scorer_calls_authorized": False,
            "screening_32_authorized": False,
        },
        "architecture_effect_estimable": False,
        "human_accuracy_estimable": False,
        "confirmation_eligible": False,
    }
    plan = {**raw, "sha256": digest(raw)}
    TARGET.mkdir(exist_ok=False, mode=0o700)
    save(TARGET / "plan.json", plan)
    print(json.dumps({"sha256": plan["sha256"], "semantic_contract_sha256":
        plan["candidate_scorer"]["semantic_contract_sha256"], "catalog_prompt_sha256":
        plan["candidate_scorer"]["catalog_prompt_sha256"], "scoring_cells": 48,
        "external_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
