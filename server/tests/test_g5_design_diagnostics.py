"""Estimand, repeat, missingness and sampling-target controls."""
import copy
import itertools
import unittest
from statistics import mean
import tempfile
from pathlib import Path

import test_g5_evaluation as evaluation_fixtures
import test_g5_study_preflight as preflight_fixtures

from test_g5_measurement import fixtures
from app.factorial_study import digest, freeze_design
from app.g5.measurement import DIMENSIONS, WEIGHTS, freeze_analysis, verify_analysis, freeze_transcript, report
from app.g5.design_diagnostics import correlated_family_stress
from app.g5.evaluation_archive import EvaluationArchive
from app.g5.release import evidence_bundle, verify_evidence
from app.g5.study_preflight import freeze_contract


def panel(kind="independent-family-population", repetitions=1):
    old, prior, _, _ = fixtures(10)
    config = {**prior["config"], "interval_method": "bounded-family-hoeffding-v1"}
    plan = freeze_analysis(config, version=3, sampling_target={"kind": kind, "frame_sha256": digest("synthetic frame")})
    design = copy.deepcopy(old["design"])
    scenarios = []
    for i, s in enumerate(design["scenarios"]):
        scenarios += [{**s, "id": s["id"] + "-" + str(j)} for j in range(3 if i % 2 else 1)]
    design["scenarios"] = scenarios; design["repetitions"] = repetitions
    design["analysis_plan_sha256"] = plan["sha256"]
    for arm in design["arms"].values(): arm["shared"]["evaluator_plan_sha256"] = plan["sha256"]
    manifest = freeze_design(design)
    transcripts, attempts = [], []
    for a in manifest["assignments"]:
        tx = freeze_transcript(manifest, a["ordinal"], [{"id": "t1", "actor": "sre", "text": "Synthetic fixture."}])
        transcripts.append(tx)
        values = {"A": 4, "B": 2, "C": 3, "D": 1} if int(a["family"].split("-")[1]) % 2 else {"A": 1, "B": 2, "C": 3, "D": 5}
        for d in DIMENSIONS:
            attempts.append({"id": f'{a["ordinal"]}-{d}', "ordinal": a["ordinal"], "dimension": d,
                "judge": plan["config"]["judge"], "transcript_sha256": tx["sha256"], "status": "completed",
                "score": values[a["arm"]], "quotes": [{"turn_id": "t1", "start": 0, "end": 18, "text": "Synthetic fixture."}],
                "rationale": "Numeric design control", "artifact_sha256": digest([a["ordinal"], d])})
    return manifest, plan, transcripts, attempts


def oracle(manifest, attempts, dimension, effect):
    scores = {a["ordinal"]: a["score"] for a in attempts if a["dimension"] == dimension}
    blocks = {}
    for a in manifest["assignments"]:
        blocks.setdefault((a["family"], a["block_id"]), {})[a["arm"]] = scores[a["ordinal"]]
    family_values = {}
    for (f, _), arms in blocks.items():
        family_values.setdefault(f, []).append(sum(w * arms[a] for a,w in WEIGHTS[effect].items()))
    return mean(mean(v) for v in family_values.values())


class DesignTests(unittest.TestCase):
    def test_family_weighting_and_perfectly_correlated_repeats_do_not_inflate_precision(self):
        first = panel(); second = panel(repetitions=3)
        a, b = report(*first), report(*second)
        expected = {"C": -.25, "G": .75, "interaction": .5}
        for d in DIMENSIONS:
            for e in WEIGHTS:
                x, y = a["dimensions"][d]["contrasts"][e], b["dimensions"][d]["contrasts"][e]
                self.assertEqual(x["estimate"], expected[e])
                self.assertEqual(x["estimate"], oracle(first[0], first[3], d, e))
                for key in ("estimate", "interval", "families"):
                    self.assertEqual(x[key], y[key])
        self.assertNotEqual(a["assigned_dialogues"], b["assigned_dialogues"])

    def test_fixed_benchmark_does_not_claim_population_or_future_run_uncertainty(self):
        source = panel("fixed-family-benchmark")
        result = report(*source)
        self.assertEqual(result["interval_method"], "none-fixed-benchmark-descriptive")
        for d in result["dimensions"].values():
            for row in d["contrasts"].values():
                self.assertIsNotNone(row["estimate"])
                self.assertIsNone(row["interval"])
                self.assertEqual(row["interval_status"], "fixed-benchmark-descriptive-no-population-interval")
        self.assertFalse(result["sampling_assumptions_verified"])

    def test_missing_scores_bounds_equal_exhaustive_completions_not_complete_case_mean(self):
        manifest, plan, tx, original = panel()
        rows = copy.deepcopy(original)
        targets = [0, 6]
        for i in targets:
            rows[i].update(status="technical_failure", score=None, quotes=[])
        result = report(manifest, plan, tx, rows)
        dimension = DIMENSIONS[0]
        for e in WEIGHTS:
            values = []
            for replacements in itertools.product((1, 5), repeat=2):
                completed = copy.deepcopy(original)
                for i,v in zip(targets, replacements): completed[i]["score"] = v
                values.append(oracle(manifest, completed, dimension, e))
            row = result["dimensions"][dimension]["contrasts"][e]
            self.assertEqual(row["missing_score_bounds"], [min(values), max(values)])
            self.assertIsNone(row["estimate"]); self.assertIsNone(row["interval"])
            self.assertLessEqual(min(values), oracle(manifest, original, dimension, e))
            self.assertGreaterEqual(max(values), oracle(manifest, original, dimension, e))

    def test_nonapplicable_retains_denominator_without_fabricating_a_bounded_score(self):
        manifest, plan, tx, rows = panel()
        rows[0].update(status="not_applicable", score=None, quotes=[])
        result = report(manifest, plan, tx, rows)
        d = result["dimensions"][DIMENSIONS[0]]
        self.assertEqual(d["denominators"]["not_applicable"], 1)
        self.assertEqual(sum(d["denominators"].values()), manifest["expected_dialogues"])
        for row in d["contrasts"].values():
            self.assertIsNone(row["missing_score_bounds"])
            self.assertEqual(row["interval_status"], "not-applicable-estimand-undefined")

    def test_target_requires_new_hash_and_cannot_be_inserted_into_old_plan(self):
        manifest, old, tx, rows = fixtures(10)
        for version in (1, 2):
            with self.assertRaises(ValueError): freeze_analysis(old["config"], version=version,
                sampling_target={"kind": "fixed-family-benchmark", "frame_sha256": digest("frame")})
        with self.assertRaises(ValueError): freeze_analysis(old["config"], version=3)
        new = freeze_analysis(old["config"], version=3,
            sampling_target={"kind": "fixed-family-benchmark", "frame_sha256": digest("frame")})
        verify_analysis(new)
        with self.assertRaises(ValueError): report(manifest, new, tx, rows)
        bad = copy.deepcopy(new); bad["sampling_target"]["kind"] = "independent-family-population"
        bad["sha256"] = digest({k:v for k,v in bad.items() if k != "sha256"})
        with self.assertRaises(ValueError): verify_analysis(bad)

    def test_joint_stress_and_exact_shared_family_counterexample(self):
        value = correlated_family_stress(trials=3, families=100, seed=73)
        self.assertEqual(value, correlated_family_stress(trials=3, families=100, seed=73))
        self.assertEqual(value["invalid_shared_sign_exact_coverage"], 0)
        self.assertFalse(value["launch_authorized"])
        for row in value["trials"]:
            self.assertEqual(len(row["intervals"]), 6)
            self.assertTrue(all(len(e) == 3 for e in row["intervals"].values()))


class IntegratedTargetTests(unittest.IsolatedAsyncioTestCase):
    async def test_v3_evaluator_archive_reconnect_and_full_source_release(self):
        await evaluation_fixtures.EvaluationTests.asyncSetUp(self)
        self.plan = freeze_analysis(self.plan["config"], version=3,
            sampling_target={"kind": "fixed-family-benchmark", "frame_sha256": digest("fixture")})
        design = copy.deepcopy(self.manifest["design"])
        design["analysis_plan_sha256"] = self.plan["sha256"]
        for arm in design["arms"].values(): arm["shared"]["evaluator_plan_sha256"] = self.plan["sha256"]
        self.manifest = freeze_design(design); self.harness.frozen = self.manifest
        packets = [await evaluation_fixtures.EvaluationTests.packet(self, arm) for arm in ("A", "B", "C", "D")]
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "evaluation.sqlite")
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            async for item in self.evaluator.missing_evaluations(self.manifest, self.plan, packets, []): archive.append(item)
            old = archive.export(); archive.close()
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            try:
                self.assertEqual(old, archive.export())
                bundle = evidence_bundle([self.world.export_source(a) for a in ("A", "B", "C", "D")], archive.export())
                self.assertTrue(verify_evidence(bundle)["evaluation_terminal"])
            finally:
                archive.close()

    async def test_v3_preflight_binds_target_frame(self):
        await preflight_fixtures.PreflightTests.asyncSetUp(self)
        for frame, expected in ((digest(self.sample["sampling_frame"]), True), (digest("wrong-frame"), False)):
            self.analysis = freeze_analysis(self.analysis["config"], version=3,
                sampling_target={"kind": "fixed-family-benchmark", "frame_sha256": frame})
            design = copy.deepcopy(self.study["design"]); design["analysis_plan_sha256"] = self.analysis["sha256"]
            for arm in design["arms"].values(): arm["shared"]["evaluator_plan_sha256"] = self.analysis["sha256"]
            self.study = freeze_design(design)
            self.contract = freeze_contract(self.study, self.analysis, self.frozen_registry, self.sample, self.criteria)
            value = preflight_fixtures.PreflightTests.report(self)
            self.assertEqual(value["checks"]["sampling_frame_bound"], expected)


if __name__ == "__main__":
    import argparse
    import hashlib
    import json
    import os
    from pathlib import Path
    from app.g5.world import canonical
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    old_path = Path("docs/G5_SYNTHETIC_COVERAGE_BOUND_COMPARISON_20260911.json")
    old_bytes = old_path.read_bytes(); old = json.loads(old_bytes)
    if digest({k:v for k,v in old.items() if k != "sha256"}) != old["sha256"]: raise ValueError("Legacy diagnostic changed")
    sampled, fixed = panel(), panel("fixed-family-benchmark")
    incomplete = copy.deepcopy(sampled)
    incomplete[3][0].update(status="technical_failure", score=None, quotes=[])
    na = copy.deepcopy(sampled); na[3][0].update(status="not_applicable", score=None, quotes=[])
    raw = {"schema": "g5-design-analysis-audit-v1", "classification": "synthetic-only",
        "legacy_input": {"path": str(old_path), "file_sha256": hashlib.sha256(old_bytes).hexdigest(),
                         "content_sha256": old["sha256"], "empirical_coverage": old["empirical_coverage"],
                         "exact_coverage_upper_bound": old["exact_coverage_upper_bound"]},
        "panels": {k: {"manifest": p[0], "plan": p[1], "transcripts": p[2], "attempts": p[3], "report": report(*p)}
                   for k,p in (("sampled", sampled), ("fixed", fixed), ("incomplete", incomplete), ("nonapplicable", na))},
        "joint_stress": correlated_family_stress(trials=100, families=100, seed=20260912),
        "real_model_calls": 0, "launch_authorized": False}
    raw["sha256"] = digest(raw)
    directory = Path(args.output_dir); directory.mkdir(mode=0o700, exist_ok=False)
    with os.fdopen(os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(canonical(raw)); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"sha256": raw["sha256"], "joint_coverage": raw["joint_stress"]["empirical_joint_18_coverage"],
                      "invalid_independence_coverage": raw["joint_stress"]["invalid_shared_sign_exact_coverage"]}))
