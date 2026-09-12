# G5 fresh-family v4 failure and v5 recovery

Date: 2026-09-12

This record concerns development execution reliability only. It is not
confirmatory evidence, scorer validation or an architecture-effect estimate.

## Frozen failed v4 execution

- Source revision: `f617c8697bc9a50b96514d89b51205a840a9c28c`
- Execution binding SHA-256:
  `3fd2adfe9c3eeea8942c2b69dd957422cb82034e141838ab6700826f30f21868`
- Failed predecessor SHA-256:
  `e92158edd584ac8c0152d38c20e762bbd9860e6fe6e7c45590aaa8820c3c9071`
- Provider/model: `ollama/gpt-oss:120b`, `reasoning_effort=low`
- Retained state: four distinct worlds, 63 events, 860 model attempts, three
  freezes and three verified internal source bundles.

V4 completed the first three 16-turn dialogues. On version 15 of the fourth
world (`research-data-release-v2`, arm D), generation, governance, session
annotation and question annotation all returned model receipts. The 313-byte
question-annotation response then failed the deterministic pre-commit projection
with `Invalid question targets`. No invalid event was committed. The worker exited
and was not restarted because this was not a transient provider interruption.
`transcripts.json` was never produced.

The binding, SQLite database, log and three sources were downloaded over encrypted
SSH into `research/experiments/2026-09-12-g5-fresh-family-v4-failed-online`.
Remote/local SHA-256 values match, the SQLite integrity check passes, and every
source seal verifies. The append-only attempt journal retains request/response
hashes and byte counts but not the rejected raw annotation body, so retrospective
diagnosis cannot claim its exact invalid target value.

## Versioned v5 recovery

V5 retains v4's bounded plan repair and adds a shared, hash-bound
`g5-question-validation-feedback-v1` protocol with at most two question-annotation
revisions. Each candidate is validated before commit against the final public
speech, registered participant IDs and the existing question projection. Invalid
targets, spans, fields, responses or question IDs are rejected. The fixed error is
returned to the same fixed model, and the model must correct only the annotation
using supplied IDs. The public speech is never rewritten by this repair.

Successful recovery evidence records the rejected request/response hashes and
validator errors alongside the accepted annotation receipt. If all revisions fail,
the pending event remains uncommitted and the attempt journal records all bounded
model I/O metadata. Offline assembly reconstructs the bound revision limit, so a
replay cannot silently disable or expand it.

The complete local G5 acceptance suite ran 400 tests, including PostgreSQL, with
zero failures, errors or skips and unchanged source. Receipt:
`docs/G5_LOCAL_ACCEPTANCE_20260912_FRESH_EXECUTION_V5_FINAL2_POSTGRES.json`, SHA-256
`6e29726e60f4ab5e0b9deb883882ee298a77d23c4b10c6ac0cf8d7ff496a3759`.
The local handoff `docs/G5_LOCAL_HANDOFF_20260912_FRESH_EXECUTION_V5_FINAL2.json`
covers 1,231 research files and verifies with SHA-256
`1d0cf8e1495802cd37e26f340fa1c8f75a3c0cfebe5a600548a28e5c775cff44`.

V5 requires a new source revision, execution binding and output directory. It must
embed the failed v4 execution binding SHA-256 above. It remains limited to the same
eight development dialogues and does not authorize evaluation, the 48-item scorer
run, 32-dialogue screening, confirmation research or external human review.
