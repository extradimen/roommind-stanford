# G5 fresh-family v3 failed online execution

Immutable local preservation of the staging v3 execution stopped on 2026-09-12.
It contains two worlds, 16 committed events, 152 model attempts and one frozen
16-turn source. The second world failed strict plan validation before committing
an event. This is development failure evidence, not confirmatory evidence.

- Source revision: `5f2124bcf0d8c2bb9df62be4027393f118d76830`
- Execution SHA-256:
  `e92158edd584ac8c0152d38c20e762bbd9860e6fe6e7c45590aaa8820c3c9071`
- Frozen source SHA-256:
  `2286163150c7c6fd786cddfa00b3401e109d4ec221e17b113cc2dc9a60472c3e`

The server originals remain in place. This directory was downloaded through
encrypted SSH without changing them.
