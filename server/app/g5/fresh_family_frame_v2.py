"""Epistemically discriminating successor to the preserved v1 fresh frame."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.fresh_family_frame import fresh_family_frame
from app.g5.measurement import require
from app.g5.world import validate_spec


_PRIVATE = {
    "library-space-allocation": {
        "accessibility_advisor": ("access_route_constraint", ["accessibility_advisor"], True),
        "youth_program_lead": ("peak_youth_attendance_pattern", ["youth_program_lead"], True),
        "archivist": ("fragile_collection_location", ["archivist"], True),
        "library_director": ("confidential_patron_identity", ["library_director"], False),
    },
    "research-data-release": {
        "privacy_officer": ("reidentification_risk", ["privacy_officer"], True),
        "reproducibility_reviewer": ("unresolved_replication_gap", ["reproducibility_reviewer"], True),
        "partner_representative": ("partner_embargo_window", ["partner_representative"], True),
        "principal_investigator": ("protected_participant_linkage_key", ["principal_investigator"], False),
    },
    "museum-loan-conservation": {
        "conservation_scientist": ("material_instability", ["conservation_scientist"], True),
        "insurance_representative": ("coverage_exclusion", ["insurance_representative"], True),
        "lender_coordinator": ("lender_display_condition", ["lender_coordinator"], True),
        "museum_curator": ("confidential_security_weakness", ["museum_curator"], False),
    },
    "community-transit-adjustment": {
        "driver_representative": ("operator_break_constraint", ["driver_representative"], True),
        "rider_advocate": ("mobility_access_gap", ["rider_advocate"], True),
        "budget_analyst": ("contingency_funding_limit", ["budget_analyst"], True),
        "transit_scheduler": ("protected_driver_roster", ["transit_scheduler"], False),
    },
}


def fresh_family_frame_v2():
    parent = fresh_family_frame()
    worlds = []
    for source in parent["worlds"]:
        item = deepcopy(source)
        for index, (role, (name, visible, disclosable)) in enumerate(
                _PRIVATE[item["family_id"]].items(), 1):
            item["world"]["facts"][name] = {
                "value": f"variant-{item['variant']}-role-signal-{index}",
                "visible_to": visible, "disclosable": disclosable}
        validate_spec(item["world"])
        item["snapshot_sha256"] = digest(item["world"])
        worlds.append(item)
    raw = {"schema": "g5-fresh-family-frame-v2", "classification": "internal-pre-generation",
           "supersedes_frame_sha256": parent["sha256"], "families": parent["families"],
           "worlds": worlds, "legacy_family_reuse": False, "dialogues_generated": 0,
           "reference_labels_collected": 0, "external_execution_authorized": False,
           "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


def validate_fresh_family_frame_v2(value):
    require(value == fresh_family_frame_v2(), "Fresh family frame v2 drift")
    require(len(value["worlds"]) == 8 and len({w["snapshot_sha256"] for w in value["worlds"]}) == 8,
            "Fresh v2 world coverage changed")
    for item in value["worlds"]:
        validate_spec(item["world"])
        private = [f for f in item["world"]["facts"].values() if f["visible_to"] is not None]
        require(len(private) == 4 and sum(not f["disclosable"] for f in private) == 1,
                "Each v2 world needs three disclosable and one protected role fact")
    return deepcopy(value)
