# Design revision proposal after G4.15

This proposal supplements all historical reports. The evidence and corrections
are recorded in `research/audits/2026-09-09-design-review/README.md`.

## Preserve the research question

Continue studying realistic multi-party interaction with independent role
memory and a shared public world. Retain separate dialogue generation and
evaluation, immutable transcripts, six separate realism dimensions, matched
conditions, and distinct exploration/screening/confirmation stages.

Do not identify successful operational execution with realism. A reasonable
decision to defer can be realistic. Also do not accept a fabricated operational
success merely because it makes the conversation appear productive.

## Required decision: what can the simulated world do?

The incident scenario asks participants to activate containment, but the
production path inspected does not register execution results. There are two
coherent ways to resolve that mismatch; they answer different research questions.

### Recommended: bounded internal simulation executor

Retain the operational objective. Add a deterministic, scenario-configured
world executor for a small set of declared actions such as containment. No
real infrastructure or external customer system is affected.

- Inputs: authorized actor, action, declared parameters, prerequisite state,
  and an idempotent request id.
- Outputs: success, failure, or blocked, plus immutable result id, actor,
  operation, object, time, and supplied evidence. Do not always return success.
- Both conditions receive the same capability, initial world state, action
  contract, and public result visibility. RoomMind's governance is the
  treatment; access to a functioning world must not be an accidental treatment.
- Freeze a new scenario/world snapshot and experiment protocol version. This
  comparison cannot be pooled with old no-executor batches as the same design.

### Alternative: discussion and decision simulation only

Keep execution outside the meeting. Replace future scenario success criteria
such as activated containment with authorized plan approval, ownership,
prerequisites, and handoff. Record external actions as pending, never executed.
This is simpler but changes the meaning of the operational scenario and the
claimed capability of the system. Preserve the original scenario unchanged;
create a new version for the different objective.

## Implementation contract after that decision

### Evidence

Separate immutable scenario facts, role-visible seed facts, participant claims,
proposals/commitments, and executor results. Each fact has provenance and
visibility. A participant claim does not become world truth by repetition.
Check exact actor/action/object/value correspondence when citing execution
evidence. A legitimate seed fact requires no invented tool invocation. Never
broaden one role's private visibility to solve grounding failures.

### Response and termination

Maintain one persistent response queue with request id, source public message,
source actor, ordered recipients, pending/answered/blocked status, and answer
message references. Ambient speech cannot consume an outstanding answer slot.
A blocked answer is explicit; it is not silently counted as substantive
completion. Preserve unanswered recipients when handing the floor to the
player. Bound nested requests without losing or duplicating them.

Session termination must be checked before any player/NPC model call and before
publication. Completion is monotonic and cannot be undone by a fallback or a
newly generated question. Candidate question phase is not itself a finished
session: legitimate candidate follow-up is allowed until explicit closure.
Prevention must cover normal speech, repair, fallback, restart, and persistence.

### Validation independent of generation guards

- Table-driven event traces with independently specified expected speakers,
  queue states, evidence visibility, and terminal state.
- End-to-end mocked model decisions that deliberately choose the wrong actor,
  wait, emit unsafe content, and fail; check persisted public messages.
- Restart/idempotency cases, including unanswered multi-recipient requests.
- Known G4.15 counterexamples plus unseen paraphrases and legitimate negative
  controls, including truthful seeded facts and realistic deferred outcomes.
- Report recognition tests separately from prevention tests. Never treat old
  transcript reclassification as a regenerated behavioral improvement.

## Next experiment contract

Use a small development panel to debug mechanisms, then freeze the candidate
and evaluate repeated runs and held-out cases under a predeclared design.
Determine sample size from the intended precision rather than inventing a
universal minimum. Report six dimensions separately, technical failures,
coverage, and concrete invariant violations. Do not use the pooled realism
mean as an added qualification gate. Separate assistant audits, model judging,
and external human ratings; do not claim independent human review occurred.

Snapshot full initial scenario/role definitions and world capabilities in the
new manifest, while retaining appropriate private-data access boundaries.
Snapshot the shared player policy and generation/evaluator configuration too.
Record model request settings and distinguish run-order seeds from model
sampling seeds. Preserve every unsuccessful run and all previous artifacts.

## Status

Design review and preservation inventory are complete. Runtime changes and a
new batch depend on selecting the simulated-world capability above. No new
generation has been registered or deployed by this proposal.
