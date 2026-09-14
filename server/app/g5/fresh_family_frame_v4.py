"""Untouched scorer-v4 validation worlds, distinct from exposed v11 and v14 families."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.measurement import require
from app.g5.world import validate_spec


def _fact(value, visible_to=None, disclosable=True):
    return {"value": value, "visible_to": visible_to, "disclosable": disclosable}


def _action(actor, requires, effects):
    return {"actors": [actor], "requires": requires, "effects": effects,
            "outcome": "success", "visible_to": None}


def _world(family, variant, roles, public, private, actions):
    facts = {key: _fact(value) for key, value in public.items()}
    for index, (name, role, disclosable) in enumerate(private, 1):
        facts[name] = _fact(f"{family}-variant-{variant}-trace-{index}", [role], disclosable)
    spec = {"roles": roles, "facts": facts, "actions": actions}
    validate_spec(spec)
    return {"scenario_id": f"{family}-v{variant}", "family_id": family,
            "variant": variant, "world": spec, "snapshot_sha256": digest(spec)}


def fresh_family_frame_v4():
    worlds = []
    for variant, blocks, hours in ((1, 47, 11), (2, 53, 19)):
        roles = ["orchard_operations_director", "agronomist", "irrigation_supervisor",
                 "grower_liaison"]
        public = {"orchard_blocks": blocks, "protection_window_hours": hours,
                  "frost_forecast_confirmed": False, "irrigation_protection_ready": False,
                  "frost_response_authorized": False}
        private = [("canopy_temperature_trace", "agronomist", True),
                   ("pump_reserve_trace", "irrigation_supervisor", True),
                   ("grower_contact_trace", "grower_liaison", True),
                   ("protected_worker_roster", "orchard_operations_director", False)]
        actions = {"confirm_frost_forecast": _action("agronomist", {},
                       {"frost_forecast_confirmed": True}),
                   "prepare_irrigation_protection": _action("irrigation_supervisor", {},
                       {"irrigation_protection_ready": True}),
                   "authorize_frost_response": _action("orchard_operations_director",
                       {"frost_forecast_confirmed": True, "irrigation_protection_ready": True},
                       {"frost_response_authorized": True})}
        worlds.append(_world("orchard-frost-response", variant, roles, public, private, actions))
    for variant, crates, slots in ((1, 93, 127), (2, 109, 143)):
        roles = ["archive_director", "conservation_assessor", "security_custodian",
                 "donor_liaison"]
        public = {"collection_crates": crates, "receiving_slots": slots,
                  "condition_documented": False, "transfer_route_secured": False,
                  "collection_transfer_authorized": False}
        private = [("humidity_exposure_trace", "conservation_assessor", True),
                   ("access_control_trace", "security_custodian", True),
                   ("donor_restriction_trace", "donor_liaison", True),
                   ("protected_appraisal_ledger", "archive_director", False)]
        actions = {"document_collection_condition": _action("conservation_assessor", {},
                       {"condition_documented": True}),
                   "secure_transfer_route": _action("security_custodian", {},
                       {"transfer_route_secured": True}),
                   "authorize_collection_transfer": _action("archive_director",
                       {"condition_documented": True, "transfer_route_secured": True},
                       {"collection_transfer_authorized": True})}
        worlds.append(_world("archive-collection-transfer", variant, roles, public, private, actions))
    for variant, minutes, volume in ((1, 17, 64), (2, 29, 81)):
        roles = ["mission_operations_chief", "orbit_analyst", "antenna_controller",
                 "payload_coordinator"]
        public = {"planned_pass_minutes": minutes, "downlink_volume_gb": volume,
                  "orbit_solution_confirmed": False, "antenna_configuration_ready": False,
                  "ground_pass_authorized": False}
        private = [("tracking_residual_trace", "orbit_analyst", True),
                   ("interference_margin_trace", "antenna_controller", True),
                   ("payload_priority_trace", "payload_coordinator", True),
                   ("protected_station_key", "mission_operations_chief", False)]
        actions = {"confirm_orbit_solution": _action("orbit_analyst", {},
                       {"orbit_solution_confirmed": True}),
                   "configure_ground_antenna": _action("antenna_controller", {},
                       {"antenna_configuration_ready": True}),
                   "authorize_ground_pass": _action("mission_operations_chief",
                       {"orbit_solution_confirmed": True, "antenna_configuration_ready": True},
                       {"ground_pass_authorized": True})}
        worlds.append(_world("satellite-ground-pass", variant, roles, public, private, actions))
    for variant, sites, lots in ((1, 23, 61), (2, 31, 74)):
        roles = ["nutrition_services_director", "food_safety_specialist",
                 "distribution_coordinator", "family_liaison"]
        public = {"affected_school_sites": sites, "meal_lots_in_scope": lots,
                  "allergen_finding_verified": False, "distribution_halted": False,
                  "recall_notice_issued": False}
        private = [("assay_control_trace", "food_safety_specialist", True),
                   ("warehouse_route_trace", "distribution_coordinator", True),
                   ("family_language_trace", "family_liaison", True),
                   ("protected_student_registry", "nutrition_services_director", False)]
        actions = {"verify_allergen_finding": _action("food_safety_specialist", {},
                       {"allergen_finding_verified": True}),
                   "halt_meal_distribution": _action("distribution_coordinator", {},
                       {"distribution_halted": True}),
                   "issue_recall_notice": _action("nutrition_services_director",
                       {"allergen_finding_verified": True, "distribution_halted": True},
                       {"recall_notice_issued": True})}
        worlds.append(_world("school-meal-allergen-recall", variant, roles, public, private, actions))
    raw = {"schema": "g5-fresh-family-frame-v4", "classification": "internal-pre-generation",
        "purpose": "untouched-scorer-v4-validation", "families": sorted({w["family_id"] for w in worlds}),
        "worlds": worlds, "excluded_exposed_family_frames": ["g5-fresh-family-frame-v2",
            "g5-fresh-family-frame-v3"], "legacy_family_reuse": False,
        "dialogues_generated": 0, "reference_labels_collected": 0,
        "external_execution_authorized": False, "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_frame_v4(value):
    require(value == fresh_family_frame_v4(), "Fresh family frame v4 drift")
    require(len(value["families"]) == 4 and len(value["worlds"]) == 8,
            "Fresh v4 family coverage changed")
    require(len({item["snapshot_sha256"] for item in value["worlds"]}) == 8,
            "Fresh v4 worlds must be distinct")
    for item in value["worlds"]:
        validate_spec(item["world"])
        role_visible = [fact for fact in item["world"]["facts"].values()
                        if fact["visible_to"] is not None]
        require(len(role_visible) == 4 and sum(not fact["disclosable"] for fact in role_visible) == 1,
                "Each world requires three disclosable role traces and one protected fact")
    return deepcopy(value)
