# G4.10 Prerequisite and Terminal-Floor Local Prequalification

## Status

G4.10 is a narrow exploratory successor to G4.9. It keeps the Stanford-style
independent memories and perceive–retrieve–plan–reflect–act loop, RoomMind's
obligation graph and public ledger, the shared comparison player, the Baseline
implementation, the four published scenarios, and the six-dimension evaluation
protocol. No frozen G1–G4.9 artifact is modified.

## Frozen evidence motivating the change

G4.9 completed 8/8 dialogues and 48/48 independent evaluation dimensions with
zero dialogue failures and zero degraded output, but failed strict
qualification. Frozen probes and manual reading isolated three defects:

1. a deterministic player floor handoff was treated as a new request boundary,
   so the original multi-addressee response set appeared to lose Finance;
2. an `accepted` structured intent could be committed when its public clause
   said approval was only available "provided" another condition was met;
3. a later-phase approval and a second same-turn NPC utterance could occur
   before prerequisite state or immediately after the final confirmation.

## Architecture change

### Response sets survive visible handoffs

The latest substantive player request remains the origin of its ordered
multi-addressee response set across deterministic “Name, the floor is yours”
messages. A visible handoff transfers the floor but does not erase the request.
A later substantive player request still starts a new boundary.

### Clause-local conditional confirmation rejection

At the final public-quote grounding boundary, an `accepted` or `verified`
transition must have an unconditional supporting clause. Phrases such as
`provided`, `subject to`, `pending`, `until`, `cannot`, and `not yet confirm`
prevent that clause from committing an authoritative acceptance. An
unconditional clause elsewhere in the same utterance remains independently
eligible.

### Phase prerequisites and terminal floor lock

An accepted field that first unlocks a later configured phase is rejected while
earlier phase-entry conditions, or the target phase's other required conditions,
remain unmet. After each committed NPC ledger event, RoomMind synchronously
projects canonical public state. If that event satisfies all configured
completion fields, the remaining same-turn NPC floor is locked before another
agent can reopen the completed phase.

## Deterministic probes

G4.10 adds two frozen-session checks while retaining all applicable legacy and
G4.9 probes:

- no accepted or verified public-ledger event is grounded by a conditional or
  negated confirmation clause;
- no NPC speaks later in the same autonomous turn after the final authoritative
  completion-field confirmation.

The multi-addressee probe now follows deterministic player handoffs before
deciding that an addressed role failed to respond. Counterfactual replay over
the frozen G4.9 debug bundle confirms that the run-502 handoff is no longer a
false request boundary, while still detecting its conditionally committed
Finance approval. The replay also detects run 504's speech after the final
confirmation. This is mechanism coverage, not evidence of improved realism.

## Local qualification gates

Before a live batch, the candidate must pass Python compilation, speech-safety,
research-protocol and frozen-behavior smoke tests, database-backed dual-mode
regression, and both production frontend builds. A live qualification must use
a new frozen batch with:

- one matched RoomMind/Baseline pair for each of the four published scenarios;
- fixed `ollama/gpt-oss:120b` for dialogue and independent evaluation;
- seed `20260910`, dialogue concurrency one, and evaluation concurrency one;
- 8/8 frozen dialogues with zero dialogue failures and zero degraded output;
- all applicable legacy, G4.9, and G4.10 probes passing and all hashes recomputed;
- 48/48 evidence-grounded six-dimension scores without overwriting completed
  dimensions during targeted retry;
- manual reading of all four matched pairs, with no conditional acceptance,
  prerequisite inversion, lost response set, same-turn phase reopening, or
  material naturalness regression.

Development evidence remains exploratory, not confirmatory. External human
review must not start automatically.

## Local result

The candidate passes Python compilation, speech-safety, LLM-resilience,
public-ledger and research-protocol smoke tests; frozen G4.8 and G4.9 behavior
replays; the PostgreSQL dual-mode regression; and both client and admin
production builds. The frontend builds retain the existing large-chunk warning
but complete successfully. These results qualify the code for a new fixed-model
staging batch; they do not establish dialogue quality.
