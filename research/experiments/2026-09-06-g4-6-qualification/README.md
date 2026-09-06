# G4.6 Qualification Artifact Set

This directory preserves the frozen artifacts for batch
`d0ed05f5-ec64-49dc-8452-e2154d60c2fe`.

- Source revision: `806685cec452df63fd26186b21761dd031ef5b6e`
- Architecture: `g4.6-clause-grounded-recovery-governance`
- Model: `ollama/gpt-oss:120b`
- Random seed: `20260906`
- Dialogues: 8/8 frozen, zero failures
- Evaluation: 48/48 AI dimensions complete
- Human review: not started

Files:

- `transcripts.json.gz`: complete public transcripts and persisted run results
- `debug-bundle.json.gz`: forensic logs, traces, prompts and integrity evidence;
  contains internal debugging content
- `final-evaluation.json`: independent six-dimension condition summaries

Independently recomputed transcript hashes:

| Run | Condition | Scenario | SHA-256 |
|---:|---|---|---|
| 473 | Baseline | Supply-chain negotiation | `ecde8521226640030ef0361c184d453d126da275d744bb9cc4059dcef065e2a7` |
| 474 | RoomMind | Supply-chain negotiation | `49333a009ea8e6441647a9b4fc7f587ab3420422f492bc56a87936ab9a671e0c` |
| 475 | Baseline | Product launch | `ad275cee57515a62c70979fbcb6ad020c65eca923c6da09b6480411991c57309` |
| 476 | RoomMind | Product launch | `b87f42e8bd1a4bc71026e9e6856ad8859abb8f78f8c2823a29332b39864387ed` |
| 477 | Baseline | Leadership interview | `535390fa341884a44ca971a3c500f22104a4f9929711b11add19ab65d6137ec3` |
| 478 | RoomMind | Leadership interview | `e953b8727afee06cc54f47cdf14f9708ac551006806aa1fdf7baa828aeeccbc3` |
| 479 | Baseline | Incident command | `bcb8a910624941a2c021b0da22572251723005d2560bc5e0c6e7d20d87eefb8e` |
| 480 | RoomMind | Incident command | `79a456e2d88adcaa16d64108c38fbd551911f3fbf41b57a1ea6084a89e861fdd` |

The evidence-backed disposition is recorded in
`docs/EXPERIMENT_G4_6_QUALIFICATION_RESULTS.md`.
