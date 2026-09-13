"""Condition-neutral role cards for untouched scorer-v3 validation worlds."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.fresh_family_frame_v3 import fresh_family_frame_v3
from app.g5.measurement import require
from app.g5.role_inputs import validate_inputs


_PROFILES = {
    "shelter_coordinator": ("Dana Mercer", "Shelter Coordinator", "emergency coordination",
                            "Activate the shelter only after structural and accessible-route checks."),
    "structural_engineer": ("Eli Navarro", "Structural Engineer", "building safety",
                            "Assess structural readiness and own the registered clearance."),
    "access_liaison": ("Mei Foster", "Access Liaison", "inclusive evacuation",
                       "Surface route barriers and own accessible-route confirmation."),
    "supply_officer": ("Omar Bell", "Supply Officer", "relief logistics",
                       "Describe supply constraints without activating the shelter."),
    "expedition_lead": ("Leona Price", "Expedition Lead", "field research",
                        "Authorize departure only after safety and ethics prerequisites."),
    "field_safety_officer": ("Anton Silva", "Field Safety Officer", "field safety",
                             "Assess field hazards and own acceptance of the safety plan."),
    "ethics_coordinator": ("Priya Mensah", "Ethics Coordinator", "research ethics",
                           "Protect consent requirements and own ethics clearance."),
    "logistics_manager": ("Jonah Reed", "Logistics Manager", "transport logistics",
                          "Describe transport constraints without authorizing departure."),
    "public_health_director": ("Dr. Celia Park", "Public Health Director", "public health",
                               "Issue an advisory only after laboratory confirmation and zone isolation."),
    "laboratory_scientist": ("Dr. Mateo Klein", "Laboratory Scientist", "water laboratory",
                             "Report analytical uncertainty and own laboratory confirmation."),
    "utility_operator": ("Nadia Cole", "Utility Operator", "water operations",
                         "Represent network operations and own isolation of the affected zone."),
    "communications_officer": ("Theo Ibrahim", "Communications Officer", "public communication",
                               "Surface language-access needs without issuing the advisory."),
    "commissioning_manager": ("Sana Brooks", "Commissioning Manager", "energy commissioning",
                              "Approve handover only after inspection and maintenance acceptance."),
    "electrical_inspector": ("Victor Huang", "Electrical Inspector", "electrical safety",
                             "Assess protection readiness and own the registered inspection."),
    "maintenance_lead": ("Alina Costa", "Maintenance Lead", "asset maintenance",
                         "Assess maintainability and own package acceptance."),
    "community_representative": ("Marcus Adeyemi", "Community Representative", "resident interests",
                                 "Surface service and outage impacts without approving handover."),
}
_PLAYERS = {"shelter_coordinator", "expedition_lead", "public_health_director",
            "commissioning_manager"}


def fresh_family_role_pack_v3():
    frame = fresh_family_frame_v3()
    scenario_roles = {}
    for world in frame["worlds"]:
        cards = {}
        for role in world["world"]["roles"]:
            name, title, side, goal = _PROFILES[role]
            cards[role] = {"public": {"name": name, "job_title": title, "side": side,
                "kind": "player" if role in _PLAYERS else "npc"},
                "private": {"persona": "Role-specific, evidence-aware, and willing to preserve disagreement.",
                    "goals": [goal, "Distinguish private signals, public claims, and registered receipts."],
                    "instructions": "Use only facts visible to this role and public observations. Disclose a visible fact only when marked disclosable. Execute only registered operations within your authority. Preserve justified uncertainty, refusal, and unresolved work."}}
        validate_inputs(cards, world["world"]["roles"])
        require(sum(card["public"]["kind"] == "player" for card in cards.values()) == 1,
                "Exactly one fixed player role required")
        require(len({tuple(card["private"]["goals"]) for card in cards.values()}) == 4,
                "Every role needs a distinct strategic goal")
        scenario_roles[world["scenario_id"]] = cards
    raw = {"schema": "g5-fresh-family-role-pack-v3", "frame_sha256": frame["sha256"],
        "scenario_roles": scenario_roles, "condition_specific_content": False,
        "dialogues_generated": 0, "external_execution_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_role_pack_v3(value):
    require(value == fresh_family_role_pack_v3(), "Fresh family role pack v3 drift")
    frame = fresh_family_frame_v3()
    for world in frame["worlds"]:
        validate_inputs(value["scenario_roles"][world["scenario_id"]], world["world"]["roles"])
    return deepcopy(value)
