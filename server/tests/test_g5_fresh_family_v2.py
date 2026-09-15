"""Epistemic and strategic coverage checks for preserved-successor v2 inputs."""
import copy
import unittest

from app.g5.fresh_family_frame import fresh_family_frame
from app.g5.fresh_family_frame_v2 import fresh_family_frame_v2, validate_fresh_family_frame_v2
from app.g5.fresh_family_roles import fresh_family_role_pack
from app.g5.fresh_family_roles_v2 import fresh_family_role_pack_v2, validate_fresh_family_role_pack_v2
from app.g5.fresh_validation_plan import fresh_validation_plan
from app.g5.fresh_validation_plan_v2 import fresh_validation_plan_v2, validate_fresh_validation_plan_v2


class FreshFamilyV2Tests(unittest.TestCase):
    def test_v1_is_preserved_and_v2_adds_epistemic_discrimination(self):
        old = fresh_family_frame()
        new = validate_fresh_family_frame_v2(fresh_family_frame_v2())
        self.assertEqual(new["supersedes_frame_sha256"], old["sha256"])
        self.assertNotEqual(new["sha256"], old["sha256"])
        for world in new["worlds"]:
            private = [fact for fact in world["world"]["facts"].values()
                       if fact["visible_to"] is not None]
            self.assertEqual(len(private), 4)
            self.assertEqual(sum(not fact["disclosable"] for fact in private), 1)

    def test_v2_roles_have_distinct_goals_and_no_condition_labels(self):
        old = fresh_family_role_pack()
        new = validate_fresh_family_role_pack_v2(fresh_family_role_pack_v2())
        self.assertEqual(new["supersedes_role_pack_sha256"], old["sha256"])
        for cards in new["scenario_roles"].values():
            self.assertEqual(len({tuple(card["private"]["goals"]) for card in cards.values()}), 4)
        self.assertNotIn("roommind", str(new).lower())
        self.assertNotIn("baseline", str(new).lower())

    def test_rehashed_tamper_is_rejected(self):
        changed = copy.deepcopy(fresh_family_frame_v2())
        changed["worlds"][0]["world"]["facts"]["access_route_constraint"]["visible_to"] = None
        with self.assertRaises(ValueError): validate_fresh_family_frame_v2(changed)

    def test_v2_validation_plan_supersedes_but_preserves_v1(self):
        old, new = fresh_validation_plan(), validate_fresh_validation_plan_v2(fresh_validation_plan_v2())
        self.assertEqual(new["supersedes_plan_sha256"], old["sha256"])
        self.assertNotEqual(new["frame_sha256"], old["frame_sha256"])
        self.assertEqual({arm: sum(row["arm"] == arm for row in new["assignments"])
                          for arm in "ABCD"}, {arm: 2 for arm in "ABCD"})
        self.assertFalse(new["launch_authorized"])


if __name__ == "__main__": unittest.main()
