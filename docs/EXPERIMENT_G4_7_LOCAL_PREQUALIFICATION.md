# G4.7 Floor and Authority Routing Local Prequalification

## Status

G4.7 is a narrow exploratory successor to G4.6. It has passed deterministic
local prequalification but has not been pushed, deployed, or used to generate a
new qualification batch. No G4.6 transcript or evaluation artifact was changed.

## Why this iteration exists

G4.6 improved evidence discipline and truthful closure, but three of four
RoomMind runs failed an applicable integrity probe. Frozen transcripts exposed
five connected interaction defects:

1. the autonomous step rebuilt public history without persisted `public_intent`,
   `turn_id`, or `sequence_no`, so structured NPC-to-NPC addressees disappeared;
2. a polite lead-in could name the addressee in one sentence while the extracted
   question used only “you”, causing the target to be inferred as the player;
3. the player could repeat “please answer directly” indefinitely when the target
   remained silent;
4. repair output could ask one role to certify another role's task-critical work;
5. a role could make a categorical claim that contradicted a factual constraint
   in its own memory, such as “all support teams are fully trained” while knowing
   that two trained specialists were missing.

## Architecture change

### Persisted public floor state

Autonomous RoomMind and Baseline steps now pass the persisted public message
metadata into the identical comparison-player policy. Question extraction also
retains an addressee named in a courteous lead-in. This restores the target that
was already validated when the NPC spoke instead of asking a later model call to
guess it from a truncated sentence.

### Bounded cross-role yield

The player may make one concise visible floor yield to the addressed NPC. If the
same target still has not answered, the second yield explicitly leaves the
decision unresolved and requests a bounded close. Test and Baseline runners now
honor that shared player stop request; RoomMind reconciles its open obligations
through the normal no-progress outcome reducer rather than fabricating progress.

### Focus-owner routing

For task-critical state variables, capability boundaries, and work items with
registered `owner_ids`, a visible question about that focus may target only an
authorized owner. The check requires lexical overlap with the current focus and
therefore does not attempt general role inference or suppress unrelated
cross-role discussion. Invalid drafts, rendered candidates, repaired clauses,
and configured fallbacks share the same check.

### Factual self-consistency boundary

A high-confidence deterministic guard rejects a categorical positive claim when
it overlaps a known factual constraint in the same agent's discoverable or
hidden information. It does not expose the private fact, use redlines as facts,
or perform open-ended semantic judgment. This is a narrow protection against
obvious self-contradiction, not a substitute for human realism review.

### Natural recovery language

Question-shaped subjects are normalized before deterministic recovery, removing
malformed constructions such as “For Could you share...”. A repeated floor
yield uses a single bounded deferral rather than rotating synonymous demands.

## Observability and probes

G4.7 adds telemetry for bounded cross-role handoffs, focus-authority rejections,
and private-constraint contradiction rejections. New frozen-session probes check
that task-critical question targets are authorized and that a repeated player
handoff carries a registered target plus an explicit stop request. All prior
G2–G4.6 probes remain applicable.

## Local verification evidence

- Python `compileall`: pass;
- `smoke_speech_safety.py`: pass;
- `smoke_public_ledger.py`: pass;
- `smoke_llm_resilience.py`: pass;
- `smoke_research_protocol.py`: pass;
- database-backed `smoke_modes.py`: pass against the rollback-only local
  PostgreSQL test database;
- Client production build: pass, with the existing bundle-size warning;
- Admin production build: pass, with the existing bundle-size warning;
- `git diff --check`: pass;
- frozen G4.6 counterfactual replay: pass.

The replay recovered the intended target for all six selected G4.6 failures:
two supplier-targeted negotiation questions, one CFO-targeted launch question,
and three SRE-targeted incident questions. It also verifies clean recovery text
for the launch artifact request and rejection of the known staffing
contradiction. These are deterministic mechanism checks only; they do not prove
that newly sampled G4.7 dialogue is more realistic.

## Frozen experimental constants

A new live qualification must keep the existing comparison constants:

- four published scenarios and one matched RoomMind/Baseline pair per scenario;
- `ollama/gpt-oss:120b` for dialogue and independent evaluation;
- dialogue concurrency one and evaluation concurrency one;
- the shared public-only comparison player and independent rolling public
  memories for Baseline;
- all six realism dimensions reported separately;
- exact transcript export, SHA-256 recomputation, full debug bundle, and manual
  reading of all four pairs;
- development-only evidence; no automatic external human review.

## Qualification gates for a new batch

1. 8/8 dialogues freeze with zero technical failures and zero degraded output;
2. all transcript hashes recompute and every applicable G2–G4.7 integrity probe
   passes;
3. no player speaks for an NPC before the addressed NPC responds;
4. no task-critical question targets a role outside the registered owner set;
5. no repeated player handoff or synonymous “answer directly” loop survives;
6. no malformed deterministic repair text is visible;
7. completed or deferred outcomes reconcile with the obligation graph and public
   ledger;
8. independent six-dimension evaluation completes without overwriting completed
   dimensions during retry;
9. manual reading finds no material regression in role behavior, temporal
   consistency, interaction structure, or multi-party naturalness.

Only a new frozen live batch can determine whether G4.7 qualifies for external
expert review.
