# G4.9 Qualification Evidence

This directory preserves the frozen evidence for staging batch
`9ca21260-0f2f-43c9-9a15-0796608753c3`, generated from source revision
`e4f953cb46a219472f2955ac4313023815c7657a` with fixed model
`ollama/gpt-oss:120b` and seed `20260909`.

## Artifacts

- `transcripts.json.gz`: all eight frozen transcripts and provenance
- `debug-bundle.json.gz`: run telemetry, manifests, integrity probes, and errors
- `final-evaluation.json.gz`: complete independent evaluator summary (48/48 dimensions)

All gzip streams were validated after encrypted transfer. The qualification
analysis is in `docs/EXPERIMENT_G4_9_QUALIFICATION_RESULTS.md`.

## Artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `transcripts.json.gz` | `3da3eb625a80ccb165dd2551e1d49f0fc216cd92c072ef01860dc753bd31b3be` |
| `debug-bundle.json.gz` | `88ccd3b5c2330d6a75e74cc492e7c8cd2cce26b1e1c74460b2ac08cba5c91ddc` |
| `final-evaluation.json.gz` | `aa922cd422002d12be35930d35e0c6b7d7f40d56d1fe6051e263ecaf892642ba` |

## Recomputed transcript hashes

| Run | Condition | Messages | SHA-256 |
| ---: | --- | ---: | --- |
| 499 | Baseline | 57 | `7ca94068d867d8ebb614d63732186ee80647a68d955b9c45130e63ca3ea27087` |
| 500 | RoomMind | 30 | `db1829b0c42962c8236da5850160e8455fc4af71efc58465e24d504b97d484bf` |
| 501 | Baseline | 77 | `097d47b466a03a521927a694960333afde51bbc9527fd8ed4d1a10f1ef45fd98` |
| 502 | RoomMind | 44 | `b19d5c61c5959018983c5455c6b94f2b4647ba0cef872d104f1c0f818d6b9632` |
| 503 | Baseline | 78 | `fd9257b2b56ba77ceee6df3a4ae79ca1907106da064b9590132d9b984a9a1cf4` |
| 504 | RoomMind | 47 | `c8680f94c3bb56b1cf83c32f42c86e19d1272d63b5456c10fcccb6cbb5c29b37` |
| 505 | Baseline | 25 | `43ea26d5de976f3e7daaa10b478979adfc730c4b089d74ba4ea4794350191486` |
| 506 | RoomMind | 12 | `ebc5d3106f9ef17d78d3522ae5a21b476ee7307053b93d8e3a02b6797cb593cb` |

Every recomputed hash matched the frozen run result and debug-bundle
provenance. No external human review was started.
