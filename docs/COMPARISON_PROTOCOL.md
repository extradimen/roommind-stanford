# RoomMind controlled comparison protocol (v3)

## Simulation realism evaluation

The persisted workflow has four stages: autonomous dialogue generation,
condition-blinded AI evaluation, condition-blinded human review, and final
six-dimension reporting. Dialogue generation and AI evaluation are separate
jobs: dialogue is frozen and exportable before evaluation begins, and evaluator
failure never changes the dialogue outcome. The same frozen transcript can be
re-evaluated under a new protocol or model without regenerating it. Evaluation is restricted to simulation realism;
learning outcomes, task cost, latency, token use, and task success are not
treated as realism measures.

The six dimensions are reported separately on a 1–7 scale: role and strategic
fidelity, epistemic fidelity, temporal coherence, interaction-structure
fidelity, multi-party dynamics fidelity, and procedural fidelity. Every AI
metric cites public transcript sequence evidence. Human reviewers receive
anonymous run codes, a fixed 20-turn window, and the full transcript, but never
the RoomMind/baseline condition. AI and human scores remain separate and no
composite realism score is computed.

Public dialogue exports support statistical and qualitative analysis. The
forensic debug bundle additionally contains internal memories, decisions,
state, evaluation details, and performance traces and must not be given to
blinded reviewers.

The batch experiment compares two implementations under the same public case,
AI player policy, platform model, history window, maximum player turns, run
order randomization, and blinded external evaluator.

## Conditions

- **RoomMind**: independent per-role memory streams, role planning/reflection,
  responsibility-based dispatch, authority enforcement, structured task state,
  and completion checks.
- **Traditional independent-agent baseline**: one model agent per NPC, each
  receiving its own role prompt, private profile, participant roster, and
  separately persisted rolling public conversation history. Agents independently
  choose `speak` or `wait`. They have no structured observation, reflection,
  planning, semantic memory retrieval, runtime dispatch, authority enforcement,
  structured task state, evidence gate, or system completion correction.

Both conditions receive the same public case material, and private profiles are
partitioned by role in both conditions. The experimental difference is that the
baseline stops at conventional per-agent rolling chat memory, while RoomMind
adds structured cognition and governance mechanisms.

In batch comparisons both conditions call the exact same public-only AI player.
The player cannot read RoomMind task state, phases, plans, memories, or baseline
internals. Provider/model overrides are disabled so all calls inherit the active
platform model. Condition order is randomized with a stored seed.

## Primary automatic outcomes

1. Externally validated completion rate
2. Premature completion rate
3. Authority violation rate
4. Responsible confirmer rate
5. Agreement retention rate
6. Cross-role knowledge contamination rate

Secondary automatic outcomes are responsibility match rate, distinct
contribution rate, semantic repetition rate, turns to externally valid
completion, protected-secret leakage rate, and technical failure rate.

Only facts explicitly classified as `protected_secrets` count as protected.
`discoverable_information`, `role_disclosable_information`, goals, personas,
and ordinary redlines are not automatically treated as leaks.

## Optional human validation

Human review is disabled by default and is not required for the primary
analysis. When enabled, the system exports condition-hidden packets for 1–5
ratings of role believability, realism of multi-participant conflict, and
perceived coherence. Human ratings should be reported separately as validation
of the automated protocol, not merged into a composite score.
