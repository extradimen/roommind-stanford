"""Role-specific, condition-neutral cards for the fresh v2 worlds."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.fresh_family_frame_v2 import fresh_family_frame_v2
from app.g5.fresh_family_roles import fresh_family_role_pack
from app.g5.measurement import require
from app.g5.role_inputs import validate_inputs


_ROLE_GOALS = {
    "library_director": "Reach a lawful allocation only after both specialist reviews.",
    "accessibility_advisor": "Surface access constraints before endorsing an allocation.",
    "youth_program_lead": "Represent observed youth demand without claiming approval authority.",
    "archivist": "Protect preservation requirements and complete the registered review.",
    "principal_investigator": "Authorize release only after privacy and reproducibility review.",
    "privacy_officer": "Assess privacy risk and never disclose protected linkage material.",
    "reproducibility_reviewer": "Resolve or clearly preserve replication uncertainty.",
    "partner_representative": "State partner timing constraints without authorizing release.",
    "museum_curator": "Approve a loan only after condition and insurance prerequisites.",
    "conservation_scientist": "Report material risk and own the condition report.",
    "insurance_representative": "Bind coverage only within declared insurance authority.",
    "lender_coordinator": "Represent lender conditions without impersonating museum authority.",
    "transit_scheduler": "Approve a schedule only after driver and equity prerequisites.",
    "rider_advocate": "Surface mobility and equity impacts before closure.",
    "driver_representative": "State operator feasibility and own its registered confirmation.",
    "budget_analyst": "Describe funding constraints without approving service changes.",
}


def fresh_family_role_pack_v2():
    frame, parent = fresh_family_frame_v2(), fresh_family_role_pack()
    cards = deepcopy(parent["scenario_roles"])
    for world in frame["worlds"]:
        for role, card in cards[world["scenario_id"]].items():
            card["private"]["persona"] = "Role-specific, evidence-aware, and willing to preserve disagreement."
            card["private"]["goals"] = [_ROLE_GOALS[role],
                "Distinguish private knowledge, public claims, and structured successful receipts."]
            card["private"]["instructions"] = (
                "Use only facts visible to this role and public observations. Disclose a visible fact only "
                "when it is marked disclosable. Execute only registered operations within your authority; "
                "do not optimize for consensus, condition guessing, or premature closure.")
        validate_inputs(cards[world["scenario_id"]], world["world"]["roles"])
    raw = {"schema": "g5-fresh-family-role-pack-v2", "frame_sha256": frame["sha256"],
           "supersedes_role_pack_sha256": parent["sha256"], "scenario_roles": cards,
           "condition_specific_content": False, "dialogues_generated": 0,
           "external_execution_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_role_pack_v2(value):
    require(value == fresh_family_role_pack_v2(), "Fresh family role pack v2 drift")
    frame = fresh_family_frame_v2()
    for world in frame["worlds"]:
        cards = value["scenario_roles"][world["scenario_id"]]
        validate_inputs(cards, world["world"]["roles"])
        require(len({tuple(card["private"]["goals"]) for card in cards.values()}) == 4,
                "Every role needs a distinct strategic goal")
    return deepcopy(value)
