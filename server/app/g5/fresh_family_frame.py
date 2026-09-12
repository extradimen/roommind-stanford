"""New-family validation worlds, frozen before any dialogue generation."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.measurement import require
from app.g5.world import validate_spec


def _fact(value):
    return {"value": value, "visible_to": None, "disclosable": True}


def _action(actor, requires, effects):
    return {"actors": [actor], "requires": requires, "effects": effects,
            "outcome": "success", "visible_to": None}


def _world(family, variant, roles, facts, actions):
    spec = {"roles": roles, "facts": {key: _fact(value) for key, value in facts.items()},
            "actions": actions}
    validate_spec(spec)
    return {"scenario_id": f"{family}-v{variant}", "family_id": family,
            "variant": variant, "world": spec, "snapshot_sha256": digest(spec)}


def fresh_family_frame():
    worlds = []
    for variant, capacity, demand in ((1, 120, 145), (2, 96, 118)):
        roles = ["library_director", "accessibility_advisor", "youth_program_lead", "archivist"]
        facts = {"room_capacity": capacity, "youth_demand": demand, "access_review": False,
                 "preservation_review": False, "allocation_approved": False}
        actions = {"complete_access_review": _action("accessibility_advisor", {}, {"access_review": True}),
            "complete_preservation_review": _action("archivist", {}, {"preservation_review": True}),
            "approve_allocation": _action("library_director",
                {"access_review": True, "preservation_review": True}, {"allocation_approved": True})}
        worlds.append(_world("library-space-allocation", variant, roles, facts, actions))
    for variant, records, threshold in ((1, 840, 0.95), (2, 1260, 0.98)):
        roles = ["principal_investigator", "privacy_officer", "reproducibility_reviewer", "partner_representative"]
        facts = {"record_count": records, "reproduction_threshold": threshold, "privacy_review": False,
                 "reproducibility_review": False, "release_authorized": False}
        actions = {"complete_privacy_review": _action("privacy_officer", {}, {"privacy_review": True}),
            "complete_reproducibility_review": _action("reproducibility_reviewer", {}, {"reproducibility_review": True}),
            "authorize_release": _action("principal_investigator",
                {"privacy_review": True, "reproducibility_review": True}, {"release_authorized": True})}
        worlds.append(_world("research-data-release", variant, roles, facts, actions))
    for variant, insured, humidity in ((1, 2_400_000, 48), (2, 1_750_000, 52)):
        roles = ["museum_curator", "conservation_scientist", "insurance_representative", "lender_coordinator"]
        facts = {"insured_value": insured, "target_humidity": humidity, "condition_report": False,
                 "insurance_bound": False, "loan_approved": False}
        actions = {"complete_condition_report": _action("conservation_scientist", {}, {"condition_report": True}),
            "bind_insurance": _action("insurance_representative", {}, {"insurance_bound": True}),
            "approve_loan": _action("museum_curator",
                {"condition_report": True, "insurance_bound": True}, {"loan_approved": True})}
        worlds.append(_world("museum-loan-conservation", variant, roles, facts, actions))
    for variant, riders, budget in ((1, 3800, 420000), (2, 5100, 510000)):
        roles = ["transit_scheduler", "rider_advocate", "driver_representative", "budget_analyst"]
        facts = {"affected_riders": riders, "annual_budget": budget, "driver_feasibility": False,
                 "equity_review": False, "schedule_approved": False}
        actions = {"confirm_driver_feasibility": _action("driver_representative", {}, {"driver_feasibility": True}),
            "complete_equity_review": _action("rider_advocate", {}, {"equity_review": True}),
            "approve_schedule": _action("transit_scheduler",
                {"driver_feasibility": True, "equity_review": True}, {"schedule_approved": True})}
        worlds.append(_world("community-transit-adjustment", variant, roles, facts, actions))
    raw = {"schema": "g5-fresh-family-frame-v1", "classification": "internal-pre-generation",
        "families": sorted({world["family_id"] for world in worlds}), "worlds": worlds,
        "legacy_family_reuse": False, "dialogues_generated": 0, "reference_labels_collected": 0,
        "external_execution_authorized": False, "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_frame(value):
    require(isinstance(value, dict) and value == fresh_family_frame(), "Fresh family frame drift")
    require(len(value["families"]) == 4 and len(value["worlds"]) == 8, "Fresh family coverage changed")
    require(len({world["snapshot_sha256"] for world in value["worlds"]}) == 8,
            "Fresh worlds must have distinct snapshots")
    for world in value["worlds"]:
        validate_spec(world["world"])
        require(world["snapshot_sha256"] == digest(world["world"]), "Fresh world hash mismatch")
    return deepcopy(value)
