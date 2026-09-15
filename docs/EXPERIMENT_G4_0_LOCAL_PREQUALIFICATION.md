# G4.0 Bounded Agenda Convergence Prequalification

## Research status

G4.0 is an exploratory architecture candidate. It must not be described as an
improvement until a frozen matched RoomMind/Baseline experiment and manual
paired reading are complete.

## Changes from G3.9

1. **Same-speaker repetition gate.** A high-threshold lexical overlap check
   examines only each speaker's own recent utterances. Near-identical promises
   and requests are suppressed and regenerated; cross-role restatement and
   ordinary topic continuity remain allowed.
2. **Public acceptance guard.** The shared comparison player receives a salient
   rendering of public completion thresholds and is instructed not to call a
   violating value final. The rule uses no RoomMind private state and is
   identical in both conditions.
3. **Bounded no-progress outcome.** Reaching the configured no-progress window
   produces a public, auditable `conditional` or `deferred` outcome while
   retaining every open issue. It never confirms missing work. `stalled` is
   reserved for safety-limit or technical exhaustion.
4. **New observability.** Exports report near-duplicate suppression and
   governor-bounded closure counts. Integrity probes recompute same-speaker
   repetition from frozen public transcripts.

The Stanford-style RoomMind core remains intact: independent per-role memory,
planning, perception, retrieval, reflection and action continue inside a
shared public world. G4.0 changes the governance boundary, not the agents'
private cognition.

## Deterministic prequalification

Required local checks:

```text
PYTHONPATH=server .venv312/bin/python server/tests/smoke_speech_safety.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_public_ledger.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_research_protocol.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_llm_resilience.py
.venv312/bin/python -m compileall -q server/app server/tests
git diff --check
```

The regression suite must prove that a paraphrased repeated request is caught,
a materially new answer on the same topic is retained, and a no-progress close
preserves open issues without fabricating confirmation.

## Frozen experiment design

- four existing scenarios and matched RoomMind/Baseline pairs;
- fixed `ollama/gpt-oss:120b` for dialogue and evaluation;
- one repetition for local qualification, concurrency one;
- maximum 20 turns, maximum six stagnant turns;
- fixed random seed recorded in the immutable manifest;
- dialogue generation, evaluation and human review remain separate;
- external human review remains disabled.

## Qualification gates

1. 8/8 dialogues freeze with no technical failure or LLM degraded fallback.
2. Every transcript hash recomputes exactly.
3. All applicable deterministic integrity probes pass for RoomMind.
4. No RoomMind transcript ends `stalled`; any governor-bounded close must retain
   nonempty open issues and is reported as a non-successful business outcome.
5. No same-speaker near-duplicate remains in a frozen RoomMind transcript under
   the registered G4 detector. Suppression counts are reported separately.
6. Completed outcomes retain a valid closure lock and satisfy every configured
   condition; bounded closure never upgrades an unmet field.
7. Unsupported current-world actions remain absent from RoomMind public speech.
8. All six dimensions complete independently. AI scores are descriptive only.
9. Manual reading covers all four matched pairs and specifically checks
   repetition, premature acceptance, reopening, missing roles, unsupported
   actions and natural closure.

Passing engineering gates is necessary but not sufficient. Promotion requires
manual evidence that G4.0 improves meeting realism rather than merely shortening
the transcript or relabeling a loop as a deferral.
