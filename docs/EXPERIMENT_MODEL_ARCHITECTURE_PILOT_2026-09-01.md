# Model × Architecture Reliability Pilot — 2026-09-01

## Purpose

This exploratory engineering pilot separates two possible causes of autonomous
dialogue failures:

1. provider/model reliability; and
2. RoomMind architecture reliability.

It is development evidence, not a confirmatory research result.  No realism scores
or external human ratings were generated in this pilot.

## Frozen factors

- Scenario: `market-launch-go-no-go` (scenario id 2).
- Scenario template SHA-256 was identical in both code worktrees:
  `29bf31bd5f00451d7b07a1c85209b268da8d168b4dfbe08cf05a9152bd4e3743`.
- Conditions per batch: RoomMind (`test`) and independent-memory-agent baseline.
- Concurrency: 1.
- Safety maximum: 12 turns.
- Maximum stagnant turns: 6.
- Random seed: `20260901`.
- Provider failover: disabled by the controlled-comparison policy.
- Old architecture: commit `95b6594`, `g1-governed-independent-agents`.
- New architecture: commit `ef8c4f7`, `g1.1-resilient-governed-agents`.
- Old and new architectures ran from separate Git worktrees, PostgreSQL databases,
  and localhost-only API ports.  They did not use the staging database.

## Stage A — initial configured-candidate qualification

This initial screen covered the models present in the deployment's configured
fallback catalog.  It did **not** represent the complete live Ollama Cloud catalog;
that distinction was discovered during review and is corrected in Stage C below.

Each configured candidate received the same three sequential, single-attempt probes:
short visible text, structured role-decision JSON, and bounded long-context JSON.
RoomMind retry and provider failover were bypassed.

| Provider/model | Usable probes | Qualification result | Failure evidence |
|---|---:|---|---|
| Ollama `deepseek-v4-flash` | 3/3 | Pass | — |
| Ollama `gpt-oss:120b:cloud` | 3/3 | Pass | — |
| Ollama `kimi-k2.5:cloud` | 0/3 | Ineligible | HTTP 410; retired 2026-07-31 |
| Ollama `deepseek-v3.2:cloud` | 0/3 | Ineligible | HTTP 410; retired 2026-07-15 |
| SiliconFlow `Qwen/Qwen2.5-7B-Instruct` | 0/3 | Ineligible | HTTP 402; insufficient account balance |
| SiliconFlow `Qwen/Qwen3-8B` | 0/3 | Ineligible | HTTP 402; insufficient account balance |
| SiliconFlow `deepseek-ai/DeepSeek-V4-Flash` | 0/3 | Ineligible | HTTP 402; insufficient account balance |
| SiliconFlow `moonshotai/Kimi-K2.5` | 0/3 | Ineligible | HTTP 402; insufficient account balance |

Models that cannot complete a raw API call were not run end to end.  Their failure
occurs before either architecture can act, so repeating the same retired-model or
unfunded-account error inside every scenario would add no architectural evidence.

## Stage B — end-to-end pilot results

One repetition was run per eligible model and architecture.  Wall time and rates
must be interpreted with the turn count because model outputs affected when the
scenario stopped.

| Architecture | Model | Condition | Result | Turns | Wall time | Attempts | Retry events | Retry rate | Tokens |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| Old G1 | DeepSeek V4 Flash | RoomMind | Completed | 7 | 646.0 s | 102 | 27 | 26.5% | 197,261 |
| Old G1 | DeepSeek V4 Flash | Baseline | Failed | — | 2.8 s | 0 | 0 | — | 0 |
| New G1.1 | DeepSeek V4 Flash | RoomMind | Completed | 8 | 1007.1 s | 112 | 37 | 33.0% | 183,661 |
| New G1.1 | DeepSeek V4 Flash | Baseline | Completed | 5 | 57.1 s | 21 | 1 | 4.8% | 50,754 |
| Old G1 | GPT-OSS 120B | RoomMind | Completed | 12 | 391.0 s | 144 | 26 | 18.1% | 315,692 |
| Old G1 | GPT-OSS 120B | Baseline | Failed | — | 1.2 s | 0 | 0 | — | 0 |
| New G1.1 | GPT-OSS 120B | RoomMind | Completed | 12 | 296.8 s | 105 | 7 | 6.7% | 260,154 |
| New G1.1 | GPT-OSS 120B | Baseline | Completed | 12 | 65.4 s | 49 | 1 | 2.0% | 150,074 |

Batch UUIDs:

- old DeepSeek: `a69230ca-69d1-4531-a756-23341e4ba551`;
- new DeepSeek: `75bac7ec-a74b-42ce-8009-a7f39115bbe3`;
- old GPT-OSS: `fd00bb6b-0820-4ce5-a898-4e818df776c7`;
- new GPT-OSS: `f21b8a22-1f6d-4581-8033-b7cf976b0107`.

An earlier batch, `886c3835-2cec-4a6c-8bdc-eeba0cec4b74`, is excluded.  Its
isolated database seeded `siliconflow/moonshotai/Kimi-K2.5`, overriding the intended
platform model and producing HTTP 402 before the intended treatment was applied.

## Findings

### Model main effect

Model choice is strongly related to technical performance in this pilot.

Within the new architecture, GPT-OSS compared with DeepSeek reduced:

- wall time per RoomMind turn from 125.9 s to 24.7 s (80.4% lower);
- attempts per turn from 14.0 to 8.75 (37.5% lower);
- retry events per turn from 4.63 to 0.58 (87.4% lower); and
- retry rate from 33.0% to 6.7%.

The direction is consistent in the old architecture: GPT-OSS had 64.7% lower wall
time per turn and a lower retry rate (18.1% versus 26.5%).  DeepSeek repeatedly
returned `finish_reason=length` on long structured prompts even though it passed the
three small raw probes.

### Architecture main effect

The new architecture fixed a deterministic system failure.  Both old-architecture
baseline runs failed before a model response was counted because `_agent_memory`
iterated over `None`.  Both new-architecture baseline runs completed.

With GPT-OSS, where model instability was relatively low, the new RoomMind
architecture also reduced per-turn wall time by 24.1%, attempts per turn by 27.1%,
retry events per turn by 73.1%, and tokens per turn by 17.6%.

The single DeepSeek repetition did not show a speed improvement under the new
architecture.  It completed without a technical crash, but stochastic `length`
responses produced more retries and one extra turn.  This is evidence that
architecture hardening improves failure containment but cannot make an unsuitable
model intrinsically stable.

### Interaction and remaining system issue

The failure risk is multiplicative: RoomMind makes many structured LLM calls per
meeting turn, so a model with a high per-call unusable-response probability is
exposed many times.  Model qualification and architectural resilience are both
necessary.

All GPT-OSS RoomMind/baseline conversations ran to the 12-turn safety limit, and
several conversations continued after participants appeared to converge.  The task
completion/stagnation detector therefore remains a separate architecture problem;
it inflates runtime and provider exposure independently of model correctness.

## Limitations and next gate

- There is only one end-to-end repetition per eligible model/architecture cell.
- LLM sampling is not deterministic even with the recorded experiment seed.
- Different stopping points require per-turn normalization and prevent treating raw
  totals as direct quality comparisons.
- Technical reliability is not dialogue realism.  The frozen transcripts must be
  evaluated separately and blindly if realism is the outcome of interest.

Before choosing a production model, repeat the 2 × 2 eligible matrix at least five
times on two scenarios.  Keep concurrency at 1, lock the provider/model in both the
database and manifest, and report failure rate, retry rate, latency per turn, and
completion-limit rate with uncertainty intervals.

## Artifacts

Raw provider results, batch summaries, transcripts, and forensic debug bundles are
stored under:

`research/experiments/2026-09-01-model-architecture-pilot/`

The reusable qualification command is:

`server/tests/model_provider_qualification.py`

## Stage C — live-catalog correction

The qualification tool now defaults to the live Ollama Cloud catalog returned by
`fetch_ollama_cloud_catalog()`.  It fails closed if a live catalog was requested but
could not be fetched, instead of silently treating the local fallback list as the
complete provider inventory.  Website family names and exact API model/tag IDs are
retained as separate candidates because a website-listed family alias may not be a
callable API identifier.

The complete live-catalog results and the follow-up architecture comparison are
stored alongside the initial pilot artifacts.  The initial Stage A and Stage B
results are retained unchanged as exploratory provenance rather than overwritten.

The live merge returned 26 exact identifiers (18 website families and 19 API
identifiers, with overlap).  A single-attempt three-probe screen produced:

- 11/26 full passes;
- 10/26 partial passes; and
- 5/26 zero passes.

Three zero-pass names (`gpt-oss`, `mistral-large-3`, and `nemotron-3-nano`) were
website family aliases that returned HTTP 404, while their explicit tagged API IDs
were callable.  Both `qwen3.5` IDs returned HTTP 200 but no visible content for all
three probes with `finish_reason=length`.

An initial 42-cell one-turn architecture screen is retained as
`invalid-model-architecture-one-turn-smoke-binding-mismatch.json` and excluded from
all model-effect analysis.  Its harness updated `.env`'s `DATABASE_URL`, whereas the
running APIs resolve their databases from `config/platform.json`; consequently all
cells actually used `gpt-oss:120b:cloud`.  The corrected harness now resolves the
same platform database source as the application and rejects any cell whose observed
player model label does not exactly match the intended model.  A two-cell DeepSeek
validation confirmed exact binding in both revisions before the corrected matrix was
started.
