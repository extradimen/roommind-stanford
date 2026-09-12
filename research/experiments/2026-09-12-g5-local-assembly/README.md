# G5 archived configuration assembly — local engineering only

This package adds `server/app/g5/assembly.py`. It reconstructs allowlisted
component classes from the existing archived runtime specifications. It does not
import modules named by configuration, discover routes, read credentials, or
authorize model access. Only `provider=offline` is accepted.

## Entry contract

Create `OfflineAssembler(transport_factories)` with an explicit mapping from each
archived `delegate_id` to a trusted zero-argument local transport factory. Then
call `factory(world=..., manifest=..., runtime_inputs=...)` and supply the returned
callable as `LocalBatch(..., factory=...)`.

`runtime_inputs` maps scenario IDs to dictionaries containing `spec`,
`role_inputs`, `max_steps`, and optionally `max_revisions`, `allow_reopening`,
`reliable_reopening`. It cannot override components, world identity, assignment,
or manifest. Runtime validates these values against the frozen hashes and stop
rules. The batch validates all assignments before creating its first world.

Each enabled adapter is newly constructed. Component fields, prompt hashes,
protocol constants, nested byte budgets and delegate declarations must roundtrip
exactly. Disabled factorial components stay absent. The factory copies archived
inputs rather than retaining caller-owned mutable dictionaries.

## Evidence

`server/tests/test_g5_assembly.py` tests all four arms, fresh adapter instances,
unknown fields/types, prompt mismatch, non-offline providers, unregistered
transport IDs, delegate/budget declaration drift, and changed stop inputs before
world creation. A four-arm batch stops after three events, resumes to four sealed
sources of seven events each, reuses sealed sources, and compares all 28 events
exactly against the pre-existing scripted factory on a separate SQLite store.

The test resolver uses scripted reference transports only; it does not return
reference component objects. Full-suite evidence is stored separately in
`docs/G5_LOCAL_ACCEPTANCE_20260912_ASSEMBLY.json`; older receipts and panels remain
unchanged. This package needs no new experimental transcripts: the full-suite
receipt binds the exact test and implementation sources.

Final full suite: 345 passed; no errors, failures or skips; source unchanged.
Receipt content SHA256:
`385db73427dd48e60e0bc70b38427e2df68bb9aaf2aa57dc8173c07cf7c90fb1`.
All validation processes exited. No prior evidence files were overwritten.

## Limits and next boundary

A trusted local callable can misrepresent its behavior. Offline declarations
and exact specifications are not a network sandbox, behavioral attestation or
proof of fresh underlying transport state. Operators must register suitable
trusted factories. Source revision authentication, cross-host locking and online
launch authorization are not supplied by this assembler. No external calls,
deployment, human review, real calibration or scientific qualification occurred.

Next local package: consolidate operational release checks and the executable
handoff requirements. Actual historical inventory, real calibration, sampling
and research-quality gates remain open and must not be inferred from unit tests.
