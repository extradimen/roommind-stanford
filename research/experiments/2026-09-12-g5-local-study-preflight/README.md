# G5 offline study preflight

This is synthetic engineering evidence, not an approved study plan. The ten families, two references per label per dimension and zero-error threshold are test controls, not recommended scientific choices.

`panel.json` includes the full frozen contract, before/current registries, original synthetic annotation and prediction records, and before/after reports. Content hash: `0680e35f0062050afea99bef33c5a5b7f2dfd8a300ec868311c1f0d34c6b61d7`.

The complete local consistency control passes. Appending development exposure then blocks both registry freshness and held-out status. Re-freezing a new contract cannot remove historical exposure. Additional tests cover exact-content family merging, declared used-family ancestry without exposure events, missing/partial calibration, wrong predictions, altered evidence, sample counts, missing registered material, substituted plans and invalid/null criteria.

## Entry points

`app.g5.study_preflight.freeze_contract` pins a verified manifest, analysis plan, full sample-plan specification hash, registry snapshot and calibration criteria. `inspect` revalidates full calibration source/label/prediction records and returns all failed checks. `require_local_contract` raises if any local check fails. All are read-only and create no worlds, workers, database migrations or model requests.

No production runner has been wired to these functions. Legacy callers are unchanged and are not retroactively protected. A future launcher must re-read the registry and apply the boundary immediately before execution; a saved report is not a reusable launch token. There is no transaction spanning a live registry and a future service, so this package does not claim atomic launch/registry locking.

## Research gates intentionally remain open

Passing local checks does not authenticate human identities, establish complete historical exposure or semantic novelty, justify sample size/thresholds, validate the six-dimension scoring judge, or verify deployed runtime identity. Binary case-classifier calibration is not scoring-judge calibration. Classification error bounds are descriptive possible-completion bounds, not uncertainty intervals for a population.

The report always retains these unverified research gates and `launch_authorized=false`. It never turns declared provenance or a changed scope string into authorization. No real data were sent, no human review occurred, no push/deployment/online batch was started. All prior files are retained.

Reproduce into a new directory:

```sh
PYTHONPATH=server:server/tests .venv312/bin/python server/tests/test_g5_study_preflight.py --output-dir NEW_DIRECTORY
```
