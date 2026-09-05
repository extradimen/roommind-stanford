# G3.7 Proposition-Grounded Convergent Simulation Prequalification

## Disposition

**G3.7 passes deterministic and fixed-model local engineering
prequalification.** It is not yet qualified as a RoomMind realism improvement
and must not replace the frozen G3.6 result: the real-model probes exercised the
shared player and speech boundary, not a complete matched RoomMind/Baseline
batch. No staging deployment has been performed.

## Frozen G3.6 failures used as counterexamples

G3.7 starts from observed failures rather than a new untested feature list:

1. `All traffic to the affected service has been blocked` bypassed the visible
   action boundary because the completion was expressed in passive voice.
2. `Sample log entries attached` bypassed the attachment detector because the
   clause omitted an auxiliary verb and explicit speaker.
3. One long player-context slice began mid-word and appeared as a corrupted
   fragment in the next public turn.
4. A conditional sentence about one field cancelled an unconditional
   confirmation of another field in the same message.
5. An unavailable executable condition remained the coordinator focus for
   multiple turns and the simulation stalled instead of closing conditionally.
6. Optional post-decision issues could be promoted into required work merely by
   describing them as blockers.

## Architecture changes

### 1. Normalized public propositions

Public clauses are reduced to an object, terminal predicate, modality, and
kind before source validation. Active, passive, perfect, and terse forms now
share the same current-world grounding policy. The normalized layer is driven
by visible language and cannot be bypassed by an LLM-authored intent label.

The G3.6 passive traffic, terse log attachment, and delivered-email examples
are permanent regression cases. Future and conditional actions remain legal;
completed current-world actions still require a registered simulated-tool
result.

### 2. Clause-atomic field confirmation

Explicit confirmations are evaluated per field-bearing clause rather than per
whole message. An unconditional price acceptance can therefore be retained
when a later delivery sentence is conditional. Questions, negation,
conditional clauses, unauthorized speakers, and ungrounded executable fields
remain unable to create confirmation.

### 3. Persistent capability boundary

When an executable field lacks a registered simulated-tool result, the
coordinator records a durable `capability_boundaries[field]` entry. The same
unavailable field is not selected again on later turns. If a matching tool
result subsequently appears, the boundary is marked resolved and ordinary
field processing resumes.

### 4. Deterministic conditional-closure reducer

If every remaining completion condition is a persisted unavailable capability
boundary and all other required public work is resolved, the reducer produces
a truthful `conditional` outcome. It never marks the external action complete.
This separates “the meeting reached the limit of the text simulation” from
“the real-world operation happened.”

### 5. Completion-scope protection

In schema-driven tasks, a new side issue must overlap a configured open field
before it can become required coordinator work. Merely using words such as
`blocked` or `must` no longer makes an optional appendix or follow-up a new
completion prerequisite. Open-ended tasks without configured state fields may
still promote explicit public blockers.

### 6. Public-player sanitation

Pending direct questions are extracted as complete sentences instead of taking
the last character window of a long utterance. Braces and code-like fragments
are removed, and overlong questions are truncated only at word boundaries.
Generic player recovery language was shortened and rewritten as ordinary
meeting language rather than visible system-governance instructions.

### 7. Structured-output budget and retrospective continuity

The fixed model spent enough of a 768-token allowance on reasoning that its
first interview answer ended as truncated JSON and invoked deterministic
fallback. Public player and NPC-render allowances are now bounded at
1024--1536 tokens. This does not permit longer public speeches: the existing
120-word dialogue limit remains unchanged; it gives the model room to finish
the required JSON envelope.

Prompt-only continuity was also non-deterministic. For retrospective follow-up
questions that do not explicitly request a new example, both comparison
conditions now receive the exact most recent public player example as a
required continuity anchor. The anchor uses public dialogue only and therefore
does not give RoomMind privileged information.

### 8. Clause-local evidence attribution

A real-model incident probe exposed a mixed-clause loophole: an invented claim
that rollback had started could be followed by `we cannot confirm recovery`,
and the later disclaimer excused the whole response. Evidence attribution is
now checked clause by clause. Unrelated negative evidence (for example, an
unverified archive checksum) cannot ground a positive assertion about rollback
completion or healthy service metrics. Fully cautious statements remain legal.

## Observability and archived probes

Exports now include persistent capability boundaries. Batch summaries include
the number of unavailable boundaries and whether conditional closure was
produced by boundary reconciliation. G3.7 integrity probes check that the same
capability boundary is not focused repeatedly and that a boundary-driven
conditional outcome names only persisted unavailable fields. Existing G3.5
tool-source and G3.6 visible-action probes continue to apply to G3.7.

## Local verification

The following checks passed using an isolated Python 3.12 environment:

```text
PYTHONPATH=. python tests/smoke_speech_safety.py
PYTHONPATH=. python tests/smoke_llm_resilience.py
PYTHONPATH=. python tests/smoke_public_ledger.py
PYTHONPATH=. python tests/smoke_research_protocol.py
python -m compileall -q app tests
python -c "from app.main import app; assert app.title == 'RoomMind API'"
git diff --check
```

The test set covers the exact frozen counterexamples, mixed conditional and
unconditional confirmation, one-time capability focus, truthful conditional
closure, post-decision side-issue isolation, complete-question extraction,
retrospective anchor selection, mixed-clause evidence claims, and unrelated
negative evidence.

## Fixed-model local probe results

After explicit authorization, engineering probes were run through the local
Ollama service using the fixed `ollama/gpt-oss:120b-cloud` model. These are
prequalification observations, not confirmatory results:

1. The four-case behavior probe produced 4/4 grounded messages: the negotiation
   confirmed only stated terms, the launch decision stayed conditional, the
   interview requested concrete evidence, and incident containment remained a
   future action pending evidence.
2. The first multi-turn run exposed one truncated structured response and one
   fallback. Raising the bounded generation allowance eliminated that failure
   on the exact rerun without increasing the public-message word limit.
3. A later run exposed silent switching between interview projects. Adding the
   public continuity anchor made all four interview answers stay on the same
   onboarding example and preserve its core metrics.
4. Another incident run invented rollback logs and healthy metrics after prior
   turns had only requested them. The clause-local attribution regression was
   added. In the final three-turn incident rerun, the player explicitly said
   rollback and checksum verification remained unconfirmed and requested the
   responsible participants' evidence.
5. The final fixed-model probe had zero deterministic fallback. Its three
   interview turns stayed on one onboarding case, and its three incident turns
   contained no unsupported current-world completion.

Temporary full probe artifacts were written under `/tmp` and are not research
artifacts. The final claims above are also encoded as deterministic regression
cases so they do not depend on retaining ephemeral model output.

## Gate before staging

Before a G3.7 staging qualification:

1. freeze the candidate and run a small fixed-`gpt-oss:120b` matched
   RoomMind/Baseline batch; local component probes are insufficient;
2. require zero unsupported visible current-world completions or artifacts;
3. require capability focus at most once per unavailable field;
4. require configured confirmations to remain closed unless explicitly
   challenged by an authorized participant;
5. require RoomMind meetings to end as completed, conditional, deferred, or
   failed rather than by stagnation/safety limit;
6. manually read every matched transcript for naturalness, role distinction,
   contradiction, and closure quality;
7. preserve transcript hashes, traces, and all earlier generation artifacts.

Only after these gates should the candidate be pushed and deployed for a new
frozen development batch. External human review remains a later independent
stage.
