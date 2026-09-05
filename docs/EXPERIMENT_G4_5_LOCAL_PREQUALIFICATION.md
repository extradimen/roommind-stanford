# G4.5 Obligation-Graph Governance Local Prequalification

## Research status

G4.5 is a local exploratory successor to the failed G4.4 realism
qualification. It is not deployed and does not establish that RoomMind is more
realistic than the baseline. A new frozen fixed-model matched batch is required
before any qualification claim.

## Evidence motivating this iteration

The frozen G4.4 dialogue and independent evaluation showed that isolated
safety boundaries were active, but they did not reliably produce a coherent
meeting outcome. In particular:

1. launch-readiness confirmations were asserted, contradicted and later treated
   as settled without one explicit shared closure contract;
2. responsibility could remain with a relevant but unauthorized role;
3. different speakers could paraphrase the same request or status without
   adding evidence;
4. the coordinator knew open fields, but not the exact missing confirmation for
   each configured completion condition.

## Architecture changes

1. **Deterministic meeting obligation graph.** Every configured completion
   condition is projected into an auditable obligation with group semantics,
   observed value/status, authorized confirmers, missing confirmers and a stable
   obligation identifier. This is derived only from scenario configuration and
   public task state.
2. **Explicit lifecycle and reopening.** Obligations transition among pending,
   satisfied, reopened and conditionally closed. A later authorized
   contradiction that invalidates a satisfied field reopens the obligation and
   is recorded instead of being hidden by an earlier closure claim.
3. **Exact owner routing.** The coordinator routes an unresolved condition first
   to the still-missing authorized NPC confirmer. Joint policies retain the
   player's separate confirmation requirement and do not let an NPC substitute
   for it.
4. **Capability-bound assignment guard.** A field-level handoff cannot create a
   public-ledger transition whose target is outside the obligation's configured
   confirmer set. Ordinary addressees on decisions or evidence statements are
   not misclassified as assignees.
5. **Cross-role obligation repetition boundary.** A participant cannot publish
   a near-identical question or status paraphrase already spoken by another
   role for the same coordinator focus. A new authorized acceptance,
   verification, submission, rejection or blocker is preserved as material
   progress.
6. **Independent probes and telemetry.** Exports now audit obligation graph
   presence, open-set reconciliation, completion reconciliation, authorized
   targets and cross-role obligation repetition. Telemetry separately counts
   obligation transitions, reopenings and duplicate suppression.

The independent Stanford-style memory, perception, retrieval, plan, reflection
and action loop remains intact. Scenario scripts, model selection, baseline
architecture and the six realism dimensions are unchanged; therefore the new
candidate isolates governance of public multi-role obligations.

## Local verification gates

Before deployment, G4.5 must pass:

1. all backend smoke suites and application compilation;
2. both frontend production builds;
3. database-backed dual-session regression;
4. positive and negative tests for joint confirmation, reopening, authorized
   obligation targets and cross-role duplicate suppression;
5. no regression in G2--G4.4 deterministic probes;
6. a local fixed-scenario pre-experiment, followed by manual reading, before
   requesting permission to push and deploy.

## Local verification completed

The implementation passes the LLM-resilience, public-ledger,
research-protocol and speech-safety/task-state smoke suites; Python application
import and compilation; both frontend production builds; `git diff --check`;
and the PostgreSQL-backed dual-session regression. Tests cover all-only and
any-only obligation contracts, joint confirmation, authorized reopening,
player-only outstanding confirmation, capability-bound handoff and the
difference between a real accepted transition and a rejected model label.

A deterministic counterfactual replay projected the four frozen G4.4 RoomMind
terminal task states through the G4.5 graph. It reconciled the recorded and
derived open sets in all four cases and selected the unresolved configured
condition rather than a generic closeout topic: Quality Director confirmation
in negotiation, the player's own launch-decision confirmation, Engineering
Director evidence in the interview, and the existing containment capability
boundary in incident command. The independent repetition probe also recovered
two real cross-role supplier restatements in the G4.4 negotiation (public
message sequence 28 and 31), showing that the new boundary targets an observed
failure rather than a fabricated fixture.

This replay is mechanism evidence only. It cannot establish dialogue
naturalness or a treatment advantage because it does not regenerate dialogue
under G4.5. The repository intentionally contains no local LLM credential, so
the fixed-model matched dialogue pre-experiment remains pending; no server
credential was copied into the development checkout.

## Future matched qualification

If local gates pass and deployment is explicitly authorized, create a new G4.5
batch rather than modifying or retrying G4.4 artifacts. Use the same four
scenarios, fixed `ollama/gpt-oss:120b` provider/model, matched seeds, turn
limits, player policy and concurrency. Freeze all eight dialogues before
independent evaluation. External human review must not start automatically.
