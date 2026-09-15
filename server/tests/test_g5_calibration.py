import copy
import unittest

from app.factorial_study import digest
from app.g5.calibration import freeze_cases, report


def case(i, label="clear", source="synthetic"):
    return {"id": str(i), "family": "test", "category": "grounding", "input_sha256": digest(i),
            "label": label, "label_source": source}


def result(c, prediction="clear", status="completed"):
    return {"case_id": c["id"], "input_sha256": c["input_sha256"], "status": status, "prediction": prediction}


class CalibrationTests(unittest.TestCase):
    def test_confusion_matrix_and_provenance(self):
        cases = [case(0), case(1), case(2, "violation"), case(3, "violation", "assistant")]
        rows = [result(c, p) for c, p in zip(cases, ["clear", "violation", "clear", "violation"])]
        stats = report(freeze_cases(cases), rows)
        self.assertEqual([stats["overall"][k] for k in ("tp", "tn", "fp", "fn")], [1, 1, 1, 1])
        self.assertEqual(stats["overall"]["false_positive_rate_decisive"], 0.5)
        self.assertEqual(stats["overall"]["false_negative_rate_decisive"], 0.5)
        self.assertNotIn("human", stats["strata"]["label_source"])

    def test_missing_failure_abstention_not_passes(self):
        cases = [case(i) for i in range(3)]
        rows = [result(cases[0], None, "technical_failure"), result(cases[1], "abstain")]
        stats = report(freeze_cases(cases), rows)["overall"]
        self.assertEqual((stats["missing"], stats["technical_failure"], stats["abstain"]), (1, 1, 1))
        self.assertEqual(stats["decisive_labeled_count"], 0)
        self.assertIsNone(stats["false_positive_rate_decisive"])
        self.assertAlmostEqual(stats["completion_rate"], 1/3)

    def test_uncertain_and_inapplicable_references_excluded_explicitly(self):
        cases = [case(0, "uncertain"), case(1, "not_applicable")]
        stats = report(freeze_cases(cases), [result(c) for c in cases])["overall"]
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["uncertain_reference"], 1)
        self.assertEqual(stats["not_applicable"], 1)
        self.assertEqual(stats["decisive_labeled_count"], 0)

    def test_duplicate_unknown_mismatched_results_fail(self):
        c = case(0)
        frozen = freeze_cases([c])
        for rows in ([result(c), result(c)], [result(case(99))],
                     [{**result(c), "input_sha256": "a"*64}],
                     [result(c, "clear", "technical_failure")]):
            with self.assertRaises(ValueError):
                report(frozen, rows)

    def test_freeze_tampering_and_inputs_unchanged(self):
        cases = [case(0)]
        frozen = freeze_cases(cases)
        original = copy.deepcopy(frozen)
        report(frozen, [])
        self.assertEqual(frozen, original)
        cases[0]["label"] = "violation"
        self.assertEqual(frozen["cases"][0]["label"], "clear")
        frozen["cases"][0]["label"] = "violation"
        with self.assertRaises(ValueError):
            report(frozen, [])
