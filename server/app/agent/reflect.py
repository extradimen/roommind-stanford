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
from app.i18n.reply_language import plan_fallback_text
from app.llm.client import llm_client
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.orchestrator.llm_binding import ResolvedLlm
from app.scenario_side import goal_seed_text, initial_plan_goal_block


# ---------------------------------------------------------------------------
# Layer 1 – Seed Memory
# ---------------------------------------------------------------------------

def _build_seed_memories(character: CharacterTemplate, scenario: ScenarioTemplate) -> list[dict[str, Any]]:
    """
    Stanford: each agent starts with a paragraph of authored facts split into
    individual memory nodes (importance pre-rated, turn_id=0).
    """
    seeds: list[dict[str, Any]] = []

    seeds.append({
        "content": f"I am {character.display_name}. {character.persona}",
        "importance": 7.0,
    })
    seeds.append({
        "content": f"My responsibility in this meeting: {character.responsibility}",
        "importance": 8.0,
    })

    if character.tendency:
        tendency_desc = json.dumps(character.tendency, ensure_ascii=False)
        seeds.append({
            "content": f"My behavioral tendency: {tendency_desc}",
            "importance": 6.0,
        })

    if character.private_state:
        for key, value in character.private_state.items():
            seeds.append({
                "content": f"Private knowledge — {key}: {value}",
                "importance": 9.0,
            })

    seeds.append({
        "content": f"Negotiation scenario: {scenario.title}. {goal_seed_text(character, scenario)}",
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
    """Inject seed memories once per session (idempotent)."""
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
    scenario: ScenarioTemplate,
    decision_llm: ResolvedLlm,
    nodes: list[MemoryNode] | None = None,
) -> MemoryNode | None:
    """Generate a coarse opening plan from seed memories (once per session)."""
    if nodes is None:
        nodes = await store.load_all(db)

    if active_plan(nodes):
        return active_plan(nodes)

    seed_nodes = [n for n in nodes if n.meta.get("source") == "seed"]
    seed_facts = "\n".join(f"- {n.content}" for n in seed_nodes) if seed_nodes else "(no seed facts)"

    private = character.private_state or {}
    goal_block = initial_plan_goal_block(character, scenario)

    prompt = f"""You are {character.display_name}.
Persona: {character.persona}
Responsibility: {character.responsibility}
Private knowledge: {json.dumps(private, ensure_ascii=False)}

Background facts you already know:
{seed_facts}

Meeting: {scenario.title}
{goal_block}

Write a 2-3 sentence opening strategy plan in English:
- Which topic will you raise first?
- What is your bottom line?
- How will you open the conversation?

Output the plan only. No JSON. No explanation."""

    raw = await llm_client.chat_completion(
        [{"role": "user", "content": prompt}],
        db_provider=decision_llm.provider,
        db_model=decision_llm.model,
        temperature=decision_llm.temperature,
        max_tokens=min(decision_llm.max_tokens, 200),
    )
    plan_text = raw.strip()
    if not plan_text:
        plan_text = plan_fallback_text(character.responsibility)

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
    """Synthesise higher-order reflections when importance threshold is exceeded."""
    if accumulator < threshold:
        return [], accumulator, None

    candidates = sorted(
        [n for n in nodes if n.node_type == "observation" and n.importance >= 4.0],
        key=lambda n: (n.turn_id, n.importance),
    )[-12:]

    if len(candidates) < 2:
        return [], 0.0, None

    obs_lines = "\n".join(f"- (importance {n.importance}) {n.content}" for n in candidates[-8:])

    prompt = f"""You are {character.display_name}. Persona: {character.persona}. Responsibility: {character.responsibility}.

Recent facts you noticed in the meeting:
{obs_lines}

Recent dialogue:
{context[-600:]}

Complete two steps in English:
1. List 2 questions that matter most to you (negotiation situation, opponent intent, your risks).
2. For each question, write one-sentence inference (higher-order reflection, not dialogue).

Format:
Q1: <question>
A1: <inference>
Q2: <question>
A2: <inference>

Output the format above only."""

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

    new_nodes: list[MemoryNode] = []
    source_ids: list[str] = []
    for n in candidates[-8:]:
        source_ids.extend(n.source_event_ids)
    source_ids = list(dict.fromkeys(source_ids))

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
