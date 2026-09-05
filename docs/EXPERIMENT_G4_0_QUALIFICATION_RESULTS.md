# G4.0 Qualification Results

## Frozen batch

- Batch: `62e609c4-8364-4a47-8d55-19bd8aa28144`
- Architecture: `g4.0-bounded-agenda-convergence`
- Dialogue and evaluator model: `ollama/gpt-oss:120b`
- Design: four scenarios, one matched RoomMind/Baseline pair per scenario
- Technical result: 8/8 dialogues frozen, 0 dialogue failures, 0 degraded LLM fallbacks
- Evaluation result: 48/48 independent dimension ratings completed after missing-only retries
- Provenance: all eight transcript hashes recomputed exactly

## Deterministic disposition

G4.0 did not qualify for promotion. Three RoomMind transcripts passed all G4
integrity probes, but the incident-command transcript retained three
same-speaker near-duplicates (player sequences 30 and 37; SRE sequence 33).
The configured suppression counter was zero, showing that the published
duplicates bypassed the candidate-output guard through deterministic fallback
paths.

All four RoomMind sessions avoided `stalled` and ended with truthful conditional
outcomes. This confirms the bounded-convergence mechanism worked as a state
governor, but it does not establish superior realism.

## Independent AI evaluation (descriptive only)

| Dimension | RoomMind mean | Baseline mean |
|---|---:|---:|
| Role and strategic fidelity | 5.25 | 6.25 |
| Information boundaries | 4.25 | 5.75 |
| Temporal coherence | 5.50 | 5.50 |
| Interaction structure | 5.00 | 5.25 |
| Multi-party dynamics | 5.25 | 5.50 |
| Procedural fidelity | 4.25 | 5.75 |

These scores are development evidence, not confirmatory findings.

## Manual paired reading

- **Supply chain:** RoomMind was shorter and more coherent than Baseline, which
  reopened settled terms and introduced severe arithmetic contradictions.
- **Product launch:** RoomMind maintained conditionality around staffing and
  budget; Baseline continued long after a decision and contradicted its own
  claims about a signed budget email.
- **Leadership interview:** RoomMind was worse. After the interviewer asked the
  candidate for a behavioral example, the Engineering Director answered in the
  first person as though he were the candidate. The private reasoning said to
  prompt the candidate, so this was a speech-act and floor-ownership failure.
- **Incident command:** both conditions were weak. RoomMind reduced unsupported
  live-action claims but repeated closure prompts and assigned work to an
  implausible role.

## Root causes carried into G4.1

1. Deterministic fallback text was not passed through the same near-duplicate
   gate as model-generated text.
2. The orchestrator continued polling later NPCs after one participant directly
   asked the player a question.
3. No deterministic check compared an agent's intended speech act with the
   public utterance it produced.

Accordingly, G4.1 is limited to generic floor ownership, speech-act consistency,
and fallback safety. It does not introduce scenario-specific dialogue rules.
