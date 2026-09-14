"""Untouched scorer-v4 material isolation tests; no model or network calls."""
import unittest

from app.g5.fresh_family_frame_v2 import fresh_family_frame_v2
from app.g5.fresh_family_frame_v3 import fresh_family_frame_v3
from app.g5.fresh_family_frame_v4 import fresh_family_frame_v4, validate_fresh_family_frame_v4
from app.g5.fresh_family_roles_v2 import fresh_family_role_pack_v2
from app.g5.fresh_family_roles_v3 import fresh_family_role_pack_v3
from app.g5.fresh_family_roles_v4 import (fresh_family_role_pack_v4,
                                          validate_fresh_family_role_pack_v4)
from app.g5.fresh_validation_plan_v4 import fresh_validation_plan_v4, validate_fresh_validation_plan_v4


def identifiers(frame):
    return {
        "families": set(frame["families"]),
        "roles": {role for world in frame["worlds"] for role in world["world"]["roles"]},
        "numbers": {fact["value"] for world in frame["worlds"]
                    for fact in world["world"]["facts"].values()
                    if type(fact["value"]) in (int, float)},
    }


def names(pack):
    return {card["public"]["name"] for cards in pack["scenario_roles"].values()
            for card in cards.values()}


class FreshFamilyV4Tests(unittest.TestCase):
    def test_frame_roles_and_balanced_plan_validate(self):
        validate_fresh_family_frame_v4(fresh_family_frame_v4())
        validate_fresh_family_role_pack_v4(fresh_family_role_pack_v4())
        validate_fresh_validation_plan_v4(fresh_validation_plan_v4())

    def test_v11_and_v14_identifiers_names_and_numbers_are_disjoint(self):
        current = identifiers(fresh_family_frame_v4())
        for exposed in (identifiers(fresh_family_frame_v2()),
                        identifiers(fresh_family_frame_v3())):
            for key in current:
                self.assertTrue(current[key].isdisjoint(exposed[key]), key)
        exposed_names = names(fresh_family_role_pack_v2()) | names(fresh_family_role_pack_v3())
        self.assertTrue(names(fresh_family_role_pack_v4()).isdisjoint(exposed_names))


if __name__ == "__main__":
    unittest.main()
