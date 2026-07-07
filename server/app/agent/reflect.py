"""
Reflection & Planning — Stanford Generative Agents architecture.

Layer 1  Seed Memory    : authored facts injected once at session start
Layer 2  Planning       : coarse-grained meeting plan generated from seed
Layer 3  Reflection     : higher-order inferences triggered by importance threshold
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_stream import AgentMemoryStore, MemoryNode, active_plan
from app.llm.client import llm_client
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.orchestrator.llm_binding import ResolvedLlm


# ---------------------------------------------------------------------------
# Layer 1 – Seed Memory
# ---------------------------------------------------------------------------

def _build_seed_memories(character: CharacterTemplate, scenario: ScenarioTemplate) -> list[dict[str, Any]]:
    """
    Stanford: each agent starts with a paragraph of authored facts split into
    individual memory nodes (importance pre-rated, turn_id=0).

    We build seeds from:
      - persona / responsibility (identity)
      - private_state (hidden knowledge: floor price, risk flags…)
      - tendency (behavioural disposition)
      - scenario business_goal (shared context)
    """
    seeds: list[dict[str, Any]] = []

    # Identity seeds (importance 7 — stable, high-relevance)
    seeds.append({
        "content": f"我是{character.display_name}，{character.persona}",
        "importance": 7.0,
    })
    seeds.append({
        "content": f"我在本次会议中的职责：{character.responsibility}",
        "importance": 8.0,
    })

    # Tendency seeds (importance 6)
    if character.tendency:
        tendency_desc = json.dumps(character.tendency, ensure_ascii=False)
        seeds.append({
            "content": f"我的行为倾向：{tendency_desc}",
            "importance": 6.0,
        })

    # Private state seeds (importance 9 — most critical private knowledge)
    if character.private_state:
        for key, value in character.private_state.items():
            seeds.append({
                "content": f"私密认知 — {key}：{value}",
                "importance": 9.0,
            })

    # Scenario context seed (importance 6)
    seeds.append({
        "content": f"本次谈判场景：{scenario.title}。目标：{scenario.business_goal}",
        "importance": 6.0,
    })

    return seeds


async def ensure_seed_memories(
    db: AsyncSession,
    store: AgentMemoryStore,
    *,
    character: CharacterTemplate,
    scenario: ScenarioTemplate,
    nodes: list[MemoryNode],
) -> list[MemoryNode]:
    """
    Inject seed memories once per session (idempotent — checks existing nodes).
    Called at session start before any user input.
    """
    # If any seed-type node exists, skip (already seeded)
    if any(n.meta.get("source") == "seed" for n in nodes):
        return []

    seeds = _build_seed_memories(character, scenario)
    new_nodes: list[MemoryNode] = []
    for seed in seeds:
        node = await store.append(
            db,
            node_type="observation",
            content=seed["content"],
            importance=seed["importance"],
            turn_id=0,
            tick=0,
            is_active=True,
            meta={"source": "seed"},
        )
        new_nodes.append(node)
        nodes.append(node)
    return new_nodes


# ---------------------------------------------------------------------------
# Layer 2 – Planning (coarse-grained, generated once per session)
# ---------------------------------------------------------------------------

async def ensure_initial_plan(
    db: AsyncSession,
    store: AgentMemoryStore,
    *,
    character: CharacterTemplate,
    scenario_title: str,
    business_goal: str,
    decision_llm: ResolvedLlm,
    nodes: list[MemoryNode] | None = None,
) -> MemoryNode | None:
    """
    Stanford: at the start of each day (= each session), agents generate a
    coarse plan that reflects their identity + seed memories.

    The plan is stored as a high-importance plan node (turn_id=0).
    It becomes the default fallback content when the agent has nothing to say.
    """
    if nodes is None:
        nodes = await store.load_all(db)

    if active_plan(nodes):
        return active_plan(nodes)

    # Collect seed knowledge to ground the plan
    seed_nodes = [n for n in nodes if n.meta.get("source") == "seed"]
    seed_facts = "\n".join(f"- {n.content}" for n in seed_nodes) if seed_nodes else "（无预设信息）"

    private = character.private_state or {}

    prompt = f"""你是 {character.display_name}。
性格：{character.persona}
职责：{character.responsibility}
私密认知：{json.dumps(private, ensure_ascii=False)}

你已了解以下背景事实：
{seed_facts}

本次会议：{scenario_title}
对方目标：{business_goal}

请用 2-3 句话写出你进入会议室时的初始策略计划：
- 打算先谈哪个议题？
- 守住什么底线？
- 第一步打算怎么开场？

只输出计划本身，不要 JSON，不要解释。"""

    raw = await llm_client.chat_completion(
        [{"role": "user", "content": prompt}],
        db_provider=decision_llm.provider,
        db_model=decision_llm.model,
        temperature=decision_llm.temperature,
        max_tokens=min(decision_llm.max_tokens, 200),
    )
    plan_text = raw.strip()
    if not plan_text:
        plan_text = f"围绕{character.responsibility}主动推进谈判，守住底线。"

    return await store.append(
        db,
        node_type="plan",
        content=plan_text,
        importance=8.5,
        turn_id=0,
        tick=0,
        is_active=True,
        meta={"source": "initial_plan"},
    )


# ---------------------------------------------------------------------------
# Layer 3 – Reflection (higher-order inference)
# ---------------------------------------------------------------------------

async def maybe_reflect(
    db: AsyncSession,
    store: AgentMemoryStore,
    *,
    character: CharacterTemplate,
    nodes: list[MemoryNode],
    turn_id: int,
    threshold: float,
    accumulator: float,
    reflect_llm: ResolvedLlm,
    context: str,
) -> tuple[list[MemoryNode], float, str | None]:
    """
    Stanford: when the sum of recent observation importance exceeds a threshold
    (default 150 in the paper; we use 18 for a shorter meeting), synthesise
    higher-order reflections and write them back to the memory stream.

    Returns (new_reflection_nodes, reset_accumulator, raw_text | None).
    """
    if accumulator < threshold:
        return [], accumulator, None

    # Take the most important recent observations as reflection candidates
    candidates = sorted(
        [n for n in nodes if n.node_type == "observation" and n.importance >= 4.0],
        key=lambda n: (n.turn_id, n.importance),
    )[-12:]

    if len(candidates) < 2:
        return [], 0.0, None

    obs_lines = "\n".join(f"- (重要性{n.importance}) {n.content}" for n in candidates[-8:])

    # Stanford reflection prompt: ask 3 salient questions, then answer them
    prompt = f"""你是 {character.display_name}，性格：{character.persona}，职责：{character.responsibility}。

以下是你在会议中最近注意到的事实：
{obs_lines}

最近对话片段：
{context[-600:]}

请完成两步：
1. 列出 2 个对你最重要的问题（关于谈判局势、对方意图、自己的风险）。
2. 针对每个问题，用一句话写出你的推断（这是高阶反思，不是对话台词）。

格式：
Q1: <问题>
A1: <推断>
Q2: <问题>
A2: <推断>

只输出上述格式，不要其他内容。"""

    raw = await llm_client.chat_completion(
        [{"role": "user", "content": prompt}],
        db_provider=reflect_llm.provider,
        db_model=reflect_llm.model,
        temperature=reflect_llm.temperature,
        max_tokens=min(reflect_llm.max_tokens, 300),
    )
    content = raw.strip()
    if not content:
        return [], 0.0, None

    # Parse Q/A pairs into separate reflection nodes (each independently retrievable)
    new_nodes: list[MemoryNode] = []
    source_ids: list[str] = []
    for n in candidates[-8:]:
        source_ids.extend(n.source_event_ids)
    source_ids = list(dict.fromkeys(source_ids))

    # Split on Q/A pairs; fall back to storing the whole text as one node
    qa_pairs: list[str] = []
    lines = content.splitlines()
    current_pair: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("Q") and current_pair:
            qa_pairs.append(" ".join(current_pair))
            current_pair = [line]
        else:
            current_pair.append(line)
    if current_pair:
        qa_pairs.append(" ".join(current_pair))

    if not qa_pairs:
        qa_pairs = [content]

    for pair in qa_pairs:
        node = await store.append(
            db,
            node_type="reflection",
            content=pair,
            importance=min(10.0, 7.0 + len(candidates) * 0.15),
            turn_id=turn_id,
            tick=0,
            source_event_ids=source_ids,
            meta={"trigger": "importance_threshold", "accumulator_was": round(accumulator, 1)},
        )
        new_nodes.append(node)

    return new_nodes, 0.0, content
