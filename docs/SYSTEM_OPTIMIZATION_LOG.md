# System Optimization Log

Ongoing record of production issues, root causes, and fixes during the RoomMind optimization phase.

| # | Title | Status | Session / Ref |
|---|-------|--------|---------------|
| 1 | Plan fallback spoken verbatim (David Chen duplicate lines) | Proposed | `7866fde8-0714-4b80-bb68-0e70f266bcf4` |
| 2 | All initial plans are fallback boilerplate (empty LLM content) | Analyzed | `7866fde8-0714-4b80-bb68-0e70f266bcf4` |

**Relationship:** Issue #1 is largely a downstream effect of Issue #2 (bad plan stored) combined with guaranteed-reply fallback and mention matching.

---

## Issue #1 — Plan fallback spoken verbatim (duplicate NPC lines)

**Date observed:** 2026-07-07  
**Scenario:** 10 (`global-smart-manufacturing-supply-chain-negotiation`)  
**Character:** David Chen (`supplier_ceo_global`)  
**Export:** `session-7866fde8.json`

### Symptom

David Chen spoke the **same non-dialogue sentence twice** (turns 2 and 4):

> Focus on Lead commercial negotiation and defend supplier profitability.. Advance proactively while holding firm on core limits.

Turn 1 was normal negotiated speech. Turns 3–4 involved other NPCs; David repeated the identical line again on turn 4 even though the user addressed him by first name ("David, Emma…").

### Root cause (three layers)

1. **Bad initial plan persisted for the whole session**  
   At session start, `ensure_initial_plan()` did not produce a real strategy. The system stored the **fallback boilerplate** (`plan_fallback_text`) as the active `plan` node (`turn_id=0`, never updated).

2. **Guaranteed-reply fallback reads the plan aloud**  
   When every agent chooses `wait` in a turn, `execute_plan_fallback_speak()` runs so at least one NPC replies. It uses `active_plan.content` as the speech draft. NPC rendering did not transform the text, so **internal plan language appeared in chat**.

3. **First-name mention not detected**  
   `match_mentioned_characters()` matches full labels like `David Chen`, not `"David"` alone. Turn 4 had `mentioned: []`, so the forced-speak path (`wait → speak when mentioned`) never ran; fallback fired again with the **same unchanged plan**.

### Proposed solution

| # | Change | File(s) | Purpose |
|---|--------|---------|---------|
| 1 | **Never expose raw plan text as user-visible speech** | `server/app/agent/act.py` | In `execute_plan_fallback_speak()` / `render_npc_speech()`: if draft equals active plan or matches plan-fallback pattern, require a dedicated “turn plan into dialogue” prompt; if LLM fails, use a short generic English line (e.g. “Let me address your point on pricing and terms.”), not plan metadata. |
| 2 | **Retry initial plan generation; avoid storing boilerplate** | `server/app/agent/reflect.py` | On empty LLM response: retry 1–2 times before fallback; if fallback is used, tag plan meta `{ "source": "initial_plan", "quality": "fallback" }` and optionally regenerate after first user message. Strip trailing period from `responsibility` before `plan_fallback_text()` to fix `..` typo. |
| 3 | **First-name / alias mention matching** | `server/app/orchestrator/common.py` | Add first-token match from `display_name` (e.g. `David` from `David Chen (…)`), plus optional `character_name` field from scenario JSON. |
| 4 | **De-duplicate consecutive identical NPC lines** | `server/app/agent/act.py` or `generative.py` | Before persisting speech, skip or re-render if `content` equals the character’s previous message in the same session. |
| 5 | **Observability** | `agent_debug`, export | Log `fallback_speak: true`, `plan_quality: fallback`, and `mention_hits` per turn for easier export review. |

### Acceptance criteria

- [ ] No NPC line equals `plan_fallback_text` or raw `plan.content` in normal or fallback paths.
- [ ] User saying `"David, …"` sets `mentioned` to include `supplier_ceo_global`.
- [ ] Same session: David does not repeat identical content on consecutive fallback turns unless the user repeats the same question.
- [ ] Initial plan in export is 2–3 sentences of strategy in English, not responsibility boilerplate.

### Implementation status

- **Proposed** — not yet implemented (logged 2026-07-08).

---

## Issue #2 — All initial plans are fallback boilerplate

**Date observed:** 2026-07-07  
**Scenario:** 10 (`global-smart-manufacturing-supply-chain-negotiation`)  
**Session:** `7866fde8-0714-4b80-bb68-0e70f266bcf4`  
**Model:** Ollama Cloud `glm-5.1` (global default)

### Symptom

At session start, **every NPC** (David, Emma, Michael) received the same style of plan:

> Focus on {responsibility}. Advance proactively while holding firm on core limits.

All three plans in `agent_memory_nodes` have `meta.source = "initial_plan"` and `turn_id = 0`. No real 2–3 sentence strategy was generated.

This is **not** scenario-specific content — it is `plan_fallback_text()` from `server/app/i18n/reply_language.py`.

### Root cause (confirmed by reproduction)

Fallback is used when `ensure_initial_plan()` gets an **empty string** after `raw.strip()`:

```python
# server/app/agent/reflect.py
max_tokens=min(decision_llm.max_tokens, 200)   # hard cap 200
...
if not plan_text:
    plan_text = plan_fallback_text(character.responsibility)
```

**Why LLM returns empty (HTTP 200, not an API error):**

1. **Ollama Cloud `glm-5.1` is a reasoning/thinking model.**  
   The API response puts long chain-of-thought in `choices[0].message.reasoning`, while `choices[0].message.content` is often `""`.

2. **`max_tokens=200` is too small.**  
   Reproduction (2026-07-08, same prompt shape as production):

   | max_tokens | content | reasoning | finish_reason |
   |------------|---------|-----------|---------------|
   | 200 | empty | ~965 chars | `length` |
   | 512 | empty | ~2621 chars | `length` |
   | 1024 | ~496 chars (valid plan) | ~3070 chars | `stop` |

   With 200 tokens, the model exhausts the budget on internal reasoning and never writes the final answer into `content`.

3. **`LLMClient.chat_completion()` only reads `message.content`.**  
   It ignores `message.reasoning`, so the call “succeeds” but returns `""` → fallback plan for all agents.

4. **Logs looked healthy.**  
   Session `7866fde8` shows multiple `POST ollama.com … 200 OK` during turn 1 seed/plan + dialogue. No exception — silent empty content.

### Why turn-1 NPC speech can still work

Other call sites use higher caps (`decision` up to 512, `npc` up to 256). Under some prompts the model may still fill `content` within the budget, or the decision JSON path behaves differently. Initial plan is ** uniquely capped at 200**, so it fails most consistently.

### Proposed solution

| # | Change | File(s) | Purpose |
|---|--------|---------|---------|
| 1 | **Raise initial-plan token budget** | `server/app/agent/reflect.py` | Use e.g. `max_tokens=min(decision_llm.max_tokens, 1024)` or a dedicated config; never cap at 200 for thinking models. |
| 2 | **Thinking-model aware client** | `server/app/llm/client.py` | If `content` is empty but `reasoning` is present: either retry with higher `max_tokens`, or parse final answer from reasoning (last resort). Prefer explicit Ollama “no think” flag if supported. |
| 3 | **Detect fallback plans** | `server/app/agent/reflect.py` | Tag `meta.quality = "fallback"`; log warning; optional admin/debug flag `initial_plan_used_fallback`. |
| 4 | **Retry before fallback** | `server/app/agent/reflect.py` | On empty content: retry once with 2× max_tokens before `plan_fallback_text()`. |
| 5 | **Model guidance** | docs / admin | Document that reasoning models (glm-5.1, kimi-k2.5:cloud on Ollama) need higher token limits for plan/decision roles. |

### Acceptance criteria

- [ ] New sessions on scenario 10 + Ollama `glm-5.1`: all agents get 2–3 sentence English plans, not `plan_fallback_text` pattern.
- [ ] `agent_memory_nodes` plan content does not start with `"Focus on {responsibility}"` unless LLM truly failed after retry.
- [ ] Debug/export shows `initial_plan_used_fallback: false` for normal runs.

### Implementation status

- **Analyzed** — root cause confirmed; fix not yet implemented (logged 2026-07-08).

---

## Template for future issues

```markdown
## Issue #N — Title

**Date observed:** YYYY-MM-DD  
**Scenario / Session:**  
**Symptom:**  

### Root cause

### Proposed solution

### Acceptance criteria

### Implementation status
```
