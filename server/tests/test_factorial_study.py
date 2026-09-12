import copy
import unittest
from collections import Counter

from app.factorial_study import (
    ARMS, PROTOCOL, SHARED_FIELDS, assignments, digest, freeze_design,
    validate_design, verify_manifest,
)


def fixture():
    return {
        "protocol": PROTOCOL, "source_revision": "a" * 40, "stage": "exploration",
        "scenarios": [{"id": "incident-v1", "family": "incident", "snapshot_sha256": "b" * 64},
                      {"id": "meeting-v1", "family": "meeting", "snapshot_sha256": "c" * 64}],
        "used_families": [], "repetitions": 2, "order_seed": 20260910,
        "sampling_seed_policy": "unsupported_recorded",
        "analysis_plan_sha256": "d" * 64, "sample_size_plan_sha256": "e" * 64,
        "arms": {name: {**switches, "shared": {key: digest(key) for key in SHARED_FIELDS}}
                 for name, switches in ARMS.items()},
    }


class FactorialDesignTests(unittest.TestCase):
    def test_four_complete_independent_blocks(self):
        design = fixture()
        rows = assignments(design)
        self.assertEqual(len(rows), 16)
        counts = Counter((r["scenario_id"], r["repetition"], r["arm"]) for r in rows)
        self.assertEqual(set(counts.values()), {1})
        for block in {r["block_id"] for r in rows}:
            self.assertEqual({r["arm"] for r in rows if r["block_id"] == block}, set(ARMS))
        self.assertEqual(assignments(design), rows)
        design["scenarios"].reverse()
        self.assertEqual(assignments(design), rows)

    def test_order_seed_changes_order_not_conditions(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["order_seed"] += 1
        first, second = assignments(a), assignments(b)
        self.assertNotEqual(first, second)
        key = lambda row: (row["scenario_id"], row["repetition"], row["arm"])
        self.assertEqual(sorted(map(key, first)), sorted(map(key, second)))

    def test_frozen_copy_and_hash(self):
        design = fixture()
        manifest = freeze_design(design)
        verify_manifest(manifest)
        design["arms"]["D"]["shared"]["world_sha256"] = "f" * 64
        verify_manifest(manifest)
        manifest["assignments"][0]["arm"] = "other"
        with self.assertRaises(ValueError):
            verify_manifest(manifest)

    def test_rehashing_missing_or_duplicated_arm_does_not_hide_corruption(self):
        for mutation in ("drop", "duplicate"):
            with self.subTest(mutation=mutation):
                manifest = freeze_design(fixture())
                if mutation == "drop":
                    manifest["assignments"].pop()
                else:
                    manifest["assignments"][1] = copy.deepcopy(manifest["assignments"][0])
                manifest["expected_dialogues"] = len(manifest["assignments"])
                manifest["manifest_sha256"] = digest({k: v for k, v in manifest.items()
                                                      if k != "manifest_sha256"})
                with self.assertRaises(ValueError):
                    verify_manifest(manifest)

    def test_every_shared_factor_must_match(self):
        for field in SHARED_FIELDS:
            with self.subTest(field=field):
                design = fixture()
                design["arms"]["B"]["shared"][field] = "f" * 64
                with self.assertRaisesRegex(ValueError, "Non-factor difference"):
                    validate_design(design)

    def test_family_holdout_not_just_new_scenario_or_seed(self):
        for stage in ("screening", "confirmation"):
            design = fixture()
            design["stage"] = stage
            design["used_families"] = ["incident"]
            design["scenarios"][0]["id"] = "new-wording-new-seed"
            with self.assertRaisesRegex(ValueError, "previously exposed"):
                validate_design(design)
            design["used_families"] = ["unrelated-family"]
            validate_design(design)

    def test_exploration_can_use_history_but_cannot_relabel_evidence(self):
        design = fixture()
        design["used_families"] = ["incident"]
        manifest = freeze_design(design)
        self.assertEqual(manifest["evidence_use"], "development_only")
        manifest["evidence_use"] = "held_out_confirmatory_evidence"
        with self.assertRaises(ValueError):
            verify_manifest(manifest)

    def test_invalid_designs_fail_closed(self):
        mutations = [
            lambda d: d["arms"].pop("A"),
            lambda d: d["arms"]["A"].update(cognition=True),
            lambda d: d["arms"]["B"].update(cognition=1),
            lambda d: d["arms"]["A"].update(extra_prompt="secret help"),
            lambda d: d.update(stage="confirm-ish"),
            lambda d: d.update(repetitions=True),
            lambda d: d.update(order_seed=1.5),
            lambda d: d.update(source_revision="unrecorded"),
            lambda d: d.update(analysis_plan_sha256=""),
            lambda d: d.update(analysis_plan_sha256=int("1" * 64)),
            lambda d: d.update(sample_size_plan_sha256=""),
            lambda d: d.update(sampling_seed_policy="same_as_order_seed"),
            lambda d: d.update(scenarios=[]),
            lambda d: d["scenarios"][0].update(family="incident "),
            lambda d: d["scenarios"].append(copy.deepcopy(d["scenarios"][0])),
            lambda d: d.update(unknown_runtime_override=True),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                design = fixture()
                mutate(design)
                with self.assertRaises(ValueError):
                    validate_design(design)

    def test_numerically_equal_type_change_is_not_a_valid_frozen_manifest(self):
        for rehash in (False, True):
            manifest = freeze_design(fixture())
            manifest["expected_dialogues"] = float(manifest["expected_dialogues"])
            if rehash:
                manifest["manifest_sha256"] = digest({k: v for k, v in manifest.items()
                                                      if k != "manifest_sha256"})
            with self.assertRaises(ValueError):
                verify_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
