# G5 evidence-catalog development review v4 inputs

This input panel preserves all 48 v3 cases from the same eight legacy internal public
dialogues without result-based selection. Trusted local code divides each message into
ordered source-bound spans and assigns immutable evidence IDs. The model would select IDs;
it would not copy quotes or calculate speaker identity or character offsets.

This directory is the immutable input-only record. Its pre-execution
`external_execution_authorized` marker remains false because authorization is never written
back into frozen inputs. The user subsequently gave separate explicit authorization; results
and authorization scope are recorded in the sibling `-predictions` directory.

- Frozen input SHA-256: `55f0de1fb8f61691030b7055fd21b6dfe92267c6bba877279fe1a6f82f7edc9b`
- Cases: 48
- Largest serialized request: 71,094 bytes
- Full local acceptance: 362 tests, SHA-256
  `128660f06b55ba0fe01b6bfd27952f76eb0954cb1e775ee760b0cca1ee643996`
