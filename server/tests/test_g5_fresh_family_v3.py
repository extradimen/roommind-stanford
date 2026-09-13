"""Untouched scorer-v3 material checks; no model or network calls."""
import json
import unittest

from app.g5.fresh_family_frame_v2 import fresh_family_frame_v2
from app.g5.fresh_family_frame_v3 import fresh_family_frame_v3, validate_fresh_family_frame_v3
from app.g5.fresh_family_roles_v2 import fresh_family_role_pack_v2
from app.g5.fresh_family_roles_v3 import fresh_family_role_pack_v3, validate_fresh_family_role_pack_v3
from app.g5.fresh_validation_plan_v3 import fresh_validation_plan_v3, validate_fresh_validation_plan_v3
from app.g5.fresh_execution_v12 import execution_binding


class FreshFamilyV3Tests(unittest.TestCase):
    def test_new_domains_roles_and_values_do_not_reuse_v11_material(self):
        old_frame, new_frame = fresh_family_frame_v2(), fresh_family_frame_v3()
        self.assertTrue(set(old_frame["families"]).isdisjoint(new_frame["families"]))
        old_roles = {role for world in old_frame["worlds"] for role in world["world"]["roles"]}
        new_roles = {role for world in new_frame["worlds"] for role in world["world"]["roles"]}
        self.assertTrue(old_roles.isdisjoint(new_roles))
        old_names = {card["public"]["name"] for cards in
                     fresh_family_role_pack_v2()["scenario_roles"].values() for card in cards.values()}
        new_names = {card["public"]["name"] for cards in
                     fresh_family_role_pack_v3()["scenario_roles"].values() for card in cards.values()}
        self.assertTrue(old_names.isdisjoint(new_names))
        old_blob = json.dumps(old_frame, sort_keys=True)
        for family in new_frame["families"]:
            self.assertNotIn(family, old_blob)

    def test_frame_roles_and_plan_validate_with_balanced_assignments(self):
        frame = validate_fresh_family_frame_v3(fresh_family_frame_v3())
        roles = validate_fresh_family_role_pack_v3(fresh_family_role_pack_v3())
        plan = validate_fresh_validation_plan_v3(fresh_validation_plan_v3())
        self.assertEqual(len(frame["worlds"]), 8)
        self.assertEqual(set(roles["scenario_roles"]),
                         {world["scenario_id"] for world in frame["worlds"]})
        counts = {arm: 0 for arm in "ABCD"}
        for row in plan["assignments"]:
            counts[row["arm"]] += 1
        self.assertEqual(counts, {arm: 2 for arm in "ABCD"})
        self.assertFalse(plan["external_execution_authorized"])
        self.assertFalse(plan["launch_authorized"])

    def test_execution_binding_is_local_only_and_selects_one_balanced_arm_per_world(self):
        execution = execution_binding("a" * 40, authorization_id="fixture-not-external-authority")
        self.assertEqual(execution["schema"], "g5-fresh-family-v12-execution-binding-v1")
        self.assertEqual(execution["dialogue_count"], 8)
        self.assertEqual(execution["max_steps"], 16)
        self.assertFalse(execution["evaluation_authorized"])
        self.assertFalse(execution["complete_block_screening_authorized"])
        self.assertEqual(execution["frame_sha256"], fresh_family_frame_v3()["sha256"])
        self.assertEqual(execution["role_pack_sha256"], fresh_family_role_pack_v3()["sha256"])
        self.assertEqual(execution["validation_plan_sha256"], fresh_validation_plan_v3()["sha256"])
        counts = {arm: 0 for arm in "ABCD"}
        for row in execution["selected_assignments"]:
            counts[row["arm"]] += 1
        self.assertEqual(counts, {arm: 2 for arm in "ABCD"})


if __name__ == "__main__":
    unittest.main()
