# G3.5 Atomic Confirmation and Source-Typed Evidence Local Prequalification

## Disposition

**G3.5 passes deterministic local engineering prequalification.** It is ready
for a small, frozen real-model staging qualification, but it has not yet shown
a realism advantage over Baseline. No G3.4 result has been overwritten.

The local Ollama endpoint was not running during this check, so this document
does not claim a real-model dialogue result. A matched RoomMind/Baseline batch
with the fixed study model remains mandatory before any realism conclusion.

## Problems carried forward from G3.4

1. A participant could explicitly accept a field in public speech while the
   aggregate task-state update remained `proposed`. That individual acceptance
   was lost, so the coordinator repeatedly reopened settled issues.
2. A participant's own sentence could be treated as proof that a rollback,
   upload, health check, hash verification, or other current-world action had
   actually completed.
3. NPC speech was always regenerated after a valid public draft had already
   been produced. The second whole-message paraphrase introduced many new
   safety violations and visible fallback phrases.
4. An evaluation dimension could be marked complete from a plausible total
   score even when all required child metrics had placeholder scores, empty
   reasons, or no transcript evidence.

## Architecture changes

### 1. Atomic projection of public confirmations

Each explicit, authorized, value-grounded confirmation is now committed to the
canonical public ledger independently. The aggregate confirmation policy still
decides when a field is fully confirmed, but the first party's acceptance is no
longer discarded while the system waits for a counterpart.

This mechanism is schema-driven. It uses each field's configured type,
permissions, and confirmation policy rather than negotiation-specific field
names.

### 2. Source-typed public evidence

Public ledger evidence is divided into four sources:

- `scenario_seed`: facts introduced by the scenario engine;
- `public_statement`: what a participant publicly said;
- `simulated_tool_result`: an in-session result registered by the trusted
  simulation engine;
- `external_followup`: work promised outside the text meeting.

An agent cannot create `scenario_seed` evidence. A current-world action can
reach a terminal lifecycle only when its exact actor, field, inline result, and
`tool_result_id` match a tool result already registered by the engine. Invented
or missing result identifiers downgrade the action to a commitment and remain
visible in ledger rejections.

### 3. Publish valid public drafts directly

The decision model's `speak_draft` is now published without a second LLM call
when it passes the same lifecycle, information-boundary, private-state, and
public-evidence checks used by the renderer. Instruction-like drafts still use
the renderer. Invalid drafts retain the bounded repair and deterministic
fallback path.

When the coordinator has moved to outcome resolution and verified evidence is
insufficient, the deterministic fallback explicitly defers and records a
remaining condition and follow-up owner instead of restarting the same issue.

### 4. Structurally complete independent evaluation

An evaluation dimension is usable only when:

- the dimension score is between 1 and 7;
- every required child metric is present with a 1–7 score;
- every child metric has a non-empty reason;
- every child metric cites at least one transcript sequence number;
- every cited sequence number exists in the frozen transcript.

Malformed dimensions are retried and remain missing if retries fail. A
plausible top-level score can no longer hide placeholder child data.

## Deterministic evidence

The following commands passed under the repository's isolated Python 3.12
environment:

```text
PYTHONPATH=server .venv312/bin/python -m compileall -q server/app server/tests
PYTHONPATH=server .venv312/bin/python server/tests/smoke_public_ledger.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_speech_safety.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_llm_resilience.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_research_protocol.py
git diff --check
```

The regression set establishes that:

- player and authorized counterpart confirmations accumulate across turns and
  close a multi-party field only after the configured policy is satisfied;
- an unregistered `tool_result_id` cannot complete an action;
- a registered, actor/field/content-matched simulated result can advance the
  action under the normal monotonic lifecycle rules;
- exported G3.5 integrity probes fail when a terminal action cites a missing
  tool result and pass after the matching result is included;
- a validated natural public draft bypasses unnecessary paraphrasing, while an
  instruction-like or unsafe draft does not;
- an outcome-resolution fallback defers rather than fabricates closure;
- malformed six-dimension child structures are retried and are reported as
  missing rather than silently accepted.

`smoke_modes.py` was not executed locally because it requires the project's
PostgreSQL service, which is not available in this isolated local environment.
That is an untested integration boundary, not a passing result.

## Remaining qualification risks

1. Real-model outputs may still choose poor intent kinds or produce repetitive
   but technically valid speech.
2. The simulation currently supplies no general-purpose tool execution layer;
   therefore action completion should remain uncommon unless a scenario engine
   deliberately registers a result.
3. Direct draft publication reduces a failure source but must be measured for
   naturalness, strategy fidelity, and leakage in real transcripts.
4. Evaluator completeness is now stricter, so partial evaluation rates may rise
   even while data validity improves.

## Gate before promotion

Run one frozen matched batch across the same four open scenario types with:

- fixed provider/model and seed policy;
- one RoomMind and one Baseline run per scenario;
- dialogue generation frozen before independent evaluation;
- transcript hashes recomputed before and after evaluation;
- all G3.5 integrity probes exported;
- direct counts of confirmed-field reopening, terminal action claims,
  validation rejections, direct validated-draft use, safe fallback use, stop
  reasons, and malformed evaluator retries;
- manual transcript reading in addition to the six separate realism dimensions.

Do not start external human review unless that qualification shows both
engineering validity and a credible improvement in conversational realism.
