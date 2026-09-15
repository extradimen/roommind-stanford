# G4.12 Player Response Lock and Atomic Speech Grounding

## Status

G4.12 is a narrow exploratory successor to G4.11. It preserves the four
published scenarios, Baseline, Stanford-style independent agent memories,
RoomMind's public ledger and obligation graph, the shared comparison player,
and the six-dimension evaluation protocol. No frozen G1-G4.11 artifact is
modified.

## Frozen evidence motivating the change

G4.11 completed 8/8 dialogues and 48/48 evaluations, but failed strict
qualification. Its frozen transcripts show three remaining control defects:

1. player-addressed questions and explicit named-floor requests could be
   answered by an unrelated role, or receive no answer from the named role;
2. quote-level grounding could reject a structured transition only after the
   renderer had already accepted stronger public wording;
3. current claims that a plan, roadmap, or design artifact had been placed in
   a shared folder, drive, or repository bypassed attachment-oriented evidence
   guards.

## Architecture change

### Deterministic player-response lock

Every registered NPC explicitly addressed by the player's visible request is
placed in a response queue in public order. While that queue is open, courtesy
mentions, dispatch rules, coordinator focus, and unrelated roles cannot consume
the floor. A named `the floor is yours` request is treated as a direct response
request. Targets that cannot speak remain pending for the next turn; completed
targets are removed without discarding the rest of the queue.

### Atomic state-to-speech boundary

The decision draft is grounded against its structured public intent before
rendering. The final rendered quote is grounded again and is re-checked against
the resulting lifecycle before it can reach the timeline, memory stream, or
public ledger. A safe independent clause may be retained; otherwise the whole
utterance is suppressed and recorded as silent recovery. Thus a transition
rejected at either boundary cannot survive as `I approve`, `I confirm`, or
equivalent public wording.

### Shared-workspace artifact grounding

The evidence guard now recognizes completed placement and availability claims
for plans, roadmaps, specifications, drafts, folders, drives, repositories, and
channels. It rejects present/perfect claims without registered tool evidence,
including `is now in the shared drive` and `in the shared folder you'll find`,
while preserving genuine future commitments such as `I will add it after this
meeting`.

## Deterministic probes

G4.12 retains every applicable legacy through G4.11 check and adds:

- each player-addressed NPC responds in visible address order before any
  unrelated NPC can consume the floor;
- the existing rejected-transition surface probe is enforced at the actual
  post-render publication boundary;
- existing public-evidence probes classify shared-workspace delivery claims as
  unsupported unless backed by registered tool evidence.

The frozen G4.11 replay detects response-lock violations in runs 526, 528, and
530, all four rejected-transition surface failures, and the four unsupported
shared-workspace artifact claims in run 528. This proves diagnostic and
counterfactual mechanism coverage only; it is not evidence that newly generated
dialogue is more realistic.

## Local qualification gates

Before a live batch, the candidate must pass Python compilation, public-ledger,
speech-safety, LLM-resilience, research-protocol, G4.11 frozen-behavior replay,
the database-backed dual-mode regression, and both production frontend builds.
A live qualification must use a new frozen batch with:

- one matched RoomMind/Baseline pair for each published scenario;
- fixed `ollama/gpt-oss:120b` for dialogue and evaluation;
- seed `20260912`, dialogue concurrency one, evaluation concurrency one;
- 8/8 frozen dialogues, zero dialogue failures, and zero degraded output;
- all applicable legacy through G4.12 probes passing and all hashes recomputed;
- 48/48 evidence-grounded dimension results, retrying only missing dimensions;
- manual reading of all four pairs, with no wrong-speaker response, missing
  named response, rejected-transition surface mismatch, unsupported live
  artifact claim, premature closure, or material repetition regression.

Development evidence remains exploratory rather than confirmatory. External
human review must not start automatically.

## Local result

The candidate passes Python compilation; public-ledger, speech-safety,
LLM-resilience, and research-protocol smoke tests; frozen G4.6 through G4.11
behavior replays; the PostgreSQL dual-mode regression; and both client and
admin production builds. The frontend builds retain the existing large-chunk
warning but complete successfully. These checks qualify the code for a new
fixed-model staging batch; they do not establish dialogue quality.
