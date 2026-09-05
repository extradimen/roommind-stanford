# G3.4 Natural Recovery and Bounded Evidence Local Prequalification

## Objective

Preserve the G3 public ledger, independent memories, authority checks, and
lifecycle ordering while removing governance language and external-artifact
deadlocks from public conversation.

## Architecture changes

1. NPC recovery uses the validated subject and ordinary role language; it does
   not expose field identifiers, `remains open`, or `responsible owner`.
2. An unavailable external file becomes a post-meeting deliverable. Participants
   must state substantive evidence inline and proceed to a conditional outcome,
   explicit deferral, or handoff rather than repeat an upload request.
3. The shared comparison player uses the latest public question to form a
   contextual recovery response. Retrospective fallbacks respond to the type of
   interview question rather than repeat one universal story.
4. Questions are not affirmative evidence. Evidence-attribution language is
   rejected when the public record contains only questions or confirmation
   requests; cautious statements that evidence is insufficient remain valid.
5. `dialogue.safe_fallback.used` is exported separately as
   `dialogue_safe_fallback_count`, so safe deterministic speech is no longer
   hidden behind a zero degraded-LLM-fallback count.

## Current local evidence

- LLM resilience, speech safety, research protocol, compileall, and diff checks
  pass under the isolated Python 3.12 environment.
- Real-model probe: `ollama/gpt-oss:120b-cloud`.
- The NPC gives a natural inline summary and records the signed security report
  as follow-up; forced empty-model recovery uses the same bounded semantics.
- A first probe caught the player converting a confirmation question into the
  invented claim that rollback was complete and monitoring showed no anomalies.
  A deterministic question-versus-evidence guard was added and regression-tested.
- A later probe caught the inverse boundary error: `we still need confirmation
  that the checksum has been verified` was mistaken for a completed checksum
  claim. Confirmation-request grammar is now explicitly non-assertive and has a
  deterministic regression case.
- The probe remains engineering prequalification only. It does not establish a
  RoomMind advantage and is not a substitute for a frozen matched-pair batch.

## Gate before staging

- all offline tests pass;
- no fallback contains internal field names or orchestration vocabulary;
- no question-only record becomes an affirmative status or metric;
- external artifact requests converge to inline evidence plus one follow-up;
- safe fallback use is observable;
- a local multi-turn sample shows no repeated universal recovery line.
