# G1.1 main exploration disposition

## Frozen identity

- Batch UUID: `86f74b31-22ba-4af2-a4a9-7513eb5cce1b`
- Generation: `G1`
- Architecture: `g1.1-resilient-governed-agents`
- Source revision: `ef8c4f7e24f9ebec963be5864f8e638ff1f0af31`
- Model in both conditions and in the independent evaluator: `ollama/gpt-oss:120b`
- Study phase: exploration (`development_only`)
- Design: 4 scenarios × 2 conditions × 3 repetitions = 24 runs / 12 matched pairs
- Baseline: independent conventional role agents with per-agent rolling public-history memory
- RoomMind: independent structured-memory agents plus planning, reflection, dispatch,
  authority, evidence-grounded state, work-item and convergence governance

## Engineering validity

- 24/24 dialogues completed; no dialogue run failed or was cancelled.
- 24/24 independent six-dimension evaluations completed after one targeted retry.
- 24/24 deterministic integrity probes passed.
- All 24 canonical public transcripts had present and unique SHA-256 values.
- No empty public message, unknown public speaker, prior attempt session, or degraded
  dialogue fallback was recorded.
- One provider read timeout and 88 length-recovery events occurred; all recovered.
- Human blind review was not started.

This establishes that G1.1 repaired the engineering-invalid G1 pilot. It does not
establish superior simulation realism.

## Six-dimension exploratory results

Scores use the registered 1–7 AI rubric. AI and future human scores remain separate;
no composite realism score is computed.

| Dimension | RoomMind mean | Baseline mean | Paired mean difference |
|---|---:|---:|---:|
| Role and strategic fidelity | 5.50 | 5.83 | -0.33 |
| Epistemic fidelity | 5.33 | 5.75 | -0.42 |
| Temporal coherence | 5.33 | 5.75 | -0.42 |
| Interaction-structure fidelity | 5.50 | 5.75 | -0.25 |
| Multi-party dynamics fidelity | 5.25 | 5.25 | 0.00 |
| Procedural fidelity | 4.83 | 6.08 | -1.25 |

Matched RoomMind win / tie / loss counts were respectively 2/6/4, 1/5/6,
4/3/5, 2/6/4, 4/4/4, and 3/1/8 in the table order. Only procedural fidelity
showed an exploratory paired Wilcoxon result below 0.05 (`p≈0.046`), in the
Baseline direction. With 12 matched pairs and development reuse, this is diagnostic,
not confirmatory evidence.

## Failure mechanism discovered

RoomMind preserved role and authority constraints but frequently failed to convert
conversation into task progression:

- 11/12 RoomMind sessions ended through a governor stop: seven safety-limit stops
  and four no-progress stops. Only one reached a natural completion state.
- Baseline had eight natural completions and four safety-limit stops.
- Promised artifacts or actions remained pending across multiple turns while agents
  repeated future delivery language.
- Confirmed matters could be reopened by later extracted proposals.
- Speaker ordering used mention/keyword routing but did not prioritize the owner of
  the current unresolved work item.
- The governor detected stagnation after it occurred but did not coordinate one
  final execution, blocker, handoff, or truthful closure step before stopping.

The procedural deficit therefore motivates a new generation. It is not appropriate
to continue prompt-only tuning inside G1.1 or to submit this batch as confirmation
evidence.

## Disposition

G1.1 is frozen as a technically valid exploratory generation whose realism
hypothesis was not supported. G2 changes the causal turn lifecycle by adding a
deterministic focus/ownership coordinator, commitment ageing, settled-item locking,
and structured closeout. G1.1 transcripts and ratings must remain unchanged and must
not be pooled with G2 evidence.
