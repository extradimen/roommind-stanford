# G4.3 Cross-role Floor and Evidence-boundary Prequalification

## Research status

G4.3 is an exploratory successor to the failed G4.2.1 qualification. It is a
new architecture candidate, not evidence that RoomMind is more realistic. A
new matched and frozen experiment is required before making that claim.

## Evidence motivating this iteration

Manual reading of all four frozen G4.2.1 RoomMind/Baseline pairs found two
recurrent failures that aggregate scores did not expose reliably:

1. The autonomous player sometimes answered a question addressed to another
   participant, supplied that role's figures, or confirmed facts on its behalf.
2. Participants could present an in-session report, certificate, log,
   measurement or operational status as if it already existed, although no
   simulated tool result had established it.

These failures weakened role separation, information boundaries and the
causal link between evidence and commitment. They were not specific to a
single negotiation, interview, launch or incident scenario.

## Changes from G4.2.1

1. **Public participant directory.** The autonomous RoomMind player and the
   controlled Baseline player resolve visible names and role labels against the
   same public-only participant aliases. No NPC private state is exposed.
2. **Cross-role question ownership.** A direct NPC-to-NPC question remains
   assigned to the addressed role. The orchestrator prioritizes that role in
   the current or next NPC pass. If the player gets the floor first, it may
   briefly hand off but may not answer, confirm, promise, or provide evidence
   for the addressed role.
3. **Resolved-question cleanup.** Once the addressed NPC has spoken, the
   question is no longer treated as pending in the next player turn.
4. **Live evidentiary artifact boundary.** A purported current-session report,
   certificate, invoice, log, measurement or test result requires a registered
   accepted simulated-tool result. Ordinary proposals, agendas, checklists and
   drafts may still be composed in dialogue.
5. **Expanded current-world action normalization.** Claims such as an action
   "remains active" or a rule "was applied" are treated as terminal world-state
   assertions and require tool grounding.
6. **Independent forensic probe.** Frozen G4.3 exports deterministically report
   whether a player intercepted an NPC-directed question instead of yielding
   it to the responsible role.

The independent agent memories, perception, retrieval, planning, reflection,
action loops, task coordinator and six-dimension external evaluation remain
unchanged. Both comparison conditions keep the same public scenario and player
information. Baseline does not receive RoomMind's governance mechanisms.

## Local gates

1. Public-ledger, research-protocol, speech-safety/task-state and LLM-resilience
   smoke suites pass.
2. A visible NPC-to-NPC question is assigned to the registered target.
3. The targeted NPC is retained in pending response priority if it cannot speak
   immediately.
4. The player may issue a short explicit handoff to the target.
5. A player response that first confirms the target's fact is rejected as role
   substitution even if it later asks the target to add detail.
6. An answered NPC-to-NPC question is removed from pending player context.
7. Unsupported live evidentiary artifacts and normalized terminal action claims
   are rejected; ordinary inline drafts remain permitted.
8. Application and test modules compile and whitespace validation passes.

The database-dependent `smoke_modes.py` additionally requires the PostgreSQL
test service and is therefore reserved for the deployed staging qualification.

## Frozen experiment design

After source revision and deployment are explicitly authorized, create a new
G4.3 exploration batch rather than retrying or mutating G4.2.1. Use the same
four matched scenarios, fixed `ollama/gpt-oss:120b` provider/model, seed policy,
turn limits and dialogue concurrency used by the preceding qualification.

Freeze all eight transcripts first. Then run the independent six-dimension AI
evaluation with concurrency one, recompute transcript hashes, inspect all
integrity probes, and manually read every RoomMind/Baseline pair. Do not start
external human review automatically.

## Qualification decision rule

G4.3 fails qualification if any dialogue has a technical failure, a RoomMind
run ends stalled, transcript provenance does not verify, the new cross-role
ownership probe fails, unsupported current-world evidence survives, or manual
reading finds that the new controls merely replace natural dialogue with
repetitive handoff language. Passing mechanism gates is necessary but not
sufficient: the paired transcripts must also show a credible qualitative
improvement in role, epistemic, interaction and procedural fidelity.
