"""Fresh role-pack tests; no dialogue generation."""
import copy
import json
import unittest

from app.g5.fresh_family_roles import fresh_family_role_pack, validate_fresh_family_role_pack
from app.g5.fresh_family_frame import fresh_family_frame
from app.factorial_study import digest, freeze_design
from app.g5.runtime import Runtime
from app.g5.world import Decision, World
from test_g5_runtime import manifest


class FreshFamilyRoleTests(unittest.TestCase):
    def test_all_scenarios_have_one_player_and_three_npcs(self):
        pack = validate_fresh_family_role_pack(fresh_family_role_pack())
        self.assertEqual(len(pack["scenario_roles"]), 8)
        for cards in pack["scenario_roles"].values():
            kinds = [card["public"]["kind"] for card in cards.values()]
            self.assertEqual(kinds.count("player"), 1)
            self.assertEqual(kinds.count("npc"), 3)
        text = json.dumps(pack).lower()
        self.assertNotIn("roommind", text)
        self.assertNotIn("baseline", text)

    def test_role_pack_tamper_is_rejected(self):
        changed = copy.deepcopy(fresh_family_role_pack())
        scenario = next(iter(changed["scenario_roles"]))
        role = next(iter(changed["scenario_roles"][scenario]))
        changed["scenario_roles"][scenario][role]["private"]["goals"].append("changed")
        with self.assertRaises(ValueError):
            validate_fresh_family_role_pack(changed)

    def test_manifest_binds_distinct_role_tables_by_scenario(self):
        frame, pack = fresh_family_frame(), fresh_family_role_pack()
        design = manifest()["design"]
        design["scenarios"] = [{"id": item["scenario_id"], "family": item["family_id"],
                                "snapshot_sha256": item["snapshot_sha256"]}
                               for item in frame["worlds"]]
        role_index = {scenario: digest(cards) for scenario, cards in pack["scenario_roles"].items()}
        design["scenario_role_inputs_sha256"] = role_index
        for arm in design["arms"].values():
            arm["shared"]["role_inputs_sha256"] = digest(role_index)
        frozen = freeze_design(design)
        for item in frame["worlds"]:
            assignment = next(row for row in frozen["assignments"]
                              if row["scenario_id"] == item["scenario_id"] and row["arm"] == "A")
            world = World(":memory:")
            self.addCleanup(world.close)
            Runtime(world=world, world_id=item["scenario_id"], spec=item["world"], manifest=frozen,
                    ordinal=assignment["ordinal"], policy=lambda view, feedback: Decision("wait"),
                    max_steps=4, role_inputs=pack["scenario_roles"][item["scenario_id"]])

    def test_manifest_rejects_incomplete_or_unbound_role_index(self):
        frame, pack = fresh_family_frame(), fresh_family_role_pack()
        design = manifest()["design"]
        design["scenarios"] = [{"id": item["scenario_id"], "family": item["family_id"],
                                "snapshot_sha256": item["snapshot_sha256"]}
                               for item in frame["worlds"]]
        role_index = {scenario: digest(cards) for scenario, cards in pack["scenario_roles"].items()}
        design["scenario_role_inputs_sha256"] = role_index
        with self.assertRaises(ValueError):
            freeze_design(design)
        design["scenario_role_inputs_sha256"].pop(next(iter(role_index)))
        for arm in design["arms"].values():
            arm["shared"]["role_inputs_sha256"] = digest(design["scenario_role_inputs_sha256"])
        with self.assertRaises(ValueError):
            freeze_design(design)


if __name__ == "__main__":
    unittest.main()
