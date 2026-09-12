# G5 local frozen batch entry

Synthetic engineering execution, not an online qualification or efficacy experiment. No external model calls, new data transfer, deployment or GitHub push.

`panel.json` content hash: `54da6ef510474d8a9c89d5804696582e389b721e70e31a423c6f30cfac4397d8`.
It preserves the full preflight contract and calibration controls, family registry, first three committed events, progress records, all four sealed sources with 28 events, and evaluation input packets. Evaluation was not started by this entry. Source attempt IDs can differ on a fresh reproduction; old evidence is not overwritten.

## Delivery

`app.g5.local_batch.LocalBatch` is a cooperating single-host entry for **synthetic exploration only**. It requires a complete preflight, all composed runtime declarations, role inputs, common request budget/window, delta cognition storage, reliable reopening, and an explicit reopen schedule for every assignment. All assignments are configured/validated before any world is created. Model provider declarations must be `offline`.

All four conditions in a paired block must have exactly the same frozen reopen schedule, and every request version must be below the common step budget. Asymmetric or over-budget schedules are rejected before generation. This fixture uses an identical predefined schedule, not a validated adaptive cross-arm reopening policy.

The immutable private control DB binds contract, original calibration evidence, preflight and reopening schedule. Deterministic world IDs derive from that frozen execution and assignment. On first use it records world storage identity, then rejects switching this control to replacement storage. SQLite uses path/device/inode; PostgreSQL uses the connected database/address/port and schema OID. These are local consistency checks, not cryptographic cluster identity.

The existing local kernel lock covers the entire async stream, including suspended yields, model waits and sealing. Cooperating callers must use the same persistent control file. Do not delete/copy the coordination file or use an independent control to “recover” the same study. Direct legacy writers, other hosts and malicious factories are outside this lock; it is not a distributed lease.

Runtime histories and budgets are not reset. Completed sources are verified and reused without new generation. Stable predeclared reopening requests remain in the world journal. Technical exceptions are retained and propagated; the entry does not run unbounded automatic retries. Close interrupted streams explicitly before closing/reopening their control DB. Pending external inference would not be exactly-once, but this entry only executes trusted local scripts.

`evaluation_inputs()` requires all assigned worlds to be sealed and revalidates every source before producing packets. It never invokes an evaluator. A premature request cannot turn an incomplete batch into valid evaluation input.

## Verified recovery and rejection paths

- Three-commit interruption, close/reopen and all four sources completed with original prefix retained.
- Real child exits before commit / after commit but before acknowledgement: zero / one initial events, then recovery to 28 without duplicate publication.
- Technical annotation failure retains failed attempts and resumes without replacing worlds.
- Competing worker rejected; changed schedule, changed registry, wrong final assignment configuration and replacement SQLite storage rejected.
- Actual local PostgreSQL pool close/reconnect completes the same batch with exact event parity against SQLite. No PostgreSQL service restart or staging recovery was performed.
- Initial test query used the wrong `g5_worlds` column; corrected to `id`. Subsequent dedicated tests passed. This was a test error, not corruption or a hidden runtime failure.
- First full acceptance (`G5_LOCAL_ACCEPTANCE_20260912_BATCH_ENTRY.json`) retained one failure: its child process could not import `test_g5_local_batch` under the full runner's `PYTHONPATH=server`. The child never reached recovery. The test now explicitly supplies `server:server/tests`, matching the other process tests; final acceptance is recorded separately as `G5_LOCAL_ACCEPTANCE_20260912_BATCH_ENTRY_FINAL.json`. The failed receipt is preserved, not relabeled.
- The corrected 340-test receipt passed with hash `6ea4918880d547eab40c8ba9ee1121e82c88b4aff811a18d6e574ad3caaa3774`. Final review then added the paired schedule/budget constraints; the latest version is covered by the separate `G5_LOCAL_ACCEPTANCE_20260912_BATCH_ENTRY_FAIRNESS.json`, not retroactively by that earlier receipt.

## Boundaries still open

Preflight freshness is checked before operations, not in a shared transaction with generation. A registry change during an awaited model call can be detected only at the next boundary; no cross-service atomic start is claimed. Factories are trusted Python dependencies, not sandboxed plugins: `offline` labels are not a network firewall. Runtime specification checks do not authenticate an implementation or the deployed Git revision.

This executable fixture uses existing test factories. A production-quality archived-configuration assembler, external authorization/transport activation, deployment identity, operational supervision, true calibration and research-plan freeze remain separate work. Formal population sampling/thresholds remain undecided. Historical G1–G4.16 and old G5 inputs were not modified.

Run a new private synthetic artifact:

```sh
PYTHONPATH=server:server/tests .venv312/bin/python server/tests/test_g5_local_batch.py --output-dir NEW_DIRECTORY
```

This command uses temporary owned SQLite stores. It does not resume a previously deployed batch or contact a model provider.

Final acceptance: 341 tests passed, no errors/failures/skips, stable source fingerprints. Receipt `docs/G5_LOCAL_ACCEPTANCE_20260912_BATCH_ENTRY_FAIRNESS.json`, content hash `f27eb4badc168c4885ed2c448bd32a576e224f49711c55d9d1894c2022deaeba`. All verification processes exited; overall research/release gates remain incomplete.
