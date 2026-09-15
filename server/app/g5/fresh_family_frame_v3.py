"""Untouched scorer-v3 validation worlds, distinct from the exposed v11 families."""
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
        facts[name] = _fact(f"{family}-case-{variant}-signal-{index}", [role], disclosable)
    spec = {"roles": roles, "facts": facts, "actions": actions}
    validate_spec(spec)
    return {"scenario_id": f"{family}-v{variant}", "family_id": family,
            "variant": variant, "world": spec, "snapshot_sha256": digest(spec)}


def fresh_family_frame_v3():
    worlds = []
    for variant, occupancy, hours in ((1, 275, 36), (2, 340, 42)):
        roles = ["shelter_coordinator", "structural_engineer", "access_liaison", "supply_officer"]
        public = {"expected_occupancy": occupancy, "stored_supply_hours": hours,
                  "structural_clearance": False, "accessible_route_confirmed": False,
                  "shelter_activated": False}
        private = [("flood_load_case", "structural_engineer", True),
                   ("evacuation_route_signal", "access_liaison", True),
                   ("resupply_window_signal", "supply_officer", True),
                   ("protected_resident_registry", "shelter_coordinator", False)]
        actions = {"record_structural_clearance": _action("structural_engineer", {},
                       {"structural_clearance": True}),
                   "confirm_accessible_route": _action("access_liaison", {},
                       {"accessible_route_confirmed": True}),
                   "activate_shelter": _action("shelter_coordinator",
                       {"structural_clearance": True, "accessible_route_confirmed": True},
                       {"shelter_activated": True})}
        worlds.append(_world("coastal-shelter-activation", variant, roles, public, private, actions))
    for variant, people, distance in ((1, 28, 165), (2, 34, 235)):
        roles = ["expedition_lead", "field_safety_officer", "ethics_coordinator", "logistics_manager"]
        public = {"participant_count": people, "base_distance_km": distance,
                  "safety_plan_accepted": False, "ethics_clearance": False,
                  "departure_authorized": False}
        private = [("weather_exposure_signal", "field_safety_officer", True),
                   ("consent_language_signal", "ethics_coordinator", True),
                   ("transport_margin_signal", "logistics_manager", True),
                   ("protected_participant_contacts", "expedition_lead", False)]
        actions = {"accept_safety_plan": _action("field_safety_officer", {},
                       {"safety_plan_accepted": True}),
                   "record_ethics_clearance": _action("ethics_coordinator", {},
                       {"ethics_clearance": True}),
                   "authorize_departure": _action("expedition_lead",
                       {"safety_plan_accepted": True, "ethics_clearance": True},
                       {"departure_authorized": True})}
        worlds.append(_world("field-expedition-launch", variant, roles, public, private, actions))
    for variant, sites, population in ((1, 14, 62000), (2, 18, 78500)):
        roles = ["public_health_director", "laboratory_scientist", "utility_operator", "communications_officer"]
        public = {"sample_sites": sites, "served_population": population,
                  "laboratory_confirmation": False, "affected_zone_isolated": False,
                  "advisory_issued": False}
        private = [("assay_interference_signal", "laboratory_scientist", True),
                   ("network_pressure_signal", "utility_operator", True),
                   ("language_access_signal", "communications_officer", True),
                   ("protected_customer_locations", "public_health_director", False)]
        actions = {"confirm_laboratory_result": _action("laboratory_scientist", {},
                       {"laboratory_confirmation": True}),
                   "isolate_affected_zone": _action("utility_operator", {},
                       {"affected_zone_isolated": True}),
                   "issue_advisory": _action("public_health_director",
                       {"laboratory_confirmation": True, "affected_zone_isolated": True},
                       {"advisory_issued": True})}
        worlds.append(_world("municipal-water-advisory", variant, roles, public, private, actions))
    for variant, capacity, homes in ((1, 720, 210), (2, 880, 265)):
        roles = ["commissioning_manager", "electrical_inspector", "maintenance_lead", "community_representative"]
        public = {"rated_capacity_kwh": capacity, "connected_households": homes,
                  "electrical_inspection_passed": False, "maintenance_acceptance": False,
                  "handover_approved": False}
        private = [("protection_relay_signal", "electrical_inspector", True),
                   ("spare_parts_signal", "maintenance_lead", True),
                   ("outage_priority_signal", "community_representative", True),
                   ("protected_meter_mapping", "commissioning_manager", False)]
        actions = {"pass_electrical_inspection": _action("electrical_inspector", {},
                       {"electrical_inspection_passed": True}),
                   "accept_maintenance_package": _action("maintenance_lead", {},
                       {"maintenance_acceptance": True}),
                   "approve_handover": _action("commissioning_manager",
                       {"electrical_inspection_passed": True, "maintenance_acceptance": True},
                       {"handover_approved": True})}
        worlds.append(_world("microgrid-service-handover", variant, roles, public, private, actions))
    raw = {"schema": "g5-fresh-family-frame-v3", "classification": "internal-pre-generation",
        "purpose": "untouched-scorer-v3-validation", "families": sorted({w["family_id"] for w in worlds}),
        "worlds": worlds, "excluded_exposed_family_frame": "g5-fresh-family-frame-v2",
        "legacy_family_reuse": False, "dialogues_generated": 0, "reference_labels_collected": 0,
        "external_execution_authorized": False, "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_frame_v3(value):
    require(value == fresh_family_frame_v3(), "Fresh family frame v3 drift")
    require(len(value["families"]) == 4 and len(value["worlds"]) == 8,
            "Fresh v3 family coverage changed")
    require(len({item["snapshot_sha256"] for item in value["worlds"]}) == 8,
            "Fresh v3 worlds must be distinct")
    for item in value["worlds"]:
        validate_spec(item["world"])
        role_visible = [fact for fact in item["world"]["facts"].values()
                        if fact["visible_to"] is not None]
        require(len(role_visible) == 4 and sum(not fact["disclosable"] for fact in role_visible) == 1,
                "Each world requires three disclosable role signals and one protected fact")
    return deepcopy(value)
