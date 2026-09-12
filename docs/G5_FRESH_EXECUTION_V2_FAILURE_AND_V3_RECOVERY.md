# G5 fresh-family v2 failure and v3 recovery

Date: 2026-09-12

This record is development evidence, not confirmatory evidence and not an
architecture-effect estimate.

## Frozen failed execution

- Source revision: `9e411669f2c354064727ce0296d413bbb1b7e66b`
- Execution binding SHA-256:
  `247d0e2f8e400f647328c761dd8f4714dd3e3dddeb01cd062befbe6580745d68`
- Provider/model: `ollama/gpt-oss:120b`
- Remote output:
  `research/experiments/2026-09-12-g5-fresh-family-v2-online`
- Retained state at stop: one world, 14 committed public events, 232 model
  attempts, zero frozen sources and no public transcript bundle.

The runner was resumed three times against the same execution binding and
SQLite database. Each process exhausted its bounded transient retries at the
same public-event version. No state was deleted or replaced.

## Root-cause evidence

An isolated copy of the failed SQLite state replayed the pending operation with
a response-shape probe. Ollama returned HTTP 200 for the fixed model, but the
response had `done=true`, `done_reason=length`, `eval_count=2048`, an empty
assistant `content`, and 7,160 characters in `message.thinking`. The v2
transport correctly rejected that response instead of treating reasoning text
as public JSON. A separate non-experimental 9.9 KB request completed normally,
so request byte length alone was not the cause.

An isolated replay with the explicitly bound Ollama `think=low` setting
successfully completed and sealed the first 16-turn dialogue. It then exposed
a second execution defect: `OfflineAssembler.factory` assigned the constant
world ID `assembly-validation` to every assignment. The second assignment
therefore collided with the already-created first world. The isolated replay is
diagnostic only and is not part of either frozen execution.

## Versioned recovery

The recovery does not mutate or resume v2. It creates a new v3 binding and a new
output directory with:

1. an Ollama HTTP v2 transport specification that hash-binds
   `reasoning_effort=low` and sends `think=low`;
2. a deterministic world ID derived from the manifest SHA-256 and assignment
   ordinal, making all eight assignment worlds distinct and replayable;
3. the failed v2 execution SHA-256 embedded as the predecessor;
4. the same eight selected assignments, fixed model, stopping limits, external
   payload authorization and development-only classification;
5. unchanged prohibitions on evaluator scoring, the 32-dialogue architecture
   screen, confirmation study and external human review.

The complete local acceptance suite after the change ran 393 tests, including
all PostgreSQL tests, with zero failures, errors or skips. Receipt:
`docs/G5_LOCAL_ACCEPTANCE_20260912_FRESH_EXECUTION_V3_POSTGRES.json`.
