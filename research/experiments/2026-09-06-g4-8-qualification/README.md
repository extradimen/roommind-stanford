# G4.8 Qualification Evidence

This directory preserves the frozen evidence for staging batch
`930fca41-758e-4b1e-ac3f-a235d8f1524b`, generated from source revision
`fa4e673580d0e7d041cb57a0e19e6c682ae73a33` with fixed model
`ollama/gpt-oss:120b` and seed `20260908`.

## Artifacts

- `transcripts.json.gz`: all eight frozen transcripts and provenance
- `debug-bundle.json.gz`: run telemetry, manifests, integrity probes, and errors
- `final-evaluation.json.gz`: complete independent evaluator summary (48/48 dimensions)

All gzip streams were validated after encrypted transfer. The qualification
analysis is in `docs/EXPERIMENT_G4_8_QUALIFICATION_RESULTS.md`.

## Artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `transcripts.json.gz` | `7859ab2024f43d6101595fd1bf0772483aad356bf372e1bbe5c65feba65a4034` |
| `debug-bundle.json.gz` | `31e14541ca4c74a9bed7bda23eb1f0c2ebcca5cd3d5cc012f3b5c3c3e1e3d71e` |
| `final-evaluation.json.gz` | `97b7bd080e27b21aea9fcbe34f058fc3c7f682ff9d3adec2097c81c5fa6088d1` |

## Recomputed transcript hashes

| Run | Condition | Messages | SHA-256 |
| ---: | --- | ---: | --- |
| 491 | Baseline | 78 | `f07e9d5e1b9d4ba7fa104dfbade333a729143230e449123b0891a721bd082d9c` |
| 492 | RoomMind | 11 | `007df6b1550917c794685f4ca4a18af50527c4fbb95bedf29d90faf3a3bc88f2` |
| 493 | Baseline | 79 | `26bad2a876a5d6aa8754e3275772e2b9cd0cfb20efb855d50a633e8c400969c2` |
| 494 | RoomMind | 14 | `d96f9c65b15118e55d2e035e97950b725014a1f0303c1112956236ea358997bd` |
| 495 | Baseline | 73 | `d7519a59cc8843c8ec22e0931225109a8c04e77116bee79699cfd1519eb7ff33` |
| 496 | RoomMind | 50 | `ad0cef04fbe94310d43e90f1e3dd1831a80ef89c17373dccd688bbb8360b2a2e` |
| 497 | Baseline | 54 | `052b83a04e86d4465e2a57758d0a3f7b2f35d99524ea654c1faf1ad6ab12d3f6` |
| 498 | RoomMind | 31 | `1e3516ea5e366eced669d7c50bb8d6928e0800b8b627f662fd43e3bcfec89f72` |

Every recomputed hash matched the frozen run result and debug-bundle provenance.
