"""Fresh scorer-validation planning tests; no model or dialogue calls."""
import copy
import unittest

from app.factorial_study import digest
from app.g5.fresh_validation_plan import fresh_validation_plan, validate_fresh_validation_plan


class FreshValidationPlanTests(unittest.TestCase):
    def test_balanced_blinded_development_plan_is_not_factorial_evidence(self):
        plan = validate_fresh_validation_plan(fresh_validation_plan())
        self.assertEqual(len(plan["assignments"]), 8)
        self.assertEqual({arm: sum(row["arm"] == arm for row in plan["assignments"])
                          for arm in "ABCD"}, {arm: 2 for arm in "ABCD"})
        self.assertFalse(plan["blinding"]["scorer_sees_arm"])
        self.assertFalse(plan["analysis"]["architecture_effect_estimation"])
        self.assertIn("architecture_effect", plan["prohibited_inferences"])
        self.assertEqual(plan["analysis"]["expected_cases"], 48)

    def test_each_assignment_binds_world_and_its_own_role_table(self):
        plan = fresh_validation_plan()
        self.assertEqual(plan["role_inputs_index_sha256"],
                         digest(plan["scenario_role_inputs_sha256"]))
        for row in plan["assignments"]:
            self.assertEqual(row["role_inputs_sha256"],
                             plan["scenario_role_inputs_sha256"][row["scenario_id"]])

    def test_tamper_and_false_authority_are_rejected(self):
        for mutate in (
                lambda p: p["assignments"][0].update(arm="D"),
                lambda p: p["analysis"].update(architecture_effect_estimation=True),
                lambda p: p.update(launch_authorized=True)):
            changed = copy.deepcopy(fresh_validation_plan())
            mutate(changed)
            unsigned = {key: value for key, value in changed.items() if key != "sha256"}
            changed["sha256"] = digest(unsigned)
            with self.assertRaises(ValueError):
                validate_fresh_validation_plan(changed)


if __name__ == "__main__":
    unittest.main()
