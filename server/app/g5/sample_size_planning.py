"""Illustrative precision planning only; no fitted effects, study freeze or inference.

Invert the existing bounded-family Hoeffding/Bonferroni-18 radius. Independent,
bounded, defined family outcomes are assumptions, not certified by this utility.
"""
import argparse
import json
import math
import os

from app.factorial_study import digest
from app.g5.measurement import require


def precision_grid(alpha, half_widths):
    require(type(alpha) in (int, float) and math.isfinite(alpha) and 0 < alpha < .5, "Invalid alpha")
    require(isinstance(half_widths, list) and half_widths, "Explicit precision grid required")
    require(all(type(h) in (int, float) and math.isfinite(h) and 0 < h <= 4 for h in half_widths),
            "Finite positive half-widths up to four required")
    require(len(set(half_widths)) == len(half_widths), "Duplicate precision target")
    rows = []
    log_term = math.log(36) - math.log(alpha)
    for h in half_widths:
        require(h * h > 0, "Precision target exceeds numerical planning range")
        effects = {}
        for effect, width in (("C", 8), ("G", 8), ("interaction", 16)):
            raw_n = width * width * log_term / (2 * h * h)
            require(math.isfinite(raw_n), "Precision target exceeds numerical planning range")
            n = max(1, math.ceil(raw_n))
            effects[effect] = {"families": n, "range_width": width,
                "radius": width * math.sqrt(log_term / (2 * n))}
        all_effects_n = max(row["families"] for row in effects.values())
        rows.append({"target_half_width": h, "effects": effects,
            "families_for_all_18": all_effects_n,
            "minimum_dialogues_one_block_per_family": 4 * all_effects_n})
    raw = {"schema": "g5-illustrative-precision-planning-v1", "status": "illustration_not_frozen_study",
        "alpha": alpha, "simultaneous_contrasts": 18, "unit": "independent_family_outcome",
        "formula": "ceil(R^2*log(36/alpha)/(2*h^2))", "rows": rows,
        "assumptions": ["all outcomes defined and fully observed", "independent bounded family outcomes",
                        "fixed outcome definitions and judge", "sampling target justified separately"],
        "not_established": ["real effect", "power", "family independence", "label validity", "external validity"],
        "real_model_calls": 0, "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--half-widths", type=float, nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = precision_grid(args.alpha, args.half_widths)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(result))
