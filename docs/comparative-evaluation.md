# Comparative evaluation mode

RoomMind exposes a prompt-only multi-role baseline for controlled experiments.
It is intended as a competitive baseline, not as a deliberately weakened demo.

## Experimental conditions

- `mode=test`: the RoomMind condition. It uses independent agent state,
  memories, dispatch, authority checks, task-state evaluation, phase progression,
  completion rules, and no-progress protection.
- `mode=baseline`: the prompt-only condition. One model receives the same
  scenario, character, private-state, authority, phase, completion, and speaker
  guidance fields in one prompt. It selects all NPC speakers and declares phase
  and completion without runtime enforcement.

Both autonomous conditions use an AI player and the same configured provider,
model family, scenario, strategy label, maximum turns, and public transcript.
For a paper, model/version, temperature, token budget, and run count must be
recorded and held constant wherever the architectures permit.

## URLs

```text
/play/{scenario_id}?mode=test
/play/{scenario_id}?mode=baseline
```

Both modes use the existing autonomous controls and public session export.

## Independent observation

Every exported session contains `external_observation`. These deterministic
metrics are computed only from public messages, public speaker metadata,
timestamps, and the system's own declared status. They do not read task state,
private memory, reasoning, dispatch decisions, or agent cognition.

Semantic metrics require a post-hoc blinded observer. After a session reaches
`completed` or `stopped`, use:

```text
POST /api/game/sessions/{session_uuid}/external-evaluation
GET  /api/game/sessions/{session_uuid}/evaluation-packet
```

The POST endpoint runs a non-participating evaluator and stores the result under
`external_evaluation` for later exports. The GET endpoint produces a
condition-hidden packet suitable for a separate model or human rater.

The semantic observer reports evidence sequence numbers for completion,
premature completion, authority violations, private-information leakage,
contradictions, semantic repetition, responsibility match, distinct
contribution, role consistency, and closure coherence.

## Analysis rule

`task_result` and `baseline_result` are system claims or diagnostics, not common
ground truth. Comparative outcome claims must use `external_evaluation` or a
separately rated `evaluation-packet`. Raters should not see which condition
produced a transcript, and a preregistered human-coded subset should be used to
measure agreement with the AI observer.
