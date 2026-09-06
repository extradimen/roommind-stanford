# G4.10 Qualification Evidence

This directory preserves the frozen evidence for staging batch
`6394089e-662e-422b-9b82-9bea10264650`, generated from source revision
`5e4df7aaf004b14f088f2be7592013ab0dc51aaf` with fixed model
`ollama/gpt-oss:120b` and seed `20260910`.

The audit-only batch `5b9a4b2e-5a71-450f-84c8-24382d648291` was created by
an obsolete orphan API process, cancelled before any dialogue completed, and
is excluded from every result in this directory.

## Artifacts

- `transcripts.json.gz`: all eight frozen transcripts and provenance
- `debug-bundle.json.gz`: run telemetry, manifests, integrity probes, and errors
- `final-evaluation.json.gz`: complete independent evaluator summary (48/48 dimensions)

All gzip streams were validated after encrypted transfer. The qualification
analysis is in `docs/EXPERIMENT_G4_10_QUALIFICATION_RESULTS.md`.

## Artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `transcripts.json.gz` | `da7a1fea7de27773f5c9aab3a5a3b8e3d084f94fb16ef484f60200ba6f086379` |
| `debug-bundle.json.gz` | `692995e4eb67dcba706442b8356fdd7b7fcf2fb17e077ba5442ae964495104e6` |
| `final-evaluation.json.gz` | `2e2fd1c52066f5798d39335d6db38ae1920970242c3caa355d10c9656659f7ca` |

## Recomputed transcript hashes

| Run | Condition | Messages | SHA-256 |
| ---: | --- | ---: | --- |
| 515 | Baseline | 78 | `e94d240e8095ac0dab8592f60a5cccfb2b8ad1028c7dacffdc8b8a7641b7fd56` |
| 516 | RoomMind | 24 | `04f5d94fc8837af2c09f0e334ebf5e47a8ea31e0964c08a5f88ca548bafbf645` |
| 517 | Baseline | 52 | `9a664dbc0316b0137d2bdf317ced4e03d827437b4cf9816db05370375ad65474` |
| 518 | RoomMind | 18 | `300d0a377f6bfc50fca4f295b85f1c75211faeccea897537e312759f20ebe970` |
| 519 | Baseline | 27 | `352adad8eaf193203a9b99be3ed460bce9c4844fbd15f615017b61ddd445ae3b` |
| 520 | RoomMind | 46 | `387ed47000c7699b0ab65534eadca9ec36ebdfd2274e1cb208aeeca491e988ce` |
| 521 | Baseline | 29 | `d53f903f610823c1175a031bad55f91c22f03f125bfa73639c8ed162c0bf83ad` |
| 522 | RoomMind | 22 | `0162a824034b5880f0e132bac3213dd58b02b34e9eb8fda4cf5c6ce5cbc00707` |

Every recomputed hash matched the frozen run result and debug-bundle
provenance. No external human review was started.
