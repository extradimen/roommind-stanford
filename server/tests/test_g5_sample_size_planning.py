"""Analytic planning checks, not a power simulation or real pilot."""
import math
import unittest

from app.factorial_study import digest
from app.g5.sample_size_planning import precision_grid


class PrecisionTests(unittest.TestCase):
    def test_radius_sufficient_and_previous_integer_insufficient(self):
        result = precision_grid(.05, [.25, .5, 1.])
        for row in result["rows"]:
            for effect in row["effects"].values():
                self.assertLessEqual(effect["radius"], row["target_half_width"])
                self.assertGreater(effect["range_width"] * math.sqrt(math.log(720) / (2 * (effect["families"] - 1))), row["target_half_width"])
            self.assertEqual(row["families_for_all_18"], row["effects"]["interaction"]["families"])
            self.assertEqual(row["minimum_dialogues_one_block_per_family"], 4 * row["families_for_all_18"])

    def test_tighter_error_and_precision_increase_required_families(self):
        broad, narrow = precision_grid(.05, [1., .5])["rows"]
        stricter = precision_grid(.01, [1.])["rows"][0]
        self.assertGreater(narrow["families_for_all_18"], broad["families_for_all_18"])
        self.assertGreater(stricter["families_for_all_18"], broad["families_for_all_18"])
        self.assertEqual(broad["effects"]["C"], broad["effects"]["G"])

    def test_no_qualification_and_digest_covers_assumptions(self):
        result = precision_grid(.05, [.5])
        self.assertEqual(result["status"], "illustration_not_frozen_study")
        self.assertFalse(result["launch_authorized"])
        self.assertEqual(result["sha256"], digest({k: v for k, v in result.items() if k != "sha256"}))
        self.assertIn("power", result["not_established"])

    def test_invalid_numeric_or_ambiguous_inputs_rejected(self):
        for alpha in (True, 0, -.1, .5, float("nan"), float("inf"), "0.05"):
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                precision_grid(alpha, [.5])
        for widths in ([], [.5, .5], [True], [0], [-1], [5], [float("nan")], [float("inf")], [.5, "1"], [1e-300], None):
            with self.subTest(widths=widths), self.assertRaises(ValueError):
                precision_grid(.05, widths)
