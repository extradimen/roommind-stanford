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
from app.scenario_side import initial_plan_goal_block, user_speaker_label
from app.i18n.reply_language import decision_language_rule
from app.orchestrator.common import orch_support
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
        return "(no relevant memories yet)"

    lines: list[str] = []
    for node, score in retrieved_scored:
        tag = {
            "observation": "observation",
            "reflection": "reflection",
            "plan": "plan",
            "action": "action",
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
    reply_language: str = "en",
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
        else "(no new observations this turn)"
    )

    wait_guidance = (
        "You were mentioned — you must not wait; respond verbally."
        if mentioned
        else "You were not mentioned — waiting is allowed if your plan does not require speaking now."
    )
    quota_guidance = (
        f"Speaking slots remaining this turn: {speak_quota_remaining}"
        if speak_quota_remaining > 0
        else "Speaking quota is full — only wait or update_plan (not shown in dialogue)."
    )
    goal_block = initial_plan_goal_block(character, scenario)
    user_label = user_speaker_label(character)

    decision_prompt = f"""You are generative negotiation agent "{character.display_name}".
Every decision must follow your own goals and plan, not react blindly to the user.

━━━━━━━━━━━━━━━━━━━━
[Identity · seed memory]
Persona: {character.persona}
Responsibility: {character.responsibility}
Behavior tendency: {json.dumps(character.tendency, ensure_ascii=False)}
Private knowledge (only you know): {json.dumps(private, ensure_ascii=False)}

━━━━━━━━━━━━━━━━━━━━
[Negotiation goals]
{goal_block}

━━━━━━━━━━━━━━━━━━━━
[Current plan] (set when you entered the room; guides all actions)
{plan.content if plan else "(no plan yet)"}

━━━━━━━━━━━━━━━━━━━━
[Retrieved memories] (recency × importance × relevance)
{memory_block}

━━━━━━━━━━━━━━━━━━━━
[New observations this turn]
{new_obs_text}

━━━━━━━━━━━━━━━━━━━━
[Dialogue context]
{conversation_context[-800:]}

━━━━━━━━━━━━━━━━━━━━
[Situation]
Scenario: {scenario.title} | Phase: {current_phase}
{user_label}: "{user_input}"
{wait_guidance}
{quota_guidance}

━━━━━━━━━━━━━━━━━━━━
[Decision guidance]
Priority:
1. Plan-driven: serve your current plan, not just the latest user message.
2. Opportunity: did the user open a topic you can advance?
3. Strategic wait: if speaking now hurts you, wait is valid.
4. No repetition: do not repeat what you just said.

{decision_language_rule(reply_language)}

Output strict JSON only:
{{
  "action": "speak|wait|update_plan|internal_note",
  "reasoning": "Brief: how your plan drives this decision (≤50 words, English)",
  "speak": {{"content": "What to say when action=speak", "emotion": "neutral|concerned|confident|firm", "gesture": "talking|nodding|thinking|leaning"}},
  "plan_update": "New plan text if action=update_plan, else null",
  "internal_note": "Inner monologue if action=internal_note, else null",
  "moment_importance": integer 1-10
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
