# G4.1 Qualification Results

## Frozen batch

- Batch: `a4542137-54ad-4d7c-9dc9-8f919440767e`
- Architecture: `g4.1-floor-and-speech-act-ownership`
- Source revision: `157e780d2cbdbdf6006a0e1438ce379ce166ced3`
- Dialogue and evaluator model: `ollama/gpt-oss:120b`
- Design: four scenarios, one matched RoomMind/Baseline pair per scenario,
  fixed seed `20260904`, concurrency `1`, maximum `20` turns
- Technical result: 8/8 dialogues frozen, 0 dialogue failures, 0 degraded
  LLM fallbacks
- Evaluation result: 48/48 independent dimension ratings completed after
  missing-only retries
- Provenance: all eight stored transcript SHA-256 values were recomputed and
  matched exactly

## Qualification disposition

G4.1 does **not** qualify for promotion as the next stable architecture.

The floor-handoff mechanism was active and prevented additional NPC speech 14
times across the four RoomMind runs. Near-duplicate suppression was also
observed three times, and no speech-act mismatch reached the rejection guard.
However, two of four RoomMind sessions still ended `stalled`, and manual review
found one genuine same-turn double question to the player plus a separate role
substitution in the interview. The frozen floor detector also produced two
false positives by interpreting NPC-to-NPC questions as player-directed. The
mechanism therefore improved control but neither the runtime rule nor its
measurement is yet reliable enough for promotion.

## Run-level technical results

| Scenario | Condition | Messages | Turns | Outcome | Floor handoffs | Duplicate suppressions | Failed RoomMind probes |
|---|---|---:|---:|---|---:|---:|---|
| Supply chain | Baseline | 80 | 20 | safety limit | 0 | 0 | n/a |
| Supply chain | RoomMind | 17 | 6 | completed | 0 | 0 | none |
| Product launch | Baseline | 77 | 20 | safety limit | 0 | 0 | n/a |
| Product launch | RoomMind | 54 | 20 | stalled | 2 | 1 | stalled outcome |
| Leadership interview | Baseline | 76 | 20 | safety limit | 0 | 0 | n/a |
| Leadership interview | RoomMind | 47 | 20 | stalled | 12 | 0 | stalled outcome; floor handoff |
| Incident command | Baseline | 79 | 20 | safety limit | 0 | 0 | n/a |
| Incident command | RoomMind | 50 | 17 | conditional | 0 | 2 | floor handoff |

All four RoomMind runs had zero degraded LLM fallbacks. The supply-chain,
product-launch, interview, and incident runs used respectively 1, 2, 1, and 1
safe dialogue fallbacks. Public-grounding rejection activated once in product
launch and three times in incident command.

## Independent AI evaluation (descriptive only)

| Dimension | RoomMind mean | Baseline mean | Difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 6.00 | 5.50 | +0.50 |
| Information boundaries | 5.75 | 5.50 | +0.25 |
| Temporal coherence | 5.75 | 6.00 | -0.25 |
| Interaction structure | 6.00 | 5.75 | +0.25 |
| Multi-party dynamics | 5.25 | 5.00 | +0.25 |
| Procedural fidelity | 5.75 | 5.75 | 0.00 |

These are eight development runs rated by one AI-evaluator protocol. They are
not confirmatory evidence, and no composite score is computed.

## Manual reading of all four matched pairs

### Supply-chain contract meeting

RoomMind was much shorter and reached the scenario's required price, delivery,
and quality fields in six turns. Baseline reached substantially similar terms
early but continued through 20 turns, repeatedly restating contract drafting
and sign-off. RoomMind was more efficient, but it still showed authority drift:
the procurement ally offered to forward supplier data, the quality director
volunteered a legal contact and draft, and the final analyst intervention
reopened price and liability concerns after apparent closure. This is a clear
relative improvement over Baseline, not a clean realism pass.

### Strategic product-launch meeting

RoomMind established evidence, safeguards, staffing mitigation, and a phased
decision, but later reopened budget approval and spent many turns requesting a
signed memo that could not actually be produced. It ended stalled even though
the CFO had earlier said the budget was approved. Baseline was more verbose and
continued well after substantive closure, but maintained a more stable explicit
decision path. G4.1 did not improve temporal or closure realism here.

### Cross-functional leadership interview

RoomMind asked questions sequentially more often than Baseline and the runtime
floor handoff activated 12 times. Nevertheless, it remained repetitive and
stalled after the candidate explicitly said the question portion was complete.
At turn 5, the Engineering Director asked the VP Product to answer an interview
question that should have been addressed to the candidate, which is role
substitution. At turn 9, two interviewers asked the candidate overlapping
questions in the same turn, a genuine floor violation. Baseline was even more
mechanical, with every interviewer frequently asking parallel questions and
several near-duplicate prompts, but RoomMind still fails the intended gate.

### Critical-service incident command

RoomMind produced a coherent incident sequence from scope through containment,
recovery planning, evidence preservation, and conditional closure. It was
shorter than Baseline and appropriately refused to claim a final hash result
while the simulated verification remained pending. Both conditions nevertheless
contained overly convenient simulated artifacts and procedural narration. The
frozen detector's reported turn-6 violation is a false positive: Sofia asked
Priya for a containment proposal and Priya answered; it was not a question to
the player.

## Detector adjudication

The frozen probe reported three G4.1 floor violations:

1. Interview turn 5: false positive for player-floor ownership, but genuine
   role substitution because Noah addressed Avery with a candidate question.
2. Interview turn 9: genuine violation; Maya and Avery both questioned Taylor
   in the same turn.
3. Incident turn 6: false positive; Sofia explicitly addressed Priya, whose
   response was appropriate.

This shows that addressee inference must use structured target metadata and
speaker-role context rather than punctuation and second-person language alone.

## Next architecture target

The next candidate should remain domain-neutral and make only the following
changes:

1. represent the intended addressee as a required structured speech-act field;
2. reserve the floor transactionally before any later NPC is evaluated;
3. reject role substitution when an NPC answers or redirects a task owned by a
   different participant without an explicit handoff;
4. treat prior authoritative confirmation as durable unless a public event
   explicitly reopens it;
5. allow an authorized participant's explicit completion statement to close a
   field without waiting for a redundant ceremonial response.

The G4.1 frozen artifacts remain development evidence and must not be replaced
or relabeled by later runs.
