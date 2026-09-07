# G4.11 Qualification Evidence

This directory preserves the frozen evidence for staging batch
`fffde583-355b-4b3e-8e5f-e404c236addb`, generated from source revision
`496bd1058432d7f5389ef3898fbac58e686c5b3b` with fixed model
`ollama/gpt-oss:120b` and seed `20260911`.

The first evaluation passes produced 46/48 complete dimensions. After repeated
missing-only retries returned the same malformed metric rows, the user
authorized evaluator-only revision
`dc159780997b3b160641c02f22b09e521f9766e2`. Only the missing
`role_strategic_fidelity` dimensions for runs 527 and 528 were recomputed. Their
transcript hashes and all other completed dimension hashes remained unchanged.

## Artifacts

- `transcripts.json.gz`: all eight frozen transcripts and provenance
- `debug-bundle.json.gz`: telemetry, manifests, integrity probes, and errors
- `final-evaluation.json.gz`: complete independent evaluator summary (48/48)

All gzip streams were validated after encrypted transfer. The qualification
analysis is in `docs/EXPERIMENT_G4_11_QUALIFICATION_RESULTS.md`.

## Artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `transcripts.json.gz` | `4a929a57ef6966c8be7173e0e8016deafa016fc53ea9d7f1a1cce9a8d4aaac56` |
| `debug-bundle.json.gz` | `3fc4a0dd8a640d31330586578cc4f544f250240dcb2d9511df9cc8b92c83a0c6` |
| `final-evaluation.json.gz` | `9ca1ad678b6f9b8bdc7443074e9ce677dd286172c47f83611764b69a13f562ae` |

## Recomputed transcript hashes

| Run | Condition | Messages | SHA-256 |
| ---: | --- | ---: | --- |
| 523 | Baseline | 76 | `b31b18b16138f564f7e24e3e09ccfc55e5b69f61c915b07c27eed33d2f859be5` |
| 524 | RoomMind | 33 | `ebf2584acac442f1b27c3ee70fb7b8472364ef6a123f5bb215ba24015600eeb2` |
| 525 | Baseline | 40 | `6d80aa2ddc71d05fe7c3e1149e2b568c0629a49f16eaefd594671c28f8c7bafe` |
| 526 | RoomMind | 8 | `32733f0d57869285e27ed05728dd2f192bed6158e00ccae4e88346b3def4373e` |
| 527 | Baseline | 73 | `05c809f3bfd7045a3640af9fc269f6de70fdf117509621da90f5c5b323faf078` |
| 528 | RoomMind | 32 | `9ccfb8e091327768723df8b4482379a05392bf37f050352ec7b46f8372b6094d` |
| 529 | Baseline | 32 | `e6cdb8b900dac6fb3e02f615df9679d387173a5f862f993963ef5ee15b83b688` |
| 530 | RoomMind | 25 | `720058d797e23ad8c576e099495ffcaed16daa3ab8f610fab98a27eb3a5aa38f` |

Every recomputed hash matched the frozen run result and debug-bundle
provenance. No external human review was started.
