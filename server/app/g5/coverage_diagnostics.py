"""Synthetic interval stress diagnostics, not scientific efficacy or certification.

An IID bounded rare-family effect demonstrates that a sample-size floor and
bootstrap tail resolution alone cannot ensure interval coverage. All family
effects are valid C contrasts: A=C=2, B=D=2+effect, with effect in {0,1}.
This examines one marginal interval using the production Bonferroni-18 tails;
it does not claim to validate joint coverage over all 18 contrasts.
"""
import math
import random

from app.factorial_study import digest
from app.g5.measurement import DIMENSIONS, family_bootstrap_interval, bounded_family_interval, require


def rare_family_stress(*, trials, families, resamples, seed, probability=.05, alpha=.05):
    require(type(trials) is int and trials > 0 and type(families) is int and families >= 10, "Positive trials and at least ten families required")
    require(type(probability) in (int, float) and 0 < probability < 1, "Nondegenerate rare-family probability required")
    require(type(alpha) in (int, float) and 0 < alpha < .5 and type(seed) is int, "Explicit alpha and seed required")
    config = {"minimum_families": 10, "resamples": resamples, "alpha": alpha, "seed": seed}
    rows = []
    for trial in range(trials):
        rng = random.Random(digest(["g5-rare-family-stress-v1", seed, trial]))
        values = [int(rng.random() < probability) for _ in range(families)]
        interval = family_bootstrap_interval(values, {**config, "seed": seed + trial}, DIMENSIONS[0], "C")
        bounded = bounded_family_interval(values, alpha, "C")
        rows.append({"trial": trial, "family_effects": values, "interval": interval,
                     "covered": interval[0] <= probability <= interval[1], "bounded_interval": bounded,
                     "bounded_covered": bounded[0] <= probability <= bounded[1]})
    coverage = sum(r["covered"] for r in rows) / trials
    # Even infinitely many bootstrap draws cannot recover an unobserved family
    # type from an all-zero sample. This exact counterexample needs no MC claim.
    exact_zero_sample_probability = (1 - probability) ** families
    raw = {"schema": "g5-synthetic-coverage-stress-v1", "evidence_use": "synthetic-algorithm-diagnostic-only",
        "config": {**config, "trials": trials, "families": families, "probability": probability},
        "true_effect": probability, "nominal_marginal_coverage": 1 - alpha / 18,
        "empirical_coverage": coverage, "monte_carlo_standard_error": math.sqrt(coverage * (1 - coverage) / trials),
        "bounded_empirical_coverage": sum(r["bounded_covered"] for r in rows) / trials,
        "exact_zero_sample_probability": exact_zero_sample_probability,
        "exact_coverage_upper_bound": 1 - exact_zero_sample_probability,
        "counterexample_below_nominal": 1 - exact_zero_sample_probability < 1 - alpha / 18,
        "trials": rows, "qualification": "not_inferred",
        "limitations": "A bounded IID counterexample, not a realistic variance estimate or sample-size recommendation. Small Monte Carlo runs are diagnostics only. No joint-18 or real-judge coverage validation."}
    return {**raw, "sha256": digest(raw)}


def main():
    import argparse
    import json
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, required=True)
    parser.add_argument("--families", type=int, required=True)
    parser.add_argument("--resamples", type=int, default=20000)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True, help="New local private JSON file; never overwrite")
    args = parser.parse_args()
    result = rare_family_stress(trials=args.trials, families=args.families, resamples=args.resamples, seed=args.seed)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({k: v for k, v in result.items() if k != "trials"}, sort_keys=True))


if __name__ == "__main__":
    main()
