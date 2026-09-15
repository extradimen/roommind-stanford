# G4.4 Deterministic Floor, Registered Owner and Timebox Closure Prequalification

## Research status

G4.4 is a local exploratory successor to the failed G4.3 qualification. It is
not yet a deployed generation and does not establish higher realism. A new
fixed-model matched batch is required after explicit push/deployment approval.

## Evidence motivating this iteration

The frozen G4.3 experiment exposed four domain-neutral failures:

1. prompt instructions did not reliably stop the shared player from answering
   before a specifically addressed NPC;
2. meetings assigned blocking work to names absent from the participant graph;
3. claims that hashes had been posted, reviewed or made immutable bypassed the
   current-world grounding boundary;
4. an otherwise healthy meeting reaching its timebox was labelled `stalled`,
   conflating incomplete business work with technical execution failure.

## Architecture changes

1. **Deterministic cross-role floor handoff.** If the latest unresolved public
   question targets another registered NPC, the shared controlled-comparison
   player publishes a minimal handoff before any player LLM call. The rule uses
   only the public transcript and participant directory and is identical in
   Baseline and RoomMind.
2. **Registered in-session owner invariant.** NPC and player speech is checked
   against the public participant directory. An explicit responsibility
   assignment to an unregistered personal name is rejected when it is an
   in-session/discussion action. A clearly typed external post-meeting follow-up
   remains legal and does not imply that the external person can speak now.
3. **Expanded current-world normalization.** `posted`, `shared`, `reviewed`,
   `matched`, `secured` and `immutable`, including plural hashes/checksums and
   `have just been` constructions, require an accepted registered simulated
   tool result when asserted about the current simulated world.
4. **Truthful timebox close.** Reaching the configured safety turn limit first
   invokes the existing domain-neutral no-progress reducer. Confirmed work is
   retained and unresolved work ends `conditional` or `deferred`; `stalled` is
   reserved for a state the reducer cannot reconcile.
5. **Independent G4.4 probe.** Frozen exports report whether any public turn
   assigned in-session responsibility to an unregistered participant.
6. **Mechanism telemetry.** Batch performance summaries separately count
   deterministic cross-role handoffs, unregistered-owner rejections and
   current-world grounding rejections, while the existing governor summary
   records the timebox stop reason.

The independent memories, perception/retrieval/planning/reflection/action
loops, task coordinator, scenarios and six-dimension evaluator are unchanged.
Baseline still receives independent per-agent rolling public memory but none of
RoomMind's governance state. The deterministic player handoff is shared because
player behavior is a controlled input, not the treatment.

## Local evidence

- Speech-safety/task-state, research-protocol, LLM-resilience and public-ledger
  smoke suites pass.
- Application modules compile and `git diff --check` passes.
- A mocked controlled-comparison player test proves an NPC-directed question
  returns a valid handoff without calling the LLM.
- Positive and negative tests cover registered owners, unregistered in-session
  owners and legitimate external follow-up owners.
- Frozen G4.3 replay detects Emily Chen and Alex Patel as unregistered public
  owners, two unsupported current-world evidence claims in incident command,
  and retains the two earlier negotiation cross-role violations.
- A dedicated local PostgreSQL 16 database was initialized and the
  database-dependent `smoke_modes.py` dual-mode session regression passed.
  This database is local-only and does not share state with staging.

## Required qualification design

After explicit authorization, freeze a new source revision and create a new
G4.4 batch rather than retrying G4.3 rows. Keep the four scenarios, fixed
`ollama/gpt-oss:120b` model, seed policy, player policy, turn limits and
concurrency comparable to G4.3. Generate and freeze all eight dialogues before
starting independent evaluation.

Qualification requires:

1. 8/8 dialogues and 48/48 evaluation dimensions with zero technical failures;
2. 8/8 transcript hashes recomputed from frozen public dialogue;
3. no RoomMind `stalled` outcome;
4. no G4.1--G4.4 floor, target, ownership or registered-owner probe failure;
5. no unsupported current-world artifact/action claim;
6. timebox endings preserve unresolved work as conditional/deferred rather than
   fabricate completion;
7. manual reading of all four pairs finds that deterministic handoffs and
   safety repairs remain natural and that RoomMind improves role, epistemic,
   interaction and procedural fidelity without introducing new loops.

External human review must not start automatically. Even a full engineering
pass remains exploratory evidence until the paired transcript review supports
promotion.
