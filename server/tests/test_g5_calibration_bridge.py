"""Case-denominator/retry bridge fixtures, no external model or human labels."""
import copy
import unittest

import test_g5_annotation_archive as fixtures
from app.factorial_study import digest
from app.g5.calibration_bridge import freeze_predictor, freeze_results, report


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.AnnotationTests.asyncSetUp(self)
        for index, case in enumerate(self.frozen["plan"]["cases"]):
            if index == 0:
                continue
            label = "uncertain" if index == 3 else "not_applicable" if index == 4 else "clear" if index % 2 else "violation"
            self.archive.append(fixtures.AnnotationTests.row(self, case["id"], label=label))
            if index != 1:
                self.archive.append(fixtures.AnnotationTests.row(self, case["id"], who=1, label="clear" if index == 2 else label))
        self.annotation = self.archive.export()
        self.predictor = freeze_predictor({"id": "synthetic-classifier", "kind": "synthetic", "spec_sha256": digest("fixture")})

    def attempt(self, case_id, outcome="clear", previous=None):
        output = {"status": "technical_failure" if outcome is None else "completed", "prediction": outcome,
                  "rationale": "Synthetic classification/technical-failure control."}
        return {"id": digest([case_id, outcome, previous]), "case_id": case_id,
            "previous_attempt_sha256": digest(previous) if previous else None,
            "artifact": {"task": self.archive.task(case_id), "predictor": self.predictor["predictor"],
                         "output": output, "raw_record": {"fixture": "synthetic-output", "declared_output": output}}}

    def mixed_attempts(self):
        attempts = []
        for i, case in enumerate(self.frozen["plan"]["cases"]):
            if i % 6 == 0:
                continue
            outcome = {1: None, 2: "abstain", 3: "clear", 4: "violation", 5: "clear"}[i % 6]
            if i % 6 == 5:
                failed = self.attempt(case["id"], None)
                attempts += [failed, self.attempt(case["id"], outcome, failed)]
            else:
                attempts.append(self.attempt(case["id"], outcome))
        return attempts

    async def test_full_case_denominator_and_disjoint_prediction_outcomes(self):
        results = freeze_results(self.annotation, self.predictor, self.mixed_attempts())
        summary = report(self.annotation, results)
        counts = summary["overall"]
        self.assertEqual(counts["total_cases"], 24)
        self.assertEqual(summary["unique_source_dialogues"], 4)
        self.assertGreater(len(self.annotation["rows"]), 24)
        self.assertEqual([counts[k] for k in ("reference_awaiting", "reference_disputed", "reference_uncertain", "reference_not_applicable")], [2, 1, 1, 1])
        self.assertEqual([counts[k] for k in ("prediction_missing", "prediction_failed", "prediction_completed", "prediction_abstain")], [4, 4, 16, 4])
        self.assertEqual(summary["technical_failure_attempts"], 8)
        self.assertEqual(sum(s["total_cases"] for s in summary["strata"]["dimension"].values()), 24)
        self.assertEqual(sum(s["total_cases"] for s in summary["strata"]["family"].values()), 24)
        self.assertNotIn("human", summary["strata"]["reference_sources"])
        self.panel = {"annotation": self.annotation, "results": results, "report": summary}

    async def test_missing_is_not_clear_and_no_decisive_denominator_means_null(self):
        result = report(self.annotation, freeze_results(self.annotation, self.predictor, []))
        self.assertEqual(result["overall"]["prediction_missing"], 24)
        self.assertEqual(result["overall"]["decisive_pairs"], 0)
        self.assertIsNone(result["overall"]["false_positive_rate_decisive"])
        self.assertIsNone(result["overall"]["false_negative_rate_decisive"])
        self.assertEqual(result["overall"]["decisive_coverage"], 0)

    async def test_completed_abstention_cannot_be_retried_or_double_counted(self):
        first = self.attempt("case-1-0", "abstain")
        for rows in ([first, first], [first, self.attempt("case-1-0", "clear", first)]):
            with self.assertRaises(ValueError):
                freeze_results(self.annotation, self.predictor, rows)
        failed = self.attempt("case-1-0", None)
        good = self.attempt("case-1-0", "clear", failed)
        self.assertEqual(len(freeze_results(self.annotation, self.predictor, [failed, good])["attempts"]), 2)
        with self.assertRaises(ValueError):
            freeze_results(self.annotation, self.predictor, [good, failed])

    async def test_input_predictor_and_rehashed_result_substitution_rejected(self):
        original = self.attempt("case-1-0")
        for change in ("input", "predictor", "predecessor"):
            bad = copy.deepcopy(original)
            if change == "input":
                bad["artifact"]["task"]["turns"][0]["text"] += "tamper"
            elif change == "predictor":
                bad["artifact"]["predictor"]["kind"] = "human"
            else:
                bad["previous_attempt_sha256"] = digest("fake")
            with self.assertRaises(ValueError):
                freeze_results(self.annotation, self.predictor, [bad])
        results = freeze_results(self.annotation, self.predictor, [original])
        results["annotation_sha256"] = digest("other")
        results["sha256"] = digest({k: v for k, v in results.items() if k != "sha256"})
        with self.assertRaises(ValueError):
            report(self.annotation, results)

    async def test_exact_confusion_counts_on_decisive_cases_only(self):
        # Indices 5..8: clear, violation, clear, violation; all already agreed.
        cases = self.frozen["plan"]["cases"][5:9]
        attempts = [self.attempt(c["id"], prediction) for c, prediction in zip(cases, ["clear", "clear", "violation", "violation"])]
        counts = report(self.annotation, freeze_results(self.annotation, self.predictor, attempts))["overall"]
        self.assertEqual([counts[k] for k in ("tp", "tn", "fp", "fn")], [1, 1, 1, 1])
        self.assertEqual(counts["false_positive_rate_decisive"], .5)
        self.assertEqual(counts["false_negative_rate_decisive"], .5)
        self.assertEqual(counts["prediction_missing"], 20)


if __name__ == "__main__":
    import argparse
    import asyncio
    import os
    from pathlib import Path
    from app.g5.world import canonical
    parser = argparse.ArgumentParser(description="Synthetic case-calibration accounting; no external calls")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700, exist_ok=False)
    async def run():
        case = BridgeTests()
        try:
            await case.asyncSetUp()
            await case.test_full_case_denominator_and_disjoint_prediction_outcomes()
            raw = {"schema": "g5-synthetic-case-calibration-panel-v1", "real_model_calls": 0, "human_annotations": 0, **case.panel}
            raw["sha256"] = digest(raw)
            fd = os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical(raw))
                stream.flush()
                os.fsync(stream.fileno())
            print({"sha256": raw["sha256"], "overall": raw["report"]["overall"]})
        finally:
            case.doCleanups()
    asyncio.run(run())
