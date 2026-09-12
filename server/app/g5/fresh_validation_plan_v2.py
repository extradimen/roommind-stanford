"""Scorer-validation plan bound to the epistemically discriminating v2 inputs."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.fresh_family_frame_v2 import fresh_family_frame_v2
from app.g5.fresh_family_roles_v2 import fresh_family_role_pack_v2
from app.g5.fresh_validation_plan import fresh_validation_plan
from app.g5.measurement import require


def fresh_validation_plan_v2():
    parent, frame, roles = (fresh_validation_plan(), fresh_family_frame_v2(),
                            fresh_family_role_pack_v2())
    role_index = {scenario: digest(cards) for scenario, cards in roles["scenario_roles"].items()}
    worlds = {world["scenario_id"]: world for world in frame["worlds"]}
    raw = deepcopy({key: value for key, value in parent.items() if key != "sha256"})
    raw.update(schema="g5-fresh-scorer-validation-plan-v2",
               supersedes_plan_sha256=parent["sha256"], frame_sha256=frame["sha256"],
               role_pack_sha256=roles["sha256"], scenario_role_inputs_sha256=role_index,
               role_inputs_index_sha256=digest(role_index))
    for row in raw["assignments"]:
        world = worlds[row["scenario_id"]]
        row["snapshot_sha256"] = world["snapshot_sha256"]
        row["role_inputs_sha256"] = role_index[row["scenario_id"]]
    return {**raw, "sha256": digest(raw)}


def validate_fresh_validation_plan_v2(value):
    require(value == fresh_validation_plan_v2(), "Fresh validation plan v2 drift")
    require(len(value["assignments"]) == 8 and
            {arm: sum(row["arm"] == arm for row in value["assignments"])
             for arm in "ABCD"} == {arm: 2 for arm in "ABCD"},
            "Fresh validation v2 assignment drift")
    require(value["source_revision"] is None and value["model_binding"] is None and
            not value["launch_authorized"], "Unbound v2 plan cannot launch")
    return deepcopy(value)
