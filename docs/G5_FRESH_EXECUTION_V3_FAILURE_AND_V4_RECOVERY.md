# G5 fresh-family v3 failure and v4 recovery

Date: 2026-09-12

This record concerns development execution reliability only. It is not
confirmatory evidence and does not estimate any architecture effect.

## Frozen failed v3 execution

- Source revision: `5f2124bcf0d8c2bb9df62be4027393f118d76830`
- Execution SHA-256:
  `e92158edd584ac8c0152d38c20e762bbd9860e6fe6e7c45590aaa8820c3c9071`
- Provider/model: `ollama/gpt-oss:120b`, `reasoning_effort=low`
- Retained state: two worlds, 16 events, 152 model attempts, one freeze.
- Frozen source: `library-space-allocation-v1`, arm A, 16 turns,
  SHA-256 `2286163150c7c6fd786cddfa00b3401e109d4ec221e17b113cc2dc9a60472c3e`.

The low-reasoning and unique-world changes solved both v2 defects: the first
dialogue sealed and the second world was created separately. Generation then
stopped before the second world's first event because repeated hierarchical
plan updates omitted required evidence IDs. The strict validator raised
`Plan source required`. Treating that output as valid or injecting an arbitrary
source ID would weaken the epistemic contract, so v3 was frozen as failed.

## Versioned v4 recovery

V4 keeps the same low-reasoning transport and unique world identity. It adds a
hash-bound `g5-plan-validation-feedback-v1` protocol with at most two plan
revisions. A rejected structured plan is not normalized or silently repaired.
Instead, the fixed validator error and a correction instruction are returned to
the same fixed model. The replacement must cite only IDs already present in
`memory.retrieved` and pass the complete existing validator. Rejected response
hashes and validation errors are retained as cognition generation receipts.

The full local acceptance suite ran 395 tests, including PostgreSQL integration,
with zero failures, errors or skips. Receipt:
`docs/G5_LOCAL_ACCEPTANCE_20260912_FRESH_EXECUTION_V4_POSTGRES.json`.

V4 requires a new source revision, execution binding and output directory. It
must embed the v3 execution SHA-256 as its failed predecessor. It remains limited
to the same eight development dialogues and does not authorize evaluation,
48-item scoring, 32-dialogue screening, a confirmation study or external review.
