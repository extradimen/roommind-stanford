"""
Single-agent Stanford loop:
  Seed Memory → Plan → Perceive → Retrieve → React (decide) → Act

Key differences from a plain chatbot:
  - The agent's PLAN (not the user's message) is the primary behavioural driver.
  - The decision prompt surfaces: seed identity, active plan, retrieved memories,
    new observations, and only then the user input.
  - "wait" means "I have a plan; I'm choosing not to act NOW", not "I don't know
    what to say."
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.act import ActionResult, decision_from_llm, execute_decision
from app.agent.memory_stream import (
    AgentMemoryStore,
    MemoryNode,
    active_plan,
    retrieve_memories,
)
from app.llm.client import llm_client
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.orchestrator.common import orch_support
from app.i18n.reply_language import decision_language_rule
from app.orchestrator.llm_binding import ResolvedLlm
from app.world.perception import perceive_events
from app.world.timeline import WorldEvent, WorldTimeline


@dataclass
class AgentLoopResult:
    character_id: str
    action: str
    spoke: bool = False
    content: str = ""
    emotion: str = "neutral"
    gesture: str = "talking"
    reasoning: str = ""
    plan_update: str | None = None
    internal_note: str | None = None
    new_observations: list[MemoryNode] = field(default_factory=list)
    retrieved: list[dict[str, Any]] = field(default_factory=list)
    decision_raw: str = ""
    action_result: ActionResult | None = None


def _loop_result_from_action(
    character_id: str,
    *,
    new_observations: list[MemoryNode],
    retrieved: list[dict[str, Any]],
    decision_raw: str,
    action_result: ActionResult,
) -> AgentLoopResult:
    return AgentLoopResult(
        character_id=character_id,
        action=action_result.action,
        spoke=action_result.spoke,
        content=action_result.content,
        emotion=action_result.emotion,
        gesture=action_result.gesture,
        reasoning=action_result.reasoning,
        plan_update=action_result.plan_update,
        internal_note=action_result.internal_note,
        new_observations=new_observations,
        retrieved=retrieved,
        decision_raw=decision_raw,
        action_result=action_result,
    )


def _format_retrieved_block(retrieved_scored: list[tuple[MemoryNode, float]]) -> str:
    """Format retrieved memories for the decision prompt, grouped by type."""
    if not retrieved_scored:
        return "（暂无相关记忆）"

    lines: list[str] = []
    for node, score in retrieved_scored:
        tag = {
            "observation": "观察",
            "reflection": "反思",
            "plan": "计划",
            "action": "行动",
        }.get(node.node_type, node.node_type)
        imp_bar = "█" * int(node.importance) + "░" * (10 - int(node.importance))
        lines.append(f"[{tag} imp={node.importance:.0f} {imp_bar}] {node.content}")
    return "\n".join(lines)


async def run_agent_tick(
    db: AsyncSession,
    *,
    character: CharacterTemplate,
    scenario: ScenarioTemplate,
    store: AgentMemoryStore,
    nodes: list[MemoryNode],
    new_events: list[WorldEvent],
    user_input: str,
    turn_id: int,
    tick: int,
    conversation_context: str,
    current_phase: str,
    decision_llm: ResolvedLlm,
    npc_llm: ResolvedLlm,
    retrieval_k: int = 10,
    retrieval_alpha: float = 1.0,
    retrieval_beta: float = 1.0,
    retrieval_gamma: float = 1.0,
    speak_quota_remaining: int = 1,
    mentioned: bool = False,
    timeline: WorldTimeline | None = None,
    reply_language: str = "zh",
) -> AgentLoopResult:
    """
    Stanford Generative Agent perceive → retrieve → react → act loop.

    Step 1  PERCEIVE   : filter world events → new observation nodes (with
                         permanent importance scores set at write time)
    Step 2  RETRIEVE   : score all memory nodes by recency + importance +
                         relevance; take top-k
    Step 3  REACT      : build a rich prompt that surfaces the agent's identity,
                         active plan, retrieved memories, new observations, and
                         the conversational context — then call the decision LLM
    Step 4  ACT        : execute the structured decision (speak / wait /
                         update_plan / internal_note)
    """

    # ------------------------------------------------------------------
    # Step 1 — PERCEIVE
    # ------------------------------------------------------------------
    perceived = perceive_events(character, new_events, reply_language=reply_language)
    existing_sources = {eid for n in nodes for eid in n.source_event_ids}
    new_obs_nodes: list[MemoryNode] = []
    for obs in perceived:
        if obs["source_event_id"] in existing_sources:
            continue
        node = await store.append(
            db,
            node_type="observation",
            content=obs["content"],
            importance=obs["importance"],   # ← set permanently at write time
            turn_id=turn_id,
            tick=tick,
            source_event_ids=[obs["source_event_id"]],
            meta={"event_type": obs["event_type"]},
        )
        new_obs_nodes.append(node)
        nodes.append(node)

    # ------------------------------------------------------------------
    # Step 2 — RETRIEVE
    # Compose query from: current user input + agent's responsibility +
    # recent observation content (what just happened)
    # ------------------------------------------------------------------
    recent_obs_text = " ".join(o.content for o in new_obs_nodes[-3:])
    query = f"{user_input} {character.responsibility} {recent_obs_text}"

    retrieved_scored = retrieve_memories(
        nodes,
        query=query,
        current_turn=turn_id,
        k=retrieval_k,
        alpha=retrieval_alpha,
        beta=retrieval_beta,
        gamma=retrieval_gamma,
    )

    # Always surface the active plan (even if not in top-k)
    plan = active_plan(nodes)
    retrieved_node_ids = {r[0].node_id for r in retrieved_scored}
    if plan and plan.node_id not in retrieved_node_ids:
        retrieved_scored.insert(0, (plan, 99.0))   # pin plan at top

    retrieved_debug: list[dict[str, Any]] = [
        {"type": n.node_type, "content": n.content, "score": round(s, 3)}
        for n, s in retrieved_scored
    ]
    memory_block = _format_retrieved_block(retrieved_scored)

    # ------------------------------------------------------------------
    # Step 3 — REACT  (decision LLM)
    # Prompt structure mirrors Stanford paper Figure 5:
    #   identity → plan → retrieved memories → new perceptions → context → action
    # ------------------------------------------------------------------
    private = character.private_state or {}
    new_obs_text = (
        "\n".join(f"• {o.content}" for o in new_obs_nodes)
        if new_obs_nodes
        else "（本轮无新观察）"
    )

    # Determine what "wait" means in context
    wait_guidance = (
        "你被点名，禁止只 wait；必须开口回应。"
        if mentioned
        else "你未被点名，可以选择 wait 等待更好时机（若计划不要求你此刻发言）。"
    )
    quota_guidance = (
        f"本轮剩余发言名额：{speak_quota_remaining}（还可发言）"
        if speak_quota_remaining > 0
        else "本轮发言名额已满，只能 wait 或 update_plan（不会显示在对话里）。"
    )

    decision_prompt = f"""你是生成式谈判 Agent「{character.display_name}」。
你的每一个决策都来自你自己的目标和计划，而非单纯响应用户。

━━━━━━━━━━━━━━━━━━━━
【身份 · 种子记忆】
性格：{character.persona}
职责：{character.responsibility}
行为倾向：{json.dumps(character.tendency, ensure_ascii=False)}
私密认知（只有你知道）：{json.dumps(private, ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━
【当前计划】（你进入会议室时制定，指导你的所有行动）
{plan.content if plan else "（尚未制定计划）"}

━━━━━━━━━━━━━━━━━━━━
【检索到的记忆】（按时效×重要性×相关性排序，最相关的在前）
{memory_block}

━━━━━━━━━━━━━━━━━━━━
【刚感知到的新事件】（本轮刚发生）
{new_obs_text}

━━━━━━━━━━━━━━━━━━━━
【对话上下文】（最近几轮）
{conversation_context[-800:]}

━━━━━━━━━━━━━━━━━━━━
【当前局面】
场景：{scenario.title} | 阶段：{current_phase}
用户刚说：「{user_input}」
{wait_guidance}
{quota_guidance}

━━━━━━━━━━━━━━━━━━━━
【决策指引】
你的决策优先级：
1. 计划驱动：你的行动首先服务于「当前计划」，而不是单纯回应用户。
2. 机会识别：用户的话是否给了你推进某个议题的机会？把握它。
3. 策略等待：如果此刻发言对你不利，选择 wait 是合理的。
4. 不重复：不要重复刚说过的内容。

{decision_language_rule(reply_language)}

输出严格 JSON（无其他文字）：
{{
  "action": "speak|wait|update_plan|internal_note",
  "reasoning": "简短说明：你的计划如何驱动这个决策（≤50字）",
  "speak": {{"content": "要说的话（action=speak时填写）", "emotion": "neutral|concerned|confident|firm", "gesture": "talking|nodding|thinking|leaning"}},
  "plan_update": "若 action=update_plan 则新计划内容，否则 null",
  "internal_note": "若 action=internal_note 则内心独白，否则 null",
  "moment_importance": 1到10的整数（这一刻对你的重要程度）
}}"""

    decision_raw = await llm_client.chat_completion(
        [{"role": "user", "content": decision_prompt}],
        db_provider=decision_llm.provider,
        db_model=decision_llm.model,
        temperature=decision_llm.temperature,
        max_tokens=min(decision_llm.max_tokens, 512),
        response_format={"type": "json_object"},
    )
    parsed = orch_support.parse_json(decision_raw)
    decision = decision_from_llm(parsed, decision_raw)

    # ------------------------------------------------------------------
    # Step 4 — ACT
    # ------------------------------------------------------------------
    action_result = await execute_decision(
        db,
        character=character,
        store=store,
        nodes=nodes,
        decision=decision,
        user_input=user_input,
        turn_id=turn_id,
        tick=tick,
        conversation_context=conversation_context,
        npc_llm=npc_llm,
        speak_quota_remaining=speak_quota_remaining,
        mentioned=mentioned,
        timeline=timeline,
        reply_language=reply_language,
    )

    return _loop_result_from_action(
        character.character_id,
        new_observations=new_obs_nodes,
        retrieved=retrieved_debug,
        decision_raw=decision.raw,
        action_result=action_result,
    )
