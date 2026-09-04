# G4.2 Grounded Addressee and Confirmation Prequalification

## Research status

G4.2 is an exploratory successor to the failed G4.1 qualification. It addresses
two interface failures observed in the frozen G4.1 traces. It must not be
described as more realistic until a new matched, frozen experiment is complete.

## Evidence motivating this iteration

1. Ordinary NPC questions did not retain `public_intent.target_id` unless they
   also committed a public-ledger event. The forensic export therefore lost the
   model's addressee metadata and both runtime and probes had to guess from text.
2. The G4.1 name detector recognised full directory labels but not the common
   given-name form used in live dialogue. This produced false player-floor
   handoffs for questions addressed to another NPC.
3. In two stalled RoomMind runs, the authorized closing speaker generated a
   clear public confirmation, but its generic structured intent disagreed with
   the stronger wording. Speech safety correctly refused the mismatch, yet the
   result was silence and an unresolved completion field.

## Changes from G4.1

1. **Durable public intent.** Every spoken NPC reply retains its grounded public
   intent, including questions and statements that do not create ledger events.
2. **Grounded addressee contract.** Visible named address in the public quote is
   resolved against registered participant aliases and takes precedence over
   stale model metadata. Given names are supported. The reconciled target is
   persisted before the reply is exported.
3. **Transactional player-floor handoff.** The orchestrator ends NPC selection
   only when the resolved target is the player. NPC-to-NPC questions stay in the
   same turn and the intended role may answer.
4. **Authorized confirmation alignment.** An unconditional first-person
   confirmation may be upgraded from a generic intent to `accepted` only when
   it maps to exactly one already-valued field in the speaker's configured
   `can_confirm` authority. Questions, conditional language and missing values
   cannot be upgraded.
5. **Observability and probes.** Traces count addressee reconciliation and
   confirmation alignment. G4.2 adds a frozen probe for divergence between the
   structured target and the public quote.

The independent-memory, perception, planning, reflection and action loops are
unchanged. These mechanisms repair the public interface between those agents,
the shared task state and the transcript.

## Local gates

1. Existing speech-safety, research-protocol and LLM-resilience smoke suites
   pass.
2. A named NPC addressee overrides stale `target_id=user` metadata.
3. A player given name still resolves to the player.
4. A clear authorized confirmation of an existing value aligns to an accepted
   field transition.
5. A conditional confirmation remains non-terminal.
6. Application and test modules compile; whitespace validation passes.

## Frozen experiment design

Use the same four matched scenarios, fixed provider/model, seed policy,
concurrency and turn limits as G4.1. Dialogue generation is frozen before
independent six-dimension evaluation. Human review remains separate and is not
started automatically.
