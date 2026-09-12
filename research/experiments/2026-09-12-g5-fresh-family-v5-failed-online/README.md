# G5 fresh-family v5 failed online execution

This directory is the byte-for-byte local archive downloaded over encrypted SSH
after the v5 worker exited. It is internal development evidence, not scorer
validation or an architecture-effect estimate.

- Source revision: `b22eb7c6ca7d7a294363ff1e85d8723579d37aac`
- Execution binding: `86b4efff3849ffe11de5f755532968a97bd66fd134a5b88a18a1416a26c44dd4`
- Failed predecessor: `3fd2adfe9c3eeea8942c2b69dd957422cb82034e141838ab6700826f30f21868`
- Provider/model: `ollama/gpt-oss:120b`, low reasoning
- Retained state: four distinct worlds, 52 committed events, 560 attempt records
  and three frozen sources; SQLite integrity passed after worker exit.

The first three dialogues completed at 16 turns. The fourth world,
`research-data-release-v2` arm D, retained four committed events. Before event 5,
the `principal_investigator` cognition stage repeatedly proposed a hierarchical
plan status transition without a nonempty `status_source_ids` list. The existing
plan protocol rejected it with `Task transition needs observed evidence`.

Three process-level attempts against the same immutable binding and SQLite state
failed at the same version. Their failed cognition records contain respectively
two, four and four received model-I/O receipts; all are classified
`invalid_or_conflicting_state`. No invalid public event was committed and
`transcripts.json` was never emitted.

All seven downloaded evidence files match their remote SHA-256 values. The three
source bundles independently verify their event hash chains and final seals. The
attempt journal retains request and response hashes and byte counts, but not the
rejected raw structured outputs or the validator's exact field path. This repeats
the v4 audit limitation and prevents a field-by-field reconstruction of why the
bounded repair failed.

This archive must not be mutated, resumed, combined with v3/v4 completions, scored
as a completed development set, or used for an architecture-effect claim.
