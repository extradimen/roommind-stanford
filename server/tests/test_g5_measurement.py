import copy
import unittest

from app.factorial_study import digest, freeze_design
from app.g5.measurement import DIMENSIONS, freeze_analysis, freeze_transcript, freeze_labels, report
from test_g5_runtime import manifest


def fixtures(families=10):
    judge = {"id": "synthetic-judge", "kind": "synthetic", "spec_sha256": digest("offline-only")}
    plan = freeze_analysis({"alpha": .05, "resamples": 20000, "seed": 73, "minimum_families": 10,
        "meaningful_differences": {d: .3 for d in DIMENSIONS}, "judge": judge,
        "rubric_sha256": digest("synthetic-rubric"), "sample_size_plan_sha256": digest("not-a-real-power-plan")})
    design = manifest()["design"]
    scenario = design["scenarios"][0]
    design["scenarios"] = [{**scenario, "id": f"s-{n}", "family": f"f-{n}"} for n in range(families)]
    design["repetitions"] = 1
    design["analysis_plan_sha256"] = plan["sha256"]
    design["sample_size_plan_sha256"] = plan["config"]["sample_size_plan_sha256"]
    for arm in design["arms"].values():
        arm["shared"]["evaluator_plan_sha256"] = plan["sha256"]
    frozen = freeze_design(design)
    transcripts, attempts = [], []
    text = "I cannot confirm yet; let us wait for evidence."
    for assignment in frozen["assignments"]:
        ordinal = assignment["ordinal"]
        tx = freeze_transcript(frozen, ordinal, [{"id": "t1", "actor": "sre", "text": text}])
        transcripts.append(tx)
        for dimension in DIMENSIONS:
            attempts.append({"id": f"{ordinal}-{dimension}", "ordinal": ordinal, "dimension": dimension,
                "judge": judge, "transcript_sha256": tx["sha256"], "status": "completed",
                "score": {"A": 2, "B": 3, "C": 2.5, "D": 4}[assignment["arm"]],
                "quotes": [{"turn_id": "t1", "start": 0, "end": len(text), "text": text}],
                "rationale": "Synthetic scoring fixture, not a semantic judgment.", "artifact_sha256": digest([ordinal, dimension])})
    return frozen, plan, transcripts, attempts


class MeasurementTests(unittest.TestCase):
    def test_paired_effects_and_reproducible_family_intervals_without_composite(self):
        args = fixtures()
        result = report(*args)
        self.assertEqual(result, report(*args))
        self.assertEqual(result["qualification"], "not_inferred")
        self.assertEqual(result["assigned_dialogues"], 40)
        for row in result["dimensions"].values():
            self.assertEqual(row["denominators"], {"completed": 40, "missing": 0, "technical_failure": 0, "not_applicable": 0})
            for name, value in (("C", 1.25), ("G", .75), ("interaction", .5)):
                self.assertEqual(row["contrasts"][name]["estimate"], value)
                self.assertEqual(row["contrasts"][name]["interval"], [value, value])
        self.assertNotIn("overall_score", result)

    def test_missing_failure_and_not_applicable_remain_in_denominators(self):
        manifest, plan, tx, rows = fixtures(2)
        rows.pop(0)
        rows[0].update(status="technical_failure", score=None, quotes=[])
        rows[1].update(status="not_applicable", score=None, quotes=[])
        result = report(manifest, plan, tx, rows)
        self.assertEqual(result["assigned_dialogues"], 8)
        self.assertEqual(sum(d["denominators"]["missing"] for d in result["dimensions"].values()), 1)
        self.assertEqual(result["technical_failure_attempts"], 1)
        for row in list(result["dimensions"].values())[:3]:
            self.assertIsNone(row["contrasts"]["C"]["estimate"])
            self.assertIsNone(row["contrasts"]["C"]["interval"])
            if row["denominators"]["not_applicable"]:
                self.assertIsNone(row["contrasts"]["C"]["missing_score_bounds"])
            else:
                lo, hi = row["contrasts"]["C"]["missing_score_bounds"]
                self.assertLess(lo, hi)

    def test_retry_retains_failure_and_never_overwrites_completion(self):
        manifest, plan, tx, rows = fixtures(1)
        original = rows.pop(0)
        failed = {**original, "id": "failed", "status": "technical_failure", "score": None, "quotes": []}
        result = report(manifest, plan, tx, [failed, *rows, original])
        self.assertEqual(result["technical_failure_attempts"], 1)
        self.assertEqual(result["dimensions"][original["dimension"]]["denominators"]["completed"], 4)
        with self.assertRaises(ValueError):
            report(manifest, plan, tx, [*rows, original, {**original, "id": "overwrite", "score": 5}])

    def test_quote_hash_judge_and_frozen_plan_mismatch_rejected(self):
        for mutation in ("quote", "hash", "judge", "score", "plan"):
            manifest, plan, tx, rows = fixtures(1)
            if mutation == "quote":
                rows[0]["quotes"][0]["text"] = "Invented quote"
            elif mutation == "hash":
                tx[0]["turns"][0]["text"] = "Changed transcript"
            elif mutation == "judge":
                rows[0]["judge"] = {**rows[0]["judge"], "kind": "human"}
            elif mutation == "score":
                rows[0]["score"] = float("nan")
            else:
                plan["config"]["alpha"] = .1
            with self.assertRaises(ValueError):
                report(manifest, plan, tx, rows)

    def test_small_family_count_does_not_report_pseudoreplicated_precision(self):
        result = report(*fixtures(1))
        for row in result["dimensions"].values():
            for effect in row["contrasts"].values():
                self.assertIsNone(effect["interval"])
                self.assertEqual(effect["families"], 1)
                self.assertEqual(effect["interval_status"], "too-few-independent-families")

    def test_unequal_family_sizes_do_not_change_equal_family_estimand(self):
        frozen, plan, _, _ = fixtures(4)
        design = frozen["design"]
        for index, scenario in enumerate(design["scenarios"]):
            scenario["family"] = "large" if index < 3 else "small"
        frozen = freeze_design(design)
        tx, rows = [], []
        for assignment in frozen["assignments"]:
            ordinal = assignment["ordinal"]
            transcript = freeze_transcript(frozen, ordinal, [{"id": "t", "actor": "sre", "text": "Wait."}])
            tx.append(transcript)
            score = 3 + int(assignment["family"] == "large" and assignment["arm"] in {"B", "D"})
            for d in DIMENSIONS:
                rows.append({"id": f"{ordinal}-{d}", "ordinal": ordinal, "dimension": d, "judge": plan["config"]["judge"],
                    "transcript_sha256": transcript["sha256"], "score": score, "status": "completed",
                    "quotes": [{"turn_id": "t", "start": 0, "end": 5, "text": "Wait."}],
                    "rationale": "Synthetic family-weight fixture", "artifact_sha256": digest([ordinal, d])})
        result = report(frozen, plan, tx, rows)
        for dimension in result["dimensions"].values():
            self.assertEqual(dimension["contrasts"]["C"]["estimate"], .5)
            self.assertEqual(dimension["contrasts"]["G"]["estimate"], 0)

    def test_no_transcripts_is_missing_not_a_pass_and_duplicate_attempts_reject(self):
        frozen, plan, tx, rows = fixtures(1)
        result = report(frozen, plan, [], [])
        self.assertEqual(result["available_transcripts"], 0)
        for dimension in result["dimensions"].values():
            self.assertEqual(dimension["denominators"]["missing"], 4)
            self.assertEqual(dimension["contrasts"]["C"]["missing_score_bounds"], [-4, 4])
            self.assertIsNone(dimension["contrasts"]["C"]["estimate"])
        with self.assertRaises(ValueError):
            report(frozen, plan, tx, [*rows, rows[0]])

    def test_reference_positive_categories_keep_evidence_and_provenance(self):
        manifest, _, tx, _ = fixtures(1)
        labels = []
        cases = {"reasonable_refusal": "I cannot authorize that action.", "unknown": "I do not know yet.",
            "defer": "Let us wait for the test result.", "conditional_agreement": "If the test passes, I can agree.",
            "disagreement": "I disagree; the risk remains unresolved."}
        for category, text in cases.items():
            transcript = freeze_transcript(manifest, 1, [{"id": "t1", "actor": "sre", "text": text}])
            labels.append({"id": category, "family": "f-0", "category": category, "transcript": transcript,
                "label": "clear", "label_source": "synthetic", "annotator_id": "fixture-author",
                "annotation_artifact_sha256": digest([category, text]), "rationale": "Synthetic positive control, not a human gold label.",
                "quotes": [{"turn_id": "t1", "start": 0, "end": len(text), "text": text}]})
        frozen = freeze_labels(manifest, labels)
        labels[0]["rationale"] = "changed"
        self.assertNotEqual(frozen["labels"][0]["rationale"], labels[0]["rationale"])
        self.assertTrue(all(r["label_source"] == "synthetic" for r in frozen["labels"]))
        changed = copy.deepcopy(frozen["labels"])
        changed[0]["quotes"][0]["start"] = 1
        with self.assertRaises(ValueError):
            freeze_labels(manifest, changed)
