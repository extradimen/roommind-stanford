# G4.8 Convergence, Closure, and Evidence Local Prequalification

## Status

G4.8 is a narrow exploratory successor to G4.7. It changes only mechanisms
directly falsified by the frozen G4.7 transcripts. Stanford-style independent
agent memories, perceive–retrieve–plan–reflect–act cognition, the RoomMind
obligation graph, the public-only comparison player, and the safety-only
Baseline remain unchanged.

## Evidence motivating this iteration

The G4.7 batch froze all eight dialogues without generation failure, but strict
qualification failed. Manual reading found four defects that its registered
probes did not adequately detect:

1. `no_task_progress` could close a dialogue immediately after an NPC asked a
   fresh directed question;
2. different roles could paraphrase the same unresolved request while staying
   below same-speaker and long-utterance similarity thresholds;
3. player-requested bounded closure still opened another NPC turn, allowing an
   objection or new question after the visible close;
4. claims such as “the attached files include …” and “we received and reviewed
   the attached report” bypassed the simulated-tool evidence boundary.

The independent evaluator also permitted empty evidence arrays in its example
while its parser required at least one sequence number, leaving one of 48 G4.7
dimensions incomplete after three attempts.

## Architecture changes

### Interaction-aware progress

The orchestrator persists a public `_pending_player_response` flag whenever an
NPC explicitly hands the floor to the player. A previous or newly created
directed question counts as interaction progress for the stagnation counter.
It does not complete task state and does not disclose any private memory; it
only prevents a fresh question from being mistaken for a deadlocked meeting.

### Terminal floor lock

When the shared comparison player emits `requested_end=true`, the player line is
persisted but no further NPC orchestration is started. The same terminal floor
rule applies to RoomMind and Baseline. RoomMind then reconciles remaining work
to its existing conditional/deferred outcome; no new post-closure objection can
appear in the transcript.

### Topic-aware cross-speaker repetition

The existing obligation repetition guard retains its conservative generic
threshold. For question/request speech about the active focus, it additionally
detects short paraphrases when the messages share the same normalized focus
topic and at least three material terms. Accepted, verified, submitted, rejected,
or blocked transitions remain exempt when validation confirms material progress.

### Stronger artifact and fragment boundaries

The evidence guard now covers attached files that purportedly contain or confirm
measurements and claims that a participant received or reviewed an attachment.
Such claims require a registered simulated tool result. A title-only fragment
such as `Mr.` is rejected as malformed. Private-constraint contradiction checks
now require at least two material overlapping stems, reducing silence caused by
unrelated facts that happened to share one word.

### Evaluator contract alignment

The strict JSON example now supplies a non-empty evidence array and explicitly
requires at least one valid public sequence number for every metric, including
non-occurrence judgments. This aligns the prompt with the unchanged parser and
keeps evidence provenance explicit.

## New deterministic probes

G4.8 adds four implementation-integrity checks:

- no semantic cross-speaker repetition around one active issue;
- no malformed title-only public fragment;
- no public speech after a player message marked `requested_end`;
- no ungrounded live artifact presentation or receipt claim.

Counterfactual replay over the frozen G4.7 debug bundle now detects the actual
negotiation fragment/artifact failures, the interview repetition failure, and
both post-closure failures. This replay is diagnostic only and does not alter
the frozen G4.7 evidence.

## Local verification

- Python compilation: pass;
- speech safety and task-state smoke test: pass;
- LLM resilience smoke test: pass;
- research protocol/probe smoke test: pass;
- PostgreSQL dual-mode and terminal-player-floor regression: pass;
- frozen G4.7 counterfactual replay: pass;
- `git diff --check`: pass.

## Frozen live qualification design

A live G4.8 qualification must use a new batch and preserve:

- scenarios 1–4, one matched RoomMind/Baseline pair per scenario;
- fixed `ollama/gpt-oss:120b` for dialogue and independent evaluation;
- concurrency one, seed `20260908`, and development-only study phase;
- the same public-only comparison player and safety-only Baseline;
- all six realism dimensions, exact transcript hashes, full debug bundle, and
  manual reading of all four pairs;
- no automatic external expert review.

Qualification requires 8/8 frozen dialogues with zero technical/degraded
failures, all applicable probes passing, 48/48 evidence-grounded evaluation
dimensions, and no material repetition, unsupported artifact, premature stop,
or post-closure speech in manual review. Only a new frozen batch can establish
whether G4.8 improves realism.
