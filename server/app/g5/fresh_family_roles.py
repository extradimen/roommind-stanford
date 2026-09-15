"""Condition-neutral role cards for the fresh-family frame."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.fresh_family_frame import fresh_family_frame
from app.g5.measurement import require
from app.g5.role_inputs import validate_inputs


_TITLES = {
    "library_director": ("Morgan Lee", "Library Director", "library leadership"),
    "accessibility_advisor": ("Avery Chen", "Accessibility Advisor", "accessibility"),
    "youth_program_lead": ("Riley Gomez", "Youth Program Lead", "youth services"),
    "archivist": ("Samira Patel", "Archivist", "archives"),
    "principal_investigator": ("Dr. Rowan Kim", "Principal Investigator", "research leadership"),
    "privacy_officer": ("Jordan Okafor", "Privacy Officer", "privacy"),
    "reproducibility_reviewer": ("Casey Novak", "Reproducibility Reviewer", "methods review"),
    "partner_representative": ("Taylor Singh", "Partner Representative", "partner institution"),
    "museum_curator": ("Alex Laurent", "Museum Curator", "curatorial"),
    "conservation_scientist": ("Dr. Noor Haddad", "Conservation Scientist", "conservation"),
    "insurance_representative": ("Jamie Brooks", "Insurance Representative", "insurance"),
    "lender_coordinator": ("Mina Rossi", "Lender Coordinator", "lending institution"),
    "transit_scheduler": ("Cameron Wu", "Transit Scheduler", "service planning"),
    "rider_advocate": ("Imani Johnson", "Rider Advocate", "rider interests"),
    "driver_representative": ("Luis Ortega", "Driver Representative", "operators"),
    "budget_analyst": ("Harper Evans", "Budget Analyst", "finance"),
}
_PLAYERS = {"library_director", "principal_investigator", "museum_curator", "transit_scheduler"}


def fresh_family_role_pack():
    frame = fresh_family_frame()
    cards = {}
    for world in frame["worlds"]:
        role_cards = {}
        for role in world["world"]["roles"]:
            name, title, side = _TITLES[role]
            is_player = role in _PLAYERS
            role_cards[role] = {"public": {"name": name, "job_title": title, "side": side,
                "kind": "player" if is_player else "npc"},
                "private": {"persona": "Direct, evidence-aware, and willing to preserve unresolved disagreement.",
                    "goals": ["Represent the declared role and its interests.",
                              "Do not treat public claims as successful simulation actions."],
                    "instructions": ("Use only visible world facts and public observations. "
                        "Execute only registered operations within your authority. State uncertainty, refusal, "
                        "or bounded deferral when appropriate; do not optimize for consensus or closure.")}}
        validate_inputs(role_cards, world["world"]["roles"])
        require(sum(card["public"]["kind"] == "player" for card in role_cards.values()) == 1,
                "Exactly one fixed player role required")
        cards[world["scenario_id"]] = role_cards
    raw = {"schema": "g5-fresh-family-role-pack-v1", "frame_sha256": frame["sha256"],
        "scenario_roles": cards, "condition_specific_content": False,
        "dialogues_generated": 0, "external_execution_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_role_pack(value):
    require(value == fresh_family_role_pack(), "Fresh family role pack drift")
    frame = fresh_family_frame()
    for world in frame["worlds"]:
        validate_inputs(value["scenario_roles"][world["scenario_id"]], world["world"]["roles"])
    return deepcopy(value)
