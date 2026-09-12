import unittest
from app.g5.coverage_diagnostics import rare_family_stress
from app.g5.measurement import DIMENSIONS, family_bootstrap_interval, bounded_family_interval, freeze_analysis, report


class CoverageDiagnosticsTests(unittest.TestCase):
    def test_unobserved_rare_family_is_a_counterexample_not_a_pass(self):
        result = rare_family_stress(trials=2, families=10, resamples=14400, seed=119)
        self.assertTrue(result["counterexample_below_nominal"])
        self.assertLess(result["exact_coverage_upper_bound"], .5)
        self.assertEqual(result["qualification"], "not_inferred")
        config = {"minimum_families": 10, "resamples": 14400, "alpha": .05, "seed": 119}
        self.assertEqual(family_bootstrap_interval([0] * 10, config, DIMENSIONS[0], "C"), [0, 0])
        self.assertGreater(result["true_effect"], 0)
        self.assertEqual(result["bounded_empirical_coverage"], 1)
        self.assertEqual(result, rare_family_stress(trials=2, families=10, resamples=14400, seed=119))

    def test_invalid_simulation_does_not_bypass_production_tail_gate(self):
        with self.assertRaises(ValueError):
            rare_family_stress(trials=1, families=10, resamples=100, seed=1)
        with self.assertRaises(ValueError):
            rare_family_stress(trials=0, families=10, resamples=20000, seed=1)

    def test_conservative_option_requires_new_frozen_plan_and_does_not_infer_precision(self):
        from test_g5_measurement import fixtures
        from app.factorial_study import freeze_design
        manifest, old, transcripts, attempts = fixtures()
        config = {**old["config"], "interval_method": "bounded-family-hoeffding-v1"}
        plan = freeze_analysis(config)
        self.assertNotEqual(plan["sha256"], old["sha256"])
        with self.assertRaises(ValueError):
            report(manifest, plan, transcripts, attempts)
        design = manifest["design"]
        design["analysis_plan_sha256"] = plan["sha256"]
        for arm in design["arms"].values():
            arm["shared"]["evaluator_plan_sha256"] = plan["sha256"]
        from app.g5.measurement import freeze_transcript
        manifest = freeze_design(design)
        transcripts = [freeze_transcript(manifest, t["ordinal"], t["turns"]) for t in transcripts]
        for attempt in attempts:
            attempt["transcript_sha256"] = transcripts[attempt["ordinal"] - 1]["sha256"]
        result = report(manifest, plan, transcripts, attempts)
        for row in result["dimensions"].values():
            interval = row["contrasts"]["C"]["interval"]
            self.assertLess(interval[0], 0)
            self.assertGreater(interval[1], 0)
            self.assertIn("hoeffding", row["contrasts"]["C"]["interval_status"])
        self.assertEqual(result["qualification"], "not_inferred")
        self.assertEqual(bounded_family_interval([0] * 10, .05, "interaction"), [-8, 8])
        with self.assertRaises(ValueError):
            bounded_family_interval([9] * 10, .05, "interaction")
