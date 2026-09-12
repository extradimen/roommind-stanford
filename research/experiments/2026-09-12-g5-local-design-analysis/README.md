# G5 design-related analysis audit

Synthetic numeric controls only; no dialogue quality, real power estimate, study freeze, human annotation or external call.

`panel.json` content SHA256: `8bd2e906b070512b2bc1b64803b31875662345d96a8ec2fb4072390533fb0633`.
It contains full synthetic manifests/plans/transcripts/scores and fixed/sampled/missing/N-A reports, all family effects and intervals for the joint stress, and a byte-hash reference to the preserved prior rare-family bootstrap diagnostic. Old diagnostics were not regenerated or overwritten.

## Findings and implementation

- Explicit opt-in analysis v3 separates a **fixed-family observed benchmark** from an **independent-family population** target and binds a sampling-frame hash. Fixed benchmarks have descriptive point estimates but no population interval or claim about uncertainty in future model runs. Population intervals retain their stated assumptions, which the code cannot certify. A new target requires a new plan/manifest; v1/v2 hashes and outputs stay unchanged.
- Unequal variant counts and heterogeneous effects are aggregated within family before averaging families. The test control has C=-0.25, G=0.75 and interaction=0.5, matching an independent arithmetic oracle. Tripling identical repeated blocks leaves estimates and family intervals unchanged, although assigned-dialogue counts grow.
- Two missing scores are checked against all four extreme completions at scores 1/5: reported bounds equal their extrema. No complete-case estimate or confidence interval is produced. A single N/A retains the assignment denominator and makes the current all-assignment score contrast undefined, rather than assigning an invented numeric truth.
- The existing rare-family bootstrap counterexample remains valid: at n=10, p=.05, the probability of seeing no rare family is .5987369 and the exact coverage upper bound for this example is .4012631. Its old 20-trial empirical value .55 is noisy and does not supersede the exact argument.
- The new bounded-interval stress checks simultaneous inclusion over all 18 contrasts using 100 independent-family trials, each with 100 families and dependent dimensions. Observed joint coverage is 100/100. This small, specific control **does not certify** general coverage or adequate precision; the plug-in Monte Carlo standard error of zero is not evidence of zero uncertainty.
- A deliberately invalid control gives every nominal family the same random sign, with C=+4 or -4 and population expectation zero. At n=100, treating those families as independent excludes zero for either sign: exact coverage is zero. The bounded method does not cure dependence or family relabeling.

The two new sampling targets are not automatic recommendations. Fixed-set repeated-run expectations require their own design and uncertainty analysis; they are not supported by calling the observed-benchmark branch. Sample-size floor 10 and retained resample validation are legacy engineering checks, not scientific sufficiency.

## Integration and limitations

v3 is verified by the evaluator, SQLite evaluation archive/reconnect, full-source release validation and preflight frame binding. No new DB schema or online launcher is introduced; existing PostgreSQL/recovery paths are covered by full acceptance. Synthetic scenario hashes in numeric panels are declarations, not validated new world sources; the separate integration test uses sealed world sources.

Remaining research gates: real scoring/semantic calibration, family sampling frame and historical inventory, planned effect/precision/threshold choices, empirical pilot variance and missingness, deployed runtime identity, and explicit external authorization. Product-vs-strong-Baseline remains a separate, unlaunched track. No claim of outperforming Baseline follows from this audit.

Reproduce into a new directory:

```sh
PYTHONPATH=server:server/tests .venv312/bin/python server/tests/test_g5_design_diagnostics.py --output-dir NEW_DIRECTORY
```
