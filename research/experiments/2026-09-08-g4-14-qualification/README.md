# G4.14 Qualification Evidence

This directory preserves the immutable evidence downloaded after RoomMind
staging batch `e29005cf-d6e5-4e4b-b4e1-34e5036f1e5e` completed dialogue
generation and independent six-dimension evaluation.

## Frozen identity

- source: `6b4e461d5d69659bb8546e285b96f77eccfa4539`
- architecture: `g4.14-publication-owner-and-artifact-grounding`
- model: `ollama/gpt-oss:120b`
- seed: `20260914`
- manifest: `5605c5f71b9f3daeca520ffa7af45cc98bd2d5dbc70f3b6cb70d20bd8ea688d6`

## Files

| File | SHA-256 |
| --- | --- |
| `g4-14-transcripts.json` | `724d34aa577c6485ad45c8aafa1c4e185624848c2dda960b1b52a70ebe1dadbe` |
| `g4-14-debug-bundle.json` | `602fe9d1dfcb035405340ae12fcd0c17f5fcae0b2472a14726f0b890ef3f76b0` |
| `g4-14-final-evaluation.json` | `ec5ed408296fcaa10428e01572e1f424fe2b2cd6962823f23aea39645271cb2e` |

All eight recorded transcript hashes were independently recomputed from
canonical JSON and matched exactly. All 48 evaluation dimensions completed
with empty error maps.

## Disposition

Strict qualification **FAIL**. All recorded deterministic probes pass on all
four RoomMind runs, but the AI aggregate is 4.521 versus Baseline 5.458 and
manual review finds unsupported live-state claims, unregistered ownership,
cross-role action substitution, terminal-phase reopening, poor fallback speech,
and premature conditional/deferred closure. See
`docs/EXPERIMENT_G4_14_QUALIFICATION_RESULTS.md` for the full evidence review.
