"""Design-related numeric stress, not dialogue data or a real power calculation."""
import math
import random
from statistics import mean

from app.factorial_study import ARMS, digest
from app.g5.measurement import DIMENSIONS, WEIGHTS, bounded_family_interval, require


def correlated_family_stress(*, trials, families, seed, alpha=.05):
    require(type(trials) is int and trials > 0 and type(families) is int and families >= 10
        and type(seed) is int and type(alpha) in (int, float) and math.isfinite(alpha) and 0 < alpha < .5,
        "Invalid stress design")
    rows = []
    for trial in range(trials):
        rng = random.Random(digest(["g5-joint-design-stress-v1", seed, trial]))
        values = {d: {e: [] for e in WEIGHTS} for d in DIMENSIONS}
        for _ in range(families):
            shared = rng.choice((-1, 1))
            for d in DIMENSIONS:
                # Shared family latent induces dependence between dimensions;
                # family draws themselves are independent in this control.
                scores = {a: 3 + shared + rng.choice((-1, 1)) for a in ARMS}
                for e, weights in WEIGHTS.items():
                    values[d][e].append(sum(scores[a] * w for a,w in weights.items()))
        intervals = {d: {e: bounded_family_interval(v, alpha, e) for e,v in effects.items()} for d,effects in values.items()}
        covered = all(interval[0] <= 0 <= interval[1] for effects in intervals.values() for interval in effects.values())
        rows.append({"trial": trial, "family_effects": values, "intervals": intervals, "joint_18_covered": covered})
    rate = mean(r["joint_18_covered"] for r in rows)
    # Deliberate assumption violation: all nominal families share one sign.
    # C contrast is +/-4 in every family, so the population mean is zero but
    # treating them as independent can exclude zero under either sign.
    invalid = [bounded_family_interval([sign * 4] * families, alpha, "C") for sign in (-1, 1)]
    raw = {"schema": "g5-design-related-interval-stress-v1", "classification": "synthetic-numeric-only",
        "config": {"trials": trials, "families": families, "seed": seed, "alpha": alpha},
        "independent_control_true_effects": "all_18_zero", "trials": rows,
        "empirical_joint_18_coverage": rate, "monte_carlo_standard_error": math.sqrt(rate * (1-rate) / trials),
        "invalid_shared_sign_intervals": invalid,
        "invalid_shared_sign_exact_coverage": sum(lo <= 0 <= hi for lo,hi in invalid) / 2,
        "limitations": "Finite Monte Carlo diagnostics do not certify coverage or power. The shared-sign control deliberately violates independence. Repeated blocks within a family are not extra independent families. No real judge, model or dialogue evidence.",
        "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}
