"""Condition-neutral role cards for untouched scorer-v4 validation worlds."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.fresh_family_frame_v4 import fresh_family_frame_v4
from app.g5.measurement import require
from app.g5.role_inputs import validate_inputs


_PROFILES = {
    "orchard_operations_director": ("Inez Calder", "Orchard Operations Director", "crop operations", "Authorize frost response once forecast and irrigation protection are ready."),
    "agronomist": ("Rowan Okafor", "Agronomist", "crop science", "Interpret frost exposure and own forecast confirmation."),
    "irrigation_supervisor": ("Pavel Dinh", "Irrigation Supervisor", "water systems", "Assess protective irrigation and own readiness."),
    "grower_liaison": ("Mara Velez", "Grower Liaison", "grower relations", "Surface grower constraints without authorizing the response."),
    "archive_director": ("Keira Sato", "Archive Director", "collection stewardship", "Authorize transfer after condition documentation and route security."),
    "conservation_assessor": ("Luc Moreau", "Conservation Assessor", "material conservation", "Assess exposure and own condition documentation."),
    "security_custodian": ("Hana Petrov", "Security Custodian", "collection security", "Assess custody controls and own route security."),
    "donor_liaison": ("Joel Nwosu", "Donor Liaison", "donor relations", "Surface donor restrictions without authorizing transfer."),
    "mission_operations_chief": ("Asha Raman", "Mission Operations Chief", "mission operations", "Authorize the pass after orbit and antenna readiness."),
    "orbit_analyst": ("Felix Bauer", "Orbit Analyst", "flight dynamics", "Assess tracking uncertainty and own orbit confirmation."),
    "antenna_controller": ("Yuna Delgado", "Antenna Controller", "ground systems", "Assess link readiness and own antenna configuration."),
    "payload_coordinator": ("Caleb Mensah", "Payload Coordinator", "payload planning", "Surface payload priorities without authorizing the pass."),
    "nutrition_services_director": ("Simone Hart", "Nutrition Services Director", "school nutrition", "Issue the recall notice after verification and distribution halt."),
    "food_safety_specialist": ("Ravi Desai", "Food Safety Specialist", "food safety", "Assess allergen evidence and own finding verification."),
    "distribution_coordinator": ("Marta Kowalski", "Distribution Coordinator", "meal logistics", "Trace deliveries and own the distribution halt."),
    "family_liaison": ("Idris Chen", "Family Liaison", "family communication", "Surface family communication needs without issuing the recall."),
}
_PLAYERS = {"orchard_operations_director", "archive_director", "mission_operations_chief",
            "nutrition_services_director"}


def fresh_family_role_pack_v4():
    frame = fresh_family_frame_v4()
    scenario_roles = {}
    for world in frame["worlds"]:
        cards = {}
        for role in world["world"]["roles"]:
            name, title, side, goal = _PROFILES[role]
            cards[role] = {"public": {"name": name, "job_title": title, "side": side,
                "kind": "player" if role in _PLAYERS else "npc"},
                "private": {"persona": "Role-specific, evidence-aware, and willing to preserve disagreement.",
                    "goals": [goal, "Distinguish role-visible traces, public claims, and registered receipts."],
                    "instructions": "Use only facts visible to this role and public observations. Disclose a visible fact only when marked disclosable. Execute only registered operations within your authority. Preserve justified uncertainty, refusal, and unresolved work."}}
        validate_inputs(cards, world["world"]["roles"])
        require(sum(card["public"]["kind"] == "player" for card in cards.values()) == 1,
                "Exactly one fixed player role required")
        require(len({tuple(card["private"]["goals"]) for card in cards.values()}) == 4,
                "Every role needs a distinct strategic goal")
        scenario_roles[world["scenario_id"]] = cards
    raw = {"schema": "g5-fresh-family-role-pack-v4", "frame_sha256": frame["sha256"],
        "scenario_roles": scenario_roles, "condition_specific_content": False,
        "dialogues_generated": 0, "external_execution_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_role_pack_v4(value):
    require(value == fresh_family_role_pack_v4(), "Fresh family role pack v4 drift")
    frame = fresh_family_frame_v4()
    for world in frame["worlds"]:
        validate_inputs(value["scenario_roles"][world["scenario_id"]], world["world"]["roles"])
    return deepcopy(value)
