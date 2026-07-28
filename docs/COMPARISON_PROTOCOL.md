# RoomMind controlled comparison protocol (v2)

The batch experiment compares two implementations under the same public case,
AI player policy, platform model, history window, maximum player turns, run
order randomization, and blinded external evaluator.

## Conditions

- **RoomMind**: independent per-role memory streams, role planning/reflection,
  responsibility-based dispatch, authority enforcement, structured task state,
  and completion checks.
- **Prompt baseline**: one centralized model call, one shared public transcript,
  and one prompt containing the same total scenario and character material. It
  has no independent role memory, runtime dispatch, authority enforcement,
  structured task state, or external completion gate.

The baseline therefore receives the same total case information, but all role
information is held by one centralized model. RoomMind partitions private
information by role. That partitioning is an experimental mechanism, not an
input-data advantage.

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
