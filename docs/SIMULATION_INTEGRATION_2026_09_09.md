# Simulation integration record — 2026-09-09

This is an additive continuation of `INTERNAL_SIMULATION_EXECUTOR.md`. Earlier
reports, datasets and implementation records retain their original contents.

## Changes completed in this step

- A persistent response queue now records request identity, source actor,
  ordered targets, pending/blocked/answered status and answer turn/tick reference.
  An unanswered head owner prevents ambient replacement. Public nested requests
  reserve the next response slot. The legacy pending list is a projection of
  the queue. Repeated requests from the same source explicitly supersede the
  earlier outstanding owner entry without recording a nonexistent answer.
- Completion closes outstanding entries as `closed_unanswered`, not answered.
  The orchestrator, action boundary and fallback publication path reject
  further work after persisted completion.
- Four complete candidate scenario snapshots were generated with distinct
  slugs, without preferred numeric IDs or automatic import into staging.
  The source bytes and each generated snapshot have recorded SHA-256 hashes.
- Incident execution now has a declared sequence: diagnose scope, preserve
  evidence, activate containment. Both experimental conditions receive the same
  world/action contract. Other scenario snapshots have no declared executable
  operation yet; these snapshots are development candidates, not qualification.

## Failure discovered and retained

The first `world-v1` snapshot failed the new end-to-end reachability assertion:
the executor recorded successful containment, but the old task projection did
not recognize the action's lifecycle as an accepted field value. The test raised
`KeyError: containment_active`. This exposed a real integration gap missed by
the earlier receipt-only checks.

`research/scenario-designs/world-v1/` is preserved as audit evidence, not an
approved experiment input. `world-v2/` adds explicit `execution_confirms` on
world-result fields. For these fields only, the trusted receipt is passed
through existing confirmation authority and phase-prerequisite validation.
Ordinary negotiated approvals do not acquire this permission. Rejected
confirmations do not promote the task state. The revised test verifies three
registered receipts, confirmed containment and an overall task that is still
incomplete until its remaining approval conditions are met.

## Validation results

| Check | Result | Scope |
| --- | --- | --- |
| Executor suite | 10 passed | Permissions, outcomes, idempotency, drift, adapter parity, terminal/fallback guards, full incident receipt-to-field projection |
| Response queue suite | 3 passed | Ordering, blocked owner, nested request, supersession, terminal history; real orchestrator with mocked model/memory boundaries |
| PostgreSQL persistence | Passed | Isolated JSONB table; two conditions; commit, new connection, retry, rollback |
| Existing speech-safety smoke | Passed | Existing safety/state behavior |
| Existing public-ledger smoke | Passed | Existing ledger rules |
| G4.15 frozen failure replay | Passed | Historical detection regression only |
| Historical archive inventory | 135 unchanged | No missing or modified pre-review experiment/document files |

The PostgreSQL test uses a uniquely named schema and deletes only that schema
after completion. It neither migrates application tables nor touches experiment
records. Reconnecting to PostgreSQL is not the same as restarting the server
or proving full batch-worker crash recovery. The orchestrator test serializes
and reloads public state but mocks LLM and memory storage. These limitations
are explicit; no live-model improvement is established.

## Remaining before a new live qualification

1. Independent public-target extraction validation: the queue protects an
   identified owner, but the existing text resolver may still identify the
   wrong owner. Include held-out phrasing and multi-addressee questions.
2. Full initial scenario/role/world snapshot binding in batch manifests and
   evaluator packets. Distinguish executor-generated receipt text from NPC prose
   using verified provenance; a model-authored receipt label is not evidence.
3. Full application database/session-message and worker recovery tests, and
   initial-role-fact grounding coverage. The isolated JSONB test does not claim
   to cover every ORM/session boundary.
4. Freeze the candidate generation and predeclare repeated and held-out checks
   with separate six-dimension reporting before requesting deployment or a
   live qualification batch. Old four-pair development batches stay separate.

No new live batch was started, and the runtime generation label has not yet
been advanced. Do not deploy this intermediate integration as a qualified
successor to G4.15.
