# G4.7 Qualification Evidence

This directory preserves the frozen evidence for staging batch
`b9e79535-4ab5-4db7-89d9-684ab5ba211c`, generated from source revision
`597dbe4b4efca804f93bc9099fc2ac95e7a7381d` with fixed model
`ollama/gpt-oss:120b` and seed `20260907`.

## Artifacts

- `transcripts.json.gz`: all eight frozen transcripts and provenance
- `debug-bundle.json.gz`: run telemetry, manifests, integrity probes, and errors
- `final-evaluation.json.gz`: independent evaluator summary (47/48 dimensions)

All gzip streams were validated after transfer. The qualification analysis is in
`docs/EXPERIMENT_G4_7_QUALIFICATION_RESULTS.md`.

## Recomputed transcript hashes

| Run | Condition | Messages | SHA-256 |
| ---: | --- | ---: | --- |
| 481 | Baseline | 31 | `5a89d49fa79f796bfa31104d7037530e56b0bdd3cad3404d0bf58d2463c34a48` |
| 482 | RoomMind | 38 | `d59fc0305fc8649f026099d0c20e5616148f5ea027d4de7e19752f03c1ed7aa4` |
| 483 | Baseline | 63 | `c5f5c31a552d69519544e9bb65d121c60e2c35d4cda5eae24e8d76759656131a` |
| 484 | RoomMind | 14 | `69fe5e3d92a5e9057bb1586a62f5c08fa68e2367add42b145f6a05fe138ab84e` |
| 485 | Baseline | 72 | `e5903c02da8d93ff5ef328271bdd8067c79f723cfc0d3469cff42f542ca82e99` |
| 486 | RoomMind | 12 | `819cb2d5a89166f5d37a9e72c5d9cc1eed37108e23365bd90644cabc5bb463d9` |
| 487 | Baseline | 74 | `f847b6d3a4f86d490805e2398686a8a3defb2a65208816c050b5e91049724435` |
| 488 | RoomMind | 39 | `6715e2c80b768d33b6e6a80a69dbca9534252db7e67a8b6dafb0d8bbb1820637` |

The partial evaluation is retained as evidence rather than repaired after the
fact. Run 486 procedural fidelity remained missing after the original attempt
and two targeted retries because the evaluator prompt permits empty evidence
arrays while its parser rejects them.
