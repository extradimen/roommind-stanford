# G4.15 Qualification Evidence

This directory preserves the immutable development-only evidence for staging
batch `ff6098d3-0cc5-41f6-90a2-5e35076c5dd2`.

## Frozen identity

- source: `5752d34bdeb08b9b35cb048011ed9b9e247c68c9`
- architecture: `g4.15-typed-publication-and-terminal-phase-governance`
- model: `ollama/gpt-oss:120b`
- seed: `20260915`
- manifest: `130da6329ddbdee19a7190512ad64b925567dbab5b64e43b6d4cec336151b3c6`

## Files

| File | SHA-256 |
| --- | --- |
| `g4-15-transcripts.json` | `194d0b5bebae68fa3e7ac18e597139a3c31a7993a1dd8156c23d00c04f46e561` |
| `g4-15-debug-bundle.json` | `394eabf1148bbbae6d084901ccad771982261c2ce7345d45729e1ea883e5b6d2` |
| `g4-15-final-evaluation.json` | `98cc77fafcdcc6826c26b4b3811b35a6446da59e4532810f5077c3359ea668b2` |

All three files passed JSON validation after encrypted transfer. Independent
canonical-JSON recomputation matched all eight recorded transcript hashes, and
all 48 evaluation dimensions completed without evaluator errors or retry.

## Disposition

Strict qualification **FAIL**. Only one of four RoomMind runs passes every
applicable integrity probe. The AI aggregate is 4.538 versus Baseline 5.250,
and manual review finds unsupported present-world claims, response-owner and
multi-addressee routing failures, terminal continuation, and repetitive
fallback output. No external human review was started. See
`docs/EXPERIMENT_G4_15_QUALIFICATION_RESULTS.md` for the complete gate review.
