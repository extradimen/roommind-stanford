"""Offline preflight controls: fixtures never authorize research."""
import copy
import unittest

import test_g5_annotation_archive as annotations
import test_g5_calibration_bridge as bridge
from test_g5_measurement import fixtures
from test_g5_family_registry import register, family, material, exposure
from app.factorial_study import digest, freeze_design
from app.g5.measurement import freeze_analysis
from app.g5.family_registry import FamilyRegistry
from app.g5.calibration_bridge import freeze_predictor, freeze_results
from app.g5.study_preflight import freeze_contract, inspect, require_local_contract


class PreflightTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await annotations.AnnotationTests.asyncSetUp(self)
        self.predictor = freeze_predictor({"id": "control", "kind": "synthetic", "spec_sha256": digest("script")})
        attempts = []
        for i, case in enumerate(self.frozen["plan"]["cases"]):
            label = "clear" if i // 6 % 2 else "violation"
            for who in (0, 1):
                self.archive.append(annotations.AnnotationTests.row(self, case["id"], who=who, label=label))
            attempts.append(bridge.BridgeTests.attempt(self, case["id"], label))
        self.annotation = self.archive.export()
        self.results = freeze_results(self.annotation, self.predictor, attempts)
        manifest, analysis, _, _ = fixtures(10)
        design = copy.deepcopy(manifest["design"])
        design["stage"] = "confirmation"
        for s in design["scenarios"]:
            s["snapshot_sha256"] = digest(["distinct-control", s["id"]])
        self.sample = {"family_count": 10, "repetitions": 1, "sampling_frame": "synthetic controls only",
                       "rationale": "Exercises consistency checks, not a real precision justification", "scope": "synthetic_control"}
        config = copy.deepcopy(analysis["config"]); config["sample_size_plan_sha256"] = digest(self.sample)
        analysis = freeze_analysis(config, version=2)
        design["analysis_plan_sha256"] = analysis["sha256"]
        design["sample_size_plan_sha256"] = digest(self.sample)
        for arm in design["arms"].values(): arm["shared"]["evaluator_plan_sha256"] = analysis["sha256"]
        self.study = freeze_design(design); self.analysis = analysis
        self.registry = FamilyRegistry(":memory:", "preflight-control"); self.addCleanup(self.registry.close)
        register(self.registry, self.study); register(self.registry, self.annotation["manifest"])
        self.registry.append(exposure(self.annotation["manifest"]["design"]["scenarios"][0]["family"]))
        self.frozen_registry = self.registry.export()
        self.criteria = {"annotation_plan_sha256": self.frozen["sha256"], "prediction_plan_sha256": self.predictor["sha256"],
                         "minimum_references_per_label_per_dimension": 2, "minimum_decisive_coverage": 1,
                         "maximum_binary_error_bound": 0}
        self.contract = freeze_contract(self.study, self.analysis, self.frozen_registry, self.sample, self.criteria)

    def report(self, **kwargs):
        return inspect(self.contract, self.frozen_registry, self.registry.export(),
                       annotation=self.annotation, results=kwargs.get("results", self.results))

    async def test_complete_control_passes_only_local_checks_and_is_replayable(self):
        result = require_local_contract(self.contract, self.frozen_registry, self.registry.export(),
                                       annotation=self.annotation, results=self.results)
        self.assertTrue(result["local_contract_checks_passed"])
        self.assertFalse(result["launch_authorized"])
        self.assertIn("scoring_judge_validation", result["unverified_research_gates"])
        self.assertEqual(result, self.report())

    async def test_missing_partial_and_wrong_predictions_block_without_changing_history(self):
        before = self.registry.export()
        missing = inspect(self.contract, self.frozen_registry, before)
        self.assertIn("calibration_present", missing["blocking_checks"])
        partial = freeze_results(self.annotation, self.predictor, [])
        self.assertFalse(self.report(results=partial)["local_contract_checks_passed"])
        wrong = [bridge.BridgeTests.attempt(self, c["id"], "clear") for c in self.frozen["plan"]["cases"]]
        result = self.report(results=freeze_results(self.annotation, self.predictor, wrong))
        self.assertTrue(any(k.endswith(":violation") for k in result["blocking_checks"]))
        with self.assertRaises(ValueError): require_local_contract(self.contract, self.frozen_registry, before)
        self.assertEqual(before, self.registry.export())

    async def test_late_exposure_and_exact_alias_block_even_after_refreeze(self):
        self.registry.append(exposure("f-0"))
        self.assertIn("registry_snapshot_current", self.report()["blocking_checks"])
        self.frozen_registry = self.registry.export()
        self.contract = freeze_contract(self.study, self.analysis, self.frozen_registry, self.sample, self.criteria)
        self.assertIn("registered_holdout_unexposed", self.report()["blocking_checks"])
        event = material("f-1", self.study["design"]["scenarios"][0]["snapshot_sha256"])
        event["id"] = "late-alias"; self.registry.append(event)
        self.assertIn("independent_declared_family_units", self.report()["blocking_checks"])

    async def test_full_rehash_cannot_substitute_plan_or_calibration_evidence(self):
        bad = copy.deepcopy(self.contract); bad["analysis"]["config"]["alpha"] = .1
        bad["sha256"] = digest({k:v for k,v in bad.items() if k != "sha256"})
        with self.assertRaises(ValueError): inspect(bad, self.frozen_registry, self.registry.export())
        bad_results = copy.deepcopy(self.results); bad_results["attempts"][0]["artifact"]["task"]["rubric"] = "tampered"
        bad_results["sha256"] = digest({k:v for k,v in bad_results.items() if k != "sha256"})
        with self.assertRaises(ValueError): self.report(results=bad_results)
        criteria = {**self.criteria, "prediction_plan_sha256": digest("other")}
        self.contract = freeze_contract(self.study, self.analysis, self.frozen_registry, self.sample, criteria)
        self.assertIn("predictor_plan_bound", self.report()["blocking_checks"])

    async def test_sample_counts_missing_material_and_used_calibration_family_block(self):
        design = copy.deepcopy(self.study["design"])
        design["scenarios"][0] = copy.deepcopy(self.annotation["manifest"]["design"]["scenarios"][0])
        self.study = freeze_design(design)
        self.contract = freeze_contract(self.study, self.analysis, self.frozen_registry, self.sample, self.criteria)
        self.assertIn("calibration_holdout_disjoint", self.report()["blocking_checks"])
        design["scenarios"][0]["snapshot_sha256"] = digest("unregistered")
        self.contract = freeze_contract(freeze_design(design), self.analysis, self.frozen_registry, self.sample, self.criteria)
        self.assertIn("scenario_materials_registered", self.report()["blocking_checks"])
        design["repetitions"] = 2
        self.contract = freeze_contract(freeze_design(design), self.analysis, self.frozen_registry, self.sample, self.criteria)
        self.assertIn("sample_counts_match", self.report()["blocking_checks"])

    async def test_null_actual_parameters_and_invalid_thresholds_cannot_freeze(self):
        for value in (None, True, 0):
            with self.assertRaises(ValueError): freeze_contract(self.study, self.analysis, self.frozen_registry,
                {**self.sample, "family_count": value}, self.criteria)
        for value in (None, True, float("nan"), -1, 2):
            with self.assertRaises(ValueError): freeze_contract(self.study, self.analysis, self.frozen_registry,
                self.sample, {**self.criteria, "maximum_binary_error_bound": value})

    async def test_declared_used_parent_blocks_without_an_exposure_event(self):
        self.registry.append(family("parent"))
        self.registry.append(family("child", ["parent"]))
        self.registry.append(material("child", digest("new-child")))
        design = copy.deepcopy(self.study["design"])
        design["scenarios"][0] = {"id": "child-scenario", "family": "child", "snapshot_sha256": digest("new-child")}
        design["used_families"] = ["parent"]
        self.frozen_registry = self.registry.export()
        self.contract = freeze_contract(freeze_design(design), self.analysis, self.frozen_registry, self.sample, self.criteria)
        self.assertIn("declared_used_lineage_disjoint", self.report()["blocking_checks"])


if __name__ == "__main__":
    import argparse
    import asyncio
    import json
    import os
    from pathlib import Path
    from app.g5.world import canonical
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    async def save():
        case = PreflightTests()
        try:
            await case.asyncSetUp()
            passing = case.report()
            case.registry.append(exposure("f-0"))
            blocked = case.report()
            raw = {"schema": "g5-synthetic-preflight-controls-v1", "contract": case.contract,
                "frozen_registry": case.frozen_registry, "current_registry": case.registry.export(),
                "annotation": case.annotation, "results": case.results, "before": passing, "after": blocked,
                "real_model_calls": 0, "human_annotations": 0, "launch_authorized": False}
            raw["sha256"] = digest(raw)
            directory = Path(args.output_dir); directory.mkdir(mode=0o700, exist_ok=False)
            with os.fdopen(os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                stream.write(canonical(raw)); stream.flush(); os.fsync(stream.fileno())
            print(json.dumps({"sha256": raw["sha256"], "before_checks": passing["local_contract_checks_passed"],
                              "after_blockers": blocked["blocking_checks"]}))
        finally:
            case.doCleanups()
    asyncio.run(save())
