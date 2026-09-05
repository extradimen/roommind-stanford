# G3.8 Authoritative State Reducer and Closure Lock Prequalification

## Disposition

**G3.8 passes deterministic component prequalification.** It directly replays
the public confirmation forms and closure-state split observed in the frozen
G3.7 batch. It has not yet passed a database-backed end-to-end mode test or a
matched real-model RoomMind/Baseline experiment, so it is not qualified as a
realism improvement and must not replace the frozen G3.7 evidence.

## Frozen G3.7 failures used as counterexamples

1. `I can confirm the product evidence you shared` did not create an accepted
   field event because the parser recognized `I confirm` but not `I can
   confirm`.
2. `I hereby approve the recovery plan` and natural schedule/assignment
   decisions were outside the narrow acceptance grammar.
3. `That covers the people-leadership evidence we need` completed a work item
   but did not confirm the corresponding completion variable.
4. Candidate questions, product evidence, and engineering evidence could be
   publicly closed while their aggregate variables remained `unknown` or
   `proposed`.
5. Extractor-created optional work remained required after all configured
   completion fields were defensibly satisfied.
6. The coordinator therefore rotated among stale fields and follow-ups until
   stagnation or the safety limit.

## Architecture changes

### 1. Expanded but bounded professional confirmation grammar

The deterministic quote projector now recognizes ordinary business acceptance
forms including `can confirm`, `hereby approve`, `consider ... complete`,
`covers/satisfies/meets the evidence`, and explicit setting, assignment, or
designation language. Questions, conditional wording, negation, unauthorized
speakers, and executable fields without registered simulated-tool results
remain rejected.

### 2. Canonical string-entity grounding

Named assignee values may be grounded by a distinctive value token plus a
reference to the configured field. This allows `Sofia` in a public assignment
statement to ground the configured value `Sofia Martinez` without permitting a
field-free arbitrary string update.

### 3. Authoritative field/work reconciliation

Configured completion fields are now evaluated before derived work items.
Required work whose subject, key, or criticality evidence overlaps a confirmed
field or a persisted unavailable capability boundary is retained for audit but
removed from the closure graph. This eliminates the G3.7 state in which
`product_evidence` work was complete while `product_evidence` remained an
independent unresolved blocker.

### 4. Deterministic closure lock

When every configured completion condition is satisfied, the reducer records a
`closure_lock` containing the resolved fields and demotes any remaining
extractor-created required work. Later generic event extraction cannot promote
new required work while the lock is active. Only an authorized field challenge
or condition change can reopen it.

### 5. Research observability

Public task exports now include the closure lock. Batch summaries report whether
the authoritative lock was reached and how many work items were reconciled.
The G3.8 integrity probe requires a completed RoomMind session to have a locked
closure, nonempty satisfied condition results, and no unresolved required work.

## Deterministic verification

The following checks pass in the isolated Python 3.12 environment:

```text
PYTHONPATH=server .venv312/bin/python server/tests/smoke_speech_safety.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_public_ledger.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_research_protocol.py
PYTHONPATH=server .venv312/bin/python server/tests/smoke_llm_resilience.py
PYTHONPATH=server .venv312/bin/python -m compileall -q server/app server/tests
git diff --check
```

The first replay uses the exact G3.7-style product, engineering, leadership,
and candidate-question confirmation forms. All four fields reach their
configured confirmation policies, the task completes, the closure lock is
installed, and an optional KPI-dashboard work item cannot keep the meeting
open. A second incident-command replay confirms the recovery plan, named
communications owner, and 20-minute review point while keeping executable
containment unconfirmed without a registered tool result. The sole remaining
capability boundary produces a truthful `conditional` outcome instead of a
stalled loop. Work reconciliation also requires two overlapping field terms
for multi-token fields so a generic word such as `review` cannot close an
unrelated obligation.

`smoke_modes.py` could not run because no PostgreSQL server is listening at the
local configured address `127.0.0.1:5432`. This is an environment prerequisite,
not a failing assertion. A database-backed end-to-end test remains required
before deployment.

## Gate before a real-model matched batch

1. Run the database-backed participation/test/baseline mode smoke test.
2. Replay exact G3.7 incident assignment, approval, and review-time clauses and
   verify that non-executable fields close while containment remains a truthful
   capability boundary without a simulated result.
3. Require nonzero quote-confirmation commits in at least the scenarios whose
   transcripts contain explicit authorized confirmations.
4. Require public field state, work-item state, and completion state to agree.
5. Require every RoomMind run to end `completed`, `conditional`, `deferred`, or
   `failed`, not `stalled`.
6. Freeze and manually read every matched RoomMind/Baseline transcript before
   any external human review.
