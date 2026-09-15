# G4.11 Direct Routing and State-Surface Convergence

## Status

G4.11 is a narrow exploratory successor to G4.10. It preserves the four
published scenarios, Baseline, Stanford-style independent agent memories,
RoomMind's public ledger and obligation graph, the shared comparison player,
and the six-dimension evaluation protocol. No frozen G1-G4.10 artifact is
modified.

## Frozen evidence motivating the change

G4.10 completed 8/8 dialogues and 48/48 evaluations without technical or
degraded-output failures, but failed strict qualification. Manual reading and
the frozen debug bundle identified three coupled control defects:

1. an NPC could visibly ask another present NPC a question after the target's
   turn or after the normal speaker quota was consumed; the player then relayed
   the floor and the addressed NPC sometimes never answered;
2. governance could rebuild the obligation graph from a stale variable snapshot
   before projecting the latest accepted field events from the canonical ledger;
3. a transition rejected structurally as a repeat or unsupported update could
   still surface as first-person confirmation language.

## Architecture change

### Bounded direct NPC response routing

A visible NPC-to-NPC question reserves the immediately following autonomous
tick for its registered target. The target is moved to the front of the
remaining queue or receives one additional tick if it already spoke. At most
one such extra response edge is created per autonomous turn, preventing
unbounded agent chains while removing the player as an administrative relay.

### Atomic ledger, field, obligation, and focus projection

Before selecting a coordinator focus, RoomMind now projects the canonical
public ledger into both work items and configured field variables, evaluates
completion, and rebuilds the obligation graph from that same snapshot. A field
whose authorization policy is already satisfied cannot remain proposed or be
selected again merely because an earlier read model was stale. A genuine
authorized rejection still reopens the obligation through a public event.

### Rejected-transition speech boundary

When `commit_allowed` is false, first-person confirmation, approval, acceptance,
endorsement, sign-off, or completion wording exceeds the validated lifecycle
even if another actor previously advanced the canonical entity to that state.
The ordinary speech repair path must replace or suppress it. Historical factual
statements that accurately describe an earlier actor's accepted event remain
eligible.

## Deterministic probes

G4.11 retains every applicable legacy and G4.10 check and adds:

- every visible NPC-directed question is followed immediately, in the same
  autonomous turn, by the addressed NPC;
- a structurally rejected transition is not reintroduced through stronger
  first-person public wording.

The frozen G4.10 replay detects missing direct responses in runs 516, 518, and
522, and rejected-transition wording in run 516. This proves diagnostic and
counterfactual mechanism coverage only; it is not evidence that new generated
dialogue is more realistic.

## Local qualification gates

Before a live batch, the candidate must pass Python compilation, public-ledger,
speech-safety, LLM-resilience, research-protocol, and frozen-behavior tests; the
database-backed dual-mode regression; and both production frontend builds. A
live qualification must use a new frozen batch with:

- one matched RoomMind/Baseline pair for each published scenario;
- fixed `ollama/gpt-oss:120b` for dialogue and evaluation;
- seed `20260911`, dialogue concurrency one, evaluation concurrency one;
- 8/8 frozen dialogues, zero dialogue failures, and zero degraded output;
- all applicable legacy through G4.11 probes passing and all hashes recomputed;
- 48/48 evidence-grounded dimension results, retrying only missing dimensions;
- manual reading of all four pairs, with no player-mediated NPC routing,
  resolved-focus reopening, rejected-transition surface mismatch, unsupported
  current-world claim, or material repetition/naturalness regression.

Development evidence remains exploratory rather than confirmatory. External
human review must not start automatically.

## Local result

The candidate passes Python compilation; public-ledger, speech-safety,
LLM-resilience, and research-protocol smoke tests; frozen G4.6 through G4.10
behavior replays; the PostgreSQL dual-mode and closure regression; and both
client and admin production builds. The frontend builds retain the existing
large-chunk warning but complete successfully. These checks qualify the code
for a new fixed-model staging batch; they do not establish dialogue quality.
