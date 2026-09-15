"""Fresh scenario-family frame tests; no generation or external calls."""
import copy
import unittest

from app.g5.fresh_family_frame import fresh_family_frame, validate_fresh_family_frame
from app.g5.world import Decision, World


class FreshFamilyFrameTests(unittest.TestCase):
    def test_four_families_two_distinct_valid_worlds_each(self):
        frame = validate_fresh_family_frame(fresh_family_frame())
        counts = {family: 0 for family in frame["families"]}
        for item in frame["worlds"]:
            counts[item["family_id"]] += 1
        self.assertEqual(set(counts.values()), {2})
        self.assertFalse(frame["legacy_family_reuse"])
        self.assertFalse(frame["external_execution_authorized"])

    def test_world_actions_enforce_prerequisites_and_structured_receipts(self):
        frame = fresh_family_frame()
        for index, item in enumerate(frame["worlds"]):
            world = World(":memory:")
            self.addCleanup(world.close)
            world.create(str(index), item["world"], {})
            final_name, final_action = list(item["world"]["actions"].items())[-1]
            event = world.commit(str(index), expected_version=0, request_id="blocked",
                actor=final_action["actors"][0],
                decision=Decision("execute", operation=final_name),
                audit={})
            self.assertEqual(event["payload"]["receipt"]["status"], "blocked")
            self.assertEqual(event["payload"]["receipt"]["effects"], {})

    def test_tamper_is_rejected(self):
        changed = copy.deepcopy(fresh_family_frame())
        changed["worlds"][0]["world"]["facts"]["room_capacity"]["value"] += 1
        with self.assertRaises(ValueError):
            validate_fresh_family_frame(changed)


if __name__ == "__main__":
    unittest.main()
