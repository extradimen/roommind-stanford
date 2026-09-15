# G4.9 Response Routing and Authorship Local Prequalification

## Status

G4.9 is a narrow exploratory successor to G4.8. It preserves the Stanford-style
independent memories and perceive–retrieve–plan–reflect–act loop, RoomMind's
obligation graph, the public comparison player, the Baseline implementation,
the four published scenarios, and the six-dimension evaluation protocol. It
does not alter any frozen G1–G4.8 transcript or evaluation artifact.

## Frozen evidence motivating the change

G4.8 completed 8/8 dialogues and 48/48 evaluation dimensions without a
technical failure, but failed strict qualification. Manual reading and frozen
diagnostics identified three narrow interaction defects:

1. a player message could address Operations and Finance separately, while a
   courtesy mention of Sales was prioritized and the dialogue closed after
   only one required owner answered;
2. the generated player repeatedly published the same visible administrative
   sentence asking an NPC to answer “directly from your area”;
3. in the structured interview, panel NPCs asked one another to supply the
   candidate's history and then spoke in the first person as if they had been
   the candidate's past collaborator.

## Architecture change

### Ordered multi-addressee routing

Direct request and question targets are resolved clause by clause in public
order. These targets outrank courtesy mentions and older queued responses when
the orchestrator chooses speakers. A latest player message remains pending
until every explicitly requested registered NPC has spoken. This is public
floor state only; it does not infer private obligations or mark task fields
complete.

### Minimal visible floor handoff

The first deterministic player handoff is reduced to “Name, the floor is
yours.” The existing second-attempt bounded deferral remains unchanged. The
change removes repeated administrative prose while retaining a visible,
auditable floor transfer shared by RoomMind and Baseline.

### Interview authorship boundary

In a structured interview, autobiographical experience belongs to the player
or candidate. Panel NPCs may ask the candidate, assess the answer, confirm that
evidence is sufficient, and answer questions about the current organization.
They may not route a candidate-history question to another panel NPC or claim
first-person ownership of the candidate's historical work. Drafts, repaired
drafts, rendered candidates, and configured fallback paths share this check.

## Deterministic probes

G4.9 adds three frozen-session checks:

- every NPC explicitly addressed in a multi-addressee player request responds
  before the next player message;
- the retired generated “answer directly from your area” prompt is absent;
- panel NPCs do not substitute themselves as authors of candidate history.

Counterfactual replay over the frozen G4.8 debug bundle detects the actual
missing Finance response in run 494, the repeated generated routing prompts in
runs 494 and 496, and retrospective authorship substitution in run 496. Replay
is diagnostic coverage only and is not evidence that new G4.9 dialogue is more
realistic.

## Local qualification gates

Before a live batch, the candidate must pass Python compilation, speech safety,
LLM resilience, public-ledger and research-protocol smoke tests, the frozen G4.8
behavior replay, database-backed dual-mode regression, and both production
frontend builds. A live qualification must then use a new frozen batch with:

- one matched RoomMind/Baseline pair for each of the four published scenarios;
- fixed `ollama/gpt-oss:120b` for dialogue and independent evaluation;
- seed `20260909`, dialogue concurrency one, and evaluation concurrency one;
- 8/8 frozen dialogues with zero dialogue failures and zero degraded output;
- all applicable legacy and G4.9 probes passing and all hashes recomputed;
- 48/48 evidence-grounded six-dimension scores without overwriting completed
  dimensions during retry;
- manual reading of all four matched pairs, with no premature multi-addressee
  closure, repetitive routing prompt, interview authorship substitution, or
  material regression in naturalness.

Development evidence is exploratory, not confirmatory. External human review
must not start automatically.
