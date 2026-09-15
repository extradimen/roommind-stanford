# G5 fresh-family v4 failed online execution

This directory is the byte-for-byte local archive downloaded over encrypted SSH
after the v4 worker exited. It is development evidence only, not scoring or an
architecture-effect estimate.

- Source revision: `f617c8697bc9a50b96514d89b51205a840a9c28c`
- Execution binding: `3fd2adfe9c3eeea8942c2b69dd957422cb82034e141838ab6700826f30f21868`
- Failed predecessor: `e92158edd584ac8c0152d38c20e762bbd9860e6fe6e7c45590aaa8820c3c9071`
- Provider/model: `ollama/gpt-oss:120b`, low reasoning
- Retained state: four distinct worlds, 63 committed events, 860 attempts and
  three frozen sources; SQLite integrity passed after worker exit.

The first three dialogues completed at 16 turns. On version 15 of the fourth
world (`research-data-release-v2`, arm D), the question annotator returned a
successful 313-byte model response, but the annotation assigned a question to
invalid targets. The strict question projection rejected the pending commit with
`Invalid question targets`; no invalid event was committed. The v4 worker was not
restarted because this was a structured-output failure, not a transient transport
interruption. `transcripts.json` was never emitted.

The attempt journal preserves the request/response byte counts and hashes, but not
the rejected raw annotation text. This limits retrospective diagnosis to the exact
validator failure and receipt metadata. A recovery must use a new binding and
output directory, validate annotations before commit, and return bounded validator
feedback to the same fixed model. It must not mutate or resume this archive.
