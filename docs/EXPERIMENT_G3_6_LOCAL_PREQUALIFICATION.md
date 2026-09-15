# G3.6 Quote-Grounded, Capability-Aware Simulation Prequalification

## Disposition

**G3.6 passes deterministic local engineering prequalification.** It is ready
for an isolated real-model probe, but not yet for a realism claim or external
human review. G3.5 artifacts remain frozen and unchanged.

## Problems carried forward from G3.5

1. Source-typed validation trusted the model's intent kind. A completed live
   action mislabeled as a statement could appear in public speech even though
   the canonical ledger correctly refused to advance.
2. Explicit public confirmations were still lost when the evaluator omitted
   `confirmed_by`, and values such as `84 RMB` did not normalize to the numeric
   schema type before projection.
3. The coordinator repeatedly pursued executable fields although no simulated
   tool existed to produce the required result.
4. After bounded generation failures, reusable safety sentences appeared as
   participant speech and made distinct business roles sound identical.

## Architecture changes

### 1. Quote-driven live-action boundary

Visible speech is now scanned sentence by sentence for completed current-world
operations such as containment, deployment, rollback, publication, archival,
hash verification, health checks, uploads, and traffic shifts. This check does
not depend on the LLM's intent label. A terminal operational clause is allowed
only when a validated intent is linked to a registered simulated tool result.

If one clause is unsupported but another is safe, the system retains the safe
complete clause instead of paraphrasing the entire utterance. Unsupported
artifact clauses are treated the same way.

### 2. Typed quote-level confirmation projection

An explicit, non-conditional acceptance can be recovered directly from public
speech when all of the following are present: a configured field reference, a
typed value, an acceptance cue, and an authorized confirmer. Numeric values
with units are normalized before ledger comparison (`84 RMB` becomes `84.0`).
Questions, negations, conditional acceptances, silence, and unauthorized
speakers cannot create confirmation.

Executable fields remain stricter: public speech cannot confirm them without
the verified action already present in the simulated-tool ledger.

### 3. Capability-aware coordination

The coordinator marks an unresolved executable field as a
`capability_boundary` when no matching simulated tool result exists. It tells
participants to state the proposed action and owner and then close
conditionally or defer, instead of requesting an impossible live result over
and over. Once a matching tool result exists, normal state-variable processing
resumes.

### 4. Silent bounded recovery

NPC drafts still receive bounded repair attempts. If all attempts fail and the
scenario author did not provide an explicitly safe public reply, the agent
waits silently and the multi-party orchestrator may try another participant.
Internal fallback instructions and global governance templates are no longer
published as business dialogue.

New telemetry separates validated drafts, clause repair, configured fallback,
silent recovery, quote-level confirmation, and capability-boundary focus.

## Deterministic tests

The following passed locally:

```text
PYTHONPATH=server .venv312/bin/python -m compileall -q server/app server/tests
PYTHONPATH=server .venv312/bin/python server/tests/smoke_public_ledger.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_speech_safety.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_llm_resilience.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_research_protocol.py
git diff --check
```

The regression set covers:

- model intent mislabeled as `statement` while the quote claims containment or
  evidence capture completed;
- preservation of safe clauses when an adjacent clause invents a live action;
- normal future and conditional operational language;
- numeric values containing configured units;
- cross-turn player/counterpart confirmation with empty evaluator
  `confirmed_by` arrays;
- rejection of conditional quote-level confirmation;
- executable-field confirmation before and after a registered tool result;
- capability-boundary focus before a tool result and normal focus afterward;
- visible-current-world-action integrity probes for G3.6 archives.

## Frozen G3.5 counterexample replay

The new deterministic probes were run read-only over the eight frozen G3.5
transcripts. They found:

- two unsupported live attachment claims in RoomMind scenario 1;
- nine unsupported completed operational claims in RoomMind scenario 4;
- no such RoomMind claims in scenarios 2 and 3;
- thirteen completed operational claims and two artifact claims in Baseline
  scenario 4, plus one completed operational claim in Baseline scenario 3.

This replay shows that G3.6 detects failures that passed G3.5 ledger-shape
probes. It does not prove that new generation avoids them, and regex detection
is not a substitute for manual transcript reading.

## Gate before a frozen qualification batch

Run an isolated fixed-model probe first. Promotion requires:

1. no visible unsupported current-world completion or artifact claim;
2. typed quote-level confirmations close a simple multi-party field without
   reopening it;
3. capability-boundary fields end conditionally/deferred when no simulated
   result exists;
4. configured/public fallback templates do not dominate the transcript;
5. all deterministic probes pass and transcript hashes remain stable;
6. manual reading finds no new conversational failure severe enough to
   invalidate a matched G3.6 qualification.

Only after this probe should a new frozen four-scenario RoomMind/Baseline batch
be started. Dialogue generation, AI evaluation, and future human review remain
separate stages.
