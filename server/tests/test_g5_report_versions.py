"""Versioned metadata and unresolved-denominator accounting; synthetic only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import test_g5_evaluation as evaluation_fixtures
import test_g5_calibration_bridge as bridge_fixtures
from test_g5_measurement import fixtures
from app.factorial_study import ARMS, digest, freeze_design
from app.g5.calibration_bridge import freeze_results, report as legacy_calibration
from app.g5.calibration_bounds import report as calibration_report
from app.g5.evaluation_archive import EvaluationArchive
from app.g5.measurement import DIMENSIONS, freeze_analysis, verify_analysis, freeze_transcript, report
from app.g5.release import evidence_bundle, verify_evidence


def bind(design, plan):
    design = copy.deepcopy(design)
    design["analysis_plan_sha256"] = plan["sha256"]
    for arm in design["arms"].values():
        arm["shared"]["evaluator_plan_sha256"] = plan["sha256"]
    return freeze_design(design)


class MetadataTests(unittest.TestCase):
    def test_v1_hash_unchanged_and_v2_explicit_method_and_unused_resamples(self):
        config = fixtures(1)[1]["config"]
        self.assertEqual(freeze_analysis(config)["sha256"], "a1dfcc3fa4c717dbebe5b8821d70dd2994d9fca713af7dd00693cf11bcfc07ae")
        for method in ("family-percentile-bootstrap-v1", "bounded-family-hoeffding-v1"):
            config["interval_method"] = method
            old, new = freeze_analysis(config), freeze_analysis(config, version=2)
            self.assertEqual(old["interval"], "family-percentile-bootstrap")
            self.assertEqual(new["interval"], method)
            self.assertEqual(new["resamples_role"], "used" if "bootstrap" in method else "unused-retained-config-field")
            self.assertNotEqual(old["sha256"], new["sha256"])
            verify_analysis(old); verify_analysis(new)
            changed = copy.deepcopy(new)
            changed["interval"] = "wrong"
            changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
            with self.assertRaises(ValueError): verify_analysis(changed)
        for version in (True, "2", 0, 3):
            with self.assertRaises(ValueError): freeze_analysis(config, version=version)

    def test_v2_report_numeric_parity_and_old_manifest_cannot_use_new_plan(self):
        manifest, plan, transcripts, attempts = fixtures(10)
        config = copy.deepcopy(plan["config"])
        config["interval_method"] = "bounded-family-hoeffding-v1"
        results = []
        for version in (1, 2):
            frozen_plan = freeze_analysis(config, version=version)
            frozen = bind(manifest["design"], frozen_plan)
            tx = [freeze_transcript(frozen, t["ordinal"], t["turns"]) for t in transcripts]
            hashes = {t["ordinal"]: t["sha256"] for t in tx}
            rows = copy.deepcopy(attempts)
            for row in rows: row["transcript_sha256"] = hashes[row["ordinal"]]
            results.append(report(frozen, frozen_plan, tx, rows))
        self.assertEqual(results[0]["dimensions"], results[1]["dimensions"])
        self.assertEqual(results[1]["interval_method"], config["interval_method"])
        for dim in results[1]["dimensions"].values():
            for contrast in dim["contrasts"].values():
                self.assertEqual(contrast["interval_status"], "bounded-independent-family-hoeffding-bonferroni-18")
        with self.assertRaises(ValueError):
            report(manifest, freeze_analysis(plan["config"], version=2), transcripts, attempts)


class CalibrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await bridge_fixtures.BridgeTests.asyncSetUp(self)

    def attempt(self, *args, **kwargs):
        return bridge_fixtures.BridgeTests.attempt(self, *args, **kwargs)

    async def test_mixed_bound_denominators_and_strata_reconcile(self):
        results = freeze_results(self.annotation, self.predictor, bridge_fixtures.BridgeTests.mixed_attempts(self))
        old = legacy_calibration(self.annotation, results)
        new = calibration_report(self.annotation, results)
        self.assertEqual(new["legacy_report_sha256"], old["sha256"])
        self.assertEqual(new["cases"], old["cases"])
        for key, value in old["overall"].items(): self.assertEqual(new["overall"][key], value)
        for label, error_label in (("clear", "violation"), ("violation", "clear")):
            subset = [c for c in new["cases"] if c["reference_label"] == label]
            row = new["overall"]["reference_strata"][label]
            n = len(subset)
            errors = sum(c["prediction"] == error_label for c in subset)
            m = sum(c["prediction"] not in ("clear", "violation") for c in subset)
            self.assertEqual(row["possible_binary_error_fraction_bounds"], [errors / n, (errors + m) / n])
            self.assertEqual(row["decisive_predictions"] + row["unresolved_predictions"], n)
            for axis in new["strata"].values():
                self.assertEqual(sum(s["reference_strata"][label]["reference_total"] for s in axis.values()), n)
        self.assertEqual(sum(r["reference_total"] for r in new["overall"]["reference_strata"].values()), 19)
        self.assertEqual(new["overall"]["total_cases"], 24)

    async def test_all_unknown_bounds_are_unit_interval_empty_reference_is_null(self):
        empty = freeze_results(self.annotation, self.predictor, [])
        value = calibration_report(self.annotation, empty)
        for row in value["overall"]["reference_strata"].values():
            self.assertEqual(row["possible_binary_error_fraction_bounds"], [0, 1])
            self.assertIsNone(row["error_fraction_decisive"])
        # Each dimension has sparse known truth; zero-denominator strata stay null.
        zero = [row for axis in value["strata"].values() for level in axis.values()
                for row in level["reference_strata"].values() if row["reference_total"] == 0]
        self.assertTrue(zero)
        self.assertTrue(all(r["possible_binary_error_fraction_bounds"] is None for r in zero))

    async def test_complete_predictions_collapse_bounds_and_rehashed_tamper_rejected(self):
        rows = [self.attempt(c["id"], "clear") for c in self.frozen["plan"]["cases"]]
        results = freeze_results(self.annotation, self.predictor, rows)
        value = calibration_report(self.annotation, results)
        self.assertEqual(value["overall"]["reference_strata"]["clear"]["possible_binary_error_fraction_bounds"], [0, 0])
        self.assertEqual(value["overall"]["reference_strata"]["violation"]["possible_binary_error_fraction_bounds"], [1, 1])
        broken = copy.deepcopy(results)
        broken["attempts"][0]["artifact"]["task"]["rubric"] = "changed"
        broken["sha256"] = digest({k: v for k, v in broken.items() if k != "sha256"})
        with self.assertRaises(ValueError): calibration_report(self.annotation, broken)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await evaluation_fixtures.EvaluationTests.asyncSetUp(self)
        config = copy.deepcopy(self.plan["config"])
        config["interval_method"] = "bounded-family-hoeffding-v1"
        self.plan = freeze_analysis(config, version=2)
        self.manifest = bind(self.manifest["design"], self.plan)
        self.harness.frozen = self.manifest

    async def test_v2_four_arm_evaluation_reconnect_and_release_with_failed_history(self):
        packets = [await evaluation_fixtures.EvaluationTests.packet(self, arm) for arm in ARMS]
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "evaluation.sqlite")
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            self.mode = "timeout"
            failed = await self.evaluator.evaluate(self.manifest, self.plan, packets[0], DIMENSIONS[0], attempt_id="failure")
            archive.append(failed)
            archive.close()
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            self.mode = "ok"
            try:
                previous = [r["attempt"] for r in archive.export()["results"]]
                async for result in self.evaluator.missing_evaluations(self.manifest, self.plan, packets, previous):
                    archive.append(result)
                exported = archive.export()
                self.assertEqual(len(exported["results"]), 25)
                sources = [self.world.export_source(arm) for arm in ARMS]
                bundle = evidence_bundle(sources, exported)
                self.assertTrue(verify_evidence(bundle)["evaluation_terminal"])
                summary = report(self.manifest, self.plan, [p["transcript"] for p in packets], [r["attempt"] for r in exported["results"]])
                self.assertEqual(summary["schema"], "g5-six-dimension-report-v2")
                self.assertEqual(summary["technical_failure_attempts"], 1)
                self.assertEqual(summary["interval_method"], self.plan["interval"])
                self.bundle, self.summary = bundle, summary
            finally:
                archive.close()


if __name__ == "__main__":
    import argparse, asyncio, hashlib, os
    from app.g5.world import canonical
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    async def audit():
        case = AdapterTests()
        try:
            await case.asyncSetUp()
            await case.test_v2_four_arm_evaluation_reconnect_and_release_with_failed_history()
            paths = [Path("research/experiments/2026-09-12-g5-local-calibration-bridge/panel.json"),
                     Path("research/experiments/2026-09-11-g5-local-evaluation-controls/panel.json")]
            original, control = [json.loads(path.read_text()) for path in paths]
            old_report = legacy_calibration(original["annotation"], original["results"])
            if old_report != original["report"] or freeze_analysis(control["plan"]["config"]) != control["plan"]:
                raise ValueError("Preserved v1 artifacts no longer reproduce")
            raw = {"schema": "g5-report-contract-audit-v1", "real_model_calls": 0,
                "legacy_input_files": [{"path": str(path), "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths],
                "legacy_analysis_sha256": control["plan"]["sha256"], "legacy_calibration_sha256": old_report["sha256"],
                "legacy_reproduces": True,
                "calibration_annotation": original["annotation"], "calibration_results": original["results"],
                "calibration_report_v2": calibration_report(original["annotation"], original["results"]),
                "new_v2_synthetic_evaluation": case.bundle, "evaluation_report_v2": case.summary,
                "qualification": "not_inferred"}
            raw["sha256"] = digest(raw)
            directory = Path(args.output_dir)
            directory.mkdir(mode=0o700, exist_ok=False)
            with os.fdopen(os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                stream.write(canonical(raw)); stream.flush(); os.fsync(stream.fileno())
            print(json.dumps({"sha256": raw["sha256"], "legacy_reproduces": True,
                "reference_strata": raw["calibration_report_v2"]["overall"]["reference_strata"]}))
        finally:
            case.doCleanups()
    asyncio.run(audit())
