"""Action execution — decide output → world effects + NPC reply."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_stream import AgentMemoryStore, MemoryNode, active_plan
from app.llm.client import llm_client
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.orchestrator.common import NPCReply
from app.orchestrator.llm_binding import ResolvedLlm
from app.i18n.reply_language import (
    action_internal_note,
    action_internal_summary,
    action_plan_update,
    action_speak_summary,
    action_wait_message,
    character_display_name,
    idle_ack,
    speech_language_rule,
)
from app.world.timeline import WorldEvent, WorldTimeline


@dataclass
class AgentDecision:
    """Structured output from the decision LLM."""

    action: str
    reasoning: str = ""
    speak_draft: str = ""
    speak_emotion: str = "neutral"
    speak_gesture: str = "talking"
    plan_update: str | None = None
    internal_note: str | None = None
    moment_importance: float = 4.0
    raw: str = ""


@dataclass
class ActionResult:
    """Result of executing one agent action in the world."""

    character_id: str
    action: str
    reasoning: str = ""
    spoke: bool = False
    content: str = ""
    emotion: str = "neutral"
    gesture: str = "talking"
    plan_update: str | None = None
    internal_note: str | None = None
    memory_nodes: list[MemoryNode] = field(default_factory=list)
    world_events: list[WorldEvent] = field(default_factory=list)


async def render_npc_speech(
    *,
    character: CharacterTemplate,
    conversation_context: str,
    user_input: str,
    reasoning: str,
    draft: str,
    npc_llm: ResolvedLlm,
    emotion: str = "neutral",
    gesture: str = "talking",
    active_plan_text: str = "",
    reply_language: str = "zh",
) -> tuple[str, str, str]:
    """
    Stanford: NPC speech is grounded in the agent's active plan.
    The plan is passed in so the NPC knows *why* they are speaking,
    not just *what* was decided in the draft.
    """
    draft = draft.strip()
    if not draft:
        return idle_ack(reply_language), emotion, gesture

    plan_hint = f"你当前的行动计划：{active_plan_text}\n" if active_plan_text else ""
    lang_rule = speech_language_rule(reply_language)

    npc_prompt = f"""你扮演 {character.display_name}（{character.persona}）。
你在会议室里，根据自己的计划和意图自然开口，说 1-2 句符合你身份的口语。

{plan_hint}本次发言的意图（来自你的决策）：{reasoning}
要说的核心内容：{draft}

近期对话：
{conversation_context[-600:]}

对方刚说：{user_input}

要求：
- 像真人谈判那样说话，不要复述提示词
- 体现你的性格：{character.persona}
{lang_rule}
- 只输出你要说的话，不要 JSON 或解释

"""

    if character.system_prompt:
        npc_prompt = character.system_prompt + "\n\n" + npc_prompt

    content = await llm_client.chat_completion(
        [{"role": "user", "content": npc_prompt}],
        db_provider=npc_llm.provider,
        db_model=npc_llm.model,
        temperature=npc_llm.temperature,
        max_tokens=min(npc_llm.max_tokens, 256),
    )
    return content.strip() or draft, emotion, gesture


def plan_speak_draft(
    nodes: list[MemoryNode],
    *,
    plan_update: str | None,
    decision: AgentDecision,
    fallback: str,
) -> str:
    if decision.speak_draft.strip():
        return decision.speak_draft.strip()
    if plan_update:
        return plan_update
    current = active_plan(nodes)
    if current:
        return current.content
    return fallback


async def _record_action_memory(
    db: AsyncSession,
    store: AgentMemoryStore,
    result: ActionResult,
    nodes: list[MemoryNode],
    *,
    action_kind: str,
    summary: str,
    turn_id: int,
    tick: int,
    importance: float = 5.0,
    meta: dict[str, Any] | None = None,
) -> MemoryNode:
    node = await store.append(
        db,
        node_type="action",
        content=summary,
        importance=importance,
        turn_id=turn_id,
        tick=tick,
        is_active=False,
        meta={"action_kind": action_kind, **(meta or {})},
    )
    result.memory_nodes.append(node)
    nodes.append(node)
    return node


async def _apply_speak(
    result: ActionResult,
    *,
    db: AsyncSession,
    store: AgentMemoryStore,
    nodes: list[MemoryNode],
    character: CharacterTemplate,
    conversation_context: str,
    user_input: str,
    reasoning: str,
    draft: str,
    npc_llm: ResolvedLlm,
    decision: AgentDecision,
    turn_id: int,
    tick: int,
    timeline: WorldTimeline | None,
    reply_language: str = "zh",
) -> ActionResult:
    plan = active_plan(nodes)
    content, emotion, gesture = await render_npc_speech(
        character=character,
        conversation_context=conversation_context,
        user_input=user_input,
        reasoning=reasoning,
        draft=draft,
        npc_llm=npc_llm,
        emotion=decision.speak_emotion,
        gesture=decision.speak_gesture,
        active_plan_text=plan.content if plan else "",
        reply_language=reply_language,
    )
    result.spoke = True
    result.content = content
    result.emotion = emotion
    result.gesture = gesture

    if timeline is not None:
        evt = timeline.append(
            turn_id=turn_id,
            tick=tick,
            event_type="npc_speech",
            actor_id=character.character_id,
            content=content,
            meta={
                "display_name": character.display_name,
                "emotion": emotion,
                "gesture": gesture,
                "action": result.action,
            },
        )
        result.world_events.append(evt)

    await _record_action_memory(
        db,
        store,
        result,
        nodes,
        action_kind="speak",
        summary=action_speak_summary(content, reply_language),
        turn_id=turn_id,
        tick=tick,
        importance=6.5,
        meta={
            "emotion": emotion,
            "gesture": gesture,
            "action_label": result.action,
            "display_text": content,
        },
    )
    return result


async def execute_decision(
    db: AsyncSession,
    *,
    character: CharacterTemplate,
    store: AgentMemoryStore,
    nodes: list[MemoryNode],
    decision: AgentDecision,
    user_input: str,
    turn_id: int,
    tick: int,
    conversation_context: str,
    npc_llm: ResolvedLlm,
    speak_quota_remaining: int,
    mentioned: bool,
    timeline: WorldTimeline | None = None,
    reply_language: str = "zh",
) -> ActionResult:
    """Execute a structured decision: memory writes + optional speech on world line."""

    action = decision.action.lower()
    result = ActionResult(
        character_id=character.character_id,
        action=action,
        reasoning=decision.reasoning,
    )

    if action == "speak" and speak_quota_remaining <= 0:
        action = "wait"
        result.action = "wait"
        result.reasoning = decision.reasoning + " [发言名额已满，改为等待]"

    if action == "update_plan":
        plan_text = (decision.plan_update or "").strip()
        if plan_text:
            plan_node = await store.append(
                db,
                node_type="plan",
                content=plan_text,
                importance=8.0,
                turn_id=turn_id,
                tick=tick,
                is_active=True,
            )
            result.plan_update = plan_text
            result.memory_nodes.append(plan_node)
            nodes.append(plan_node)

            if timeline is not None:
                evt = timeline.append(
                    turn_id=turn_id,
                    tick=tick,
                    event_type="agent_action",
                    actor_id=character.character_id,
                    content=action_plan_update(plan_text, reply_language),
                    meta={
                        "display_name": character.display_name,
                        "action_kind": "update_plan",
                    },
                )
                result.world_events.append(evt)

        speak_tick = tick + (1 if result.world_events else 0)

        if speak_quota_remaining > 0:
            draft = plan_speak_draft(
                nodes,
                plan_update=plan_text or None,
                decision=decision,
                fallback=decision.reasoning or user_input,
            )
            result.action = "update_plan+speak"
            result.reasoning = decision.reasoning + " → 更新计划并发言"
            return await _apply_speak(
                result,
                db=db,
                store=store,
                nodes=nodes,
                character=character,
                conversation_context=conversation_context,
                user_input=user_input,
                reasoning=decision.reasoning + "（更新计划后执行）",
                draft=draft,
                npc_llm=npc_llm,
                decision=decision,
                turn_id=turn_id,
                tick=speak_tick,
                timeline=timeline,
                reply_language=reply_language,
            )

        if plan_text:
            await _record_action_memory(
                db,
                store,
                result,
                nodes,
                action_kind="update_plan",
                summary=action_plan_update(plan_text, reply_language),
                turn_id=turn_id,
                tick=tick,
                importance=7.0,
            )
        return result

    if action == "internal_note":
        note = (decision.internal_note or "").strip()
        if note:
            node = await store.append(
                db,
                node_type="observation",
                content=action_internal_note(note, reply_language),
                importance=decision.moment_importance,
                turn_id=turn_id,
                tick=tick,
                meta={"visibility": "private"},
            )
            result.internal_note = note
            result.memory_nodes.append(node)

        if speak_quota_remaining > 0 and mentioned:
            draft = plan_speak_draft(nodes, plan_update=None, decision=decision, fallback=user_input)
            result.action = "internal_note+speak"
            return await _apply_speak(
                result,
                db=db,
                store=store,
                nodes=nodes,
                character=character,
                conversation_context=conversation_context,
                user_input=user_input,
                reasoning=decision.reasoning + "（内心整理后回应）",
                draft=draft,
                npc_llm=npc_llm,
                decision=decision,
                turn_id=turn_id,
                tick=tick,
                timeline=timeline,
                reply_language=reply_language,
            )
        if note:
            await _record_action_memory(
                db,
                store,
                result,
                nodes,
                action_kind="internal_note",
                summary=action_internal_summary(note, reply_language),
                turn_id=turn_id,
                tick=tick,
                importance=4.0,
                meta={"visibility": "private"},
            )
        return result

    if action == "speak":
        draft = decision.speak_draft or decision.reasoning or user_input
        return await _apply_speak(
            result,
            db=db,
            store=store,
            nodes=nodes,
            character=character,
            conversation_context=conversation_context,
            user_input=user_input,
            reasoning=decision.reasoning,
            draft=draft,
            npc_llm=npc_llm,
            decision=decision,
            turn_id=turn_id,
            tick=tick,
            timeline=timeline,
            reply_language=reply_language,
        )

    if action == "wait" and speak_quota_remaining > 0 and mentioned:
        draft = plan_speak_draft(nodes, plan_update=None, decision=decision, fallback=user_input)
        result.action = "wait→speak"
        result.reasoning = decision.reasoning + " → 被点名，改为发言"
        return await _apply_speak(
            result,
            db=db,
            store=store,
            nodes=nodes,
            character=character,
            conversation_context=conversation_context,
            user_input=user_input,
            reasoning=decision.reasoning + "（被点名，按当前计划回应）",
            draft=draft,
            npc_llm=npc_llm,
            decision=decision,
            turn_id=turn_id,
            tick=tick,
            timeline=timeline,
            reply_language=reply_language,
        )

    if action == "wait" and timeline is not None:
        disp = character_display_name(character.character_id, character.display_name, reply_language)
        wait_msg = action_wait_message(disp, reply_language)
        evt = timeline.append(
            turn_id=turn_id,
            tick=tick,
            event_type="agent_action",
            actor_id=character.character_id,
            content=wait_msg,
            meta={"display_name": character.display_name, "action_kind": "wait"},
        )
        result.world_events.append(evt)

    if action == "wait":
        disp = character_display_name(character.character_id, character.display_name, reply_language)
        await _record_action_memory(
            db,
            store,
            result,
            nodes,
            action_kind="wait",
            summary=action_wait_message(disp, reply_language),
            turn_id=turn_id,
            tick=tick,
            importance=3.0,
        )

    return result


async def execute_plan_fallback_speak(
    db: AsyncSession,
    *,
    character: CharacterTemplate,
    scenario: ScenarioTemplate,
    store: AgentMemoryStore,
    nodes: list[MemoryNode],
    user_input: str,
    turn_id: int,
    tick: int,
    conversation_context: str,
    current_phase: str,
    npc_llm: ResolvedLlm,
    timeline: WorldTimeline,
    reply_language: str = "zh",
) -> ActionResult | None:
    """When no NPC spoke this turn, force one reply from the active plan."""
    plan = active_plan(nodes)
    if not plan and not user_input.strip():
        return None

    draft = plan.content if plan else f"回应：{user_input}"
    reasoning = f"按当前计划回应用户（{scenario.title} / {current_phase}）"
    decision = AgentDecision(action="speak", reasoning=reasoning, speak_draft=draft)
    result = ActionResult(
        character_id=character.character_id,
        action="plan_fallback_speak",
        reasoning=reasoning,
    )
    return await _apply_speak(
        result,
        db=db,
        store=store,
        nodes=nodes,
        character=character,
        conversation_context=conversation_context,
        user_input=user_input,
        reasoning=reasoning,
        draft=draft,
        npc_llm=npc_llm,
        decision=decision,
        turn_id=turn_id,
        tick=tick,
        timeline=timeline,
        reply_language=reply_language,
    )


def decision_from_llm(raw: dict[str, Any], raw_text: str = "") -> AgentDecision:
    speak = raw.get("speak") if isinstance(raw.get("speak"), dict) else {}
    return AgentDecision(
        action=str(raw.get("action", "wait")).lower(),
        reasoning=str(raw.get("reasoning", "")),
        speak_draft=str(speak.get("content") or ""),
        speak_emotion=str(speak.get("emotion", "neutral")),
        speak_gesture=str(speak.get("gesture", "talking")),
        plan_update=str(raw.get("plan_update") or "").strip() or None,
        internal_note=str(raw.get("internal_note") or "").strip() or None,
        moment_importance=float(raw.get("moment_importance", 4)),
        raw=raw_text[:500],
    )


def action_to_npc_reply(character: CharacterTemplate, result: ActionResult) -> NPCReply:
    return NPCReply(
        character_id=character.character_id,
        display_name=character.display_name,
        content=result.content,
        emotion=result.emotion,
        gesture=result.gesture,
        reasoning=result.reasoning,
    )


def iter_speech_stream_events(
    character: CharacterTemplate,
    result: ActionResult,
) -> Iterator[dict[str, Any]]:
    """WebSocket stream chunks for one NPC line."""
    cid = character.character_id
    yield {"type": "npc_start", "speaker_id": cid, "display_name": character.display_name}
    chunk_size = max(1, len(result.content) // 8)
    for i in range(0, len(result.content), chunk_size):
        yield {
            "type": "npc_delta",
            "speaker_id": cid,
            "delta": result.content[i : i + chunk_size],
        }
    yield {
        "type": "npc_done",
        "speaker_id": cid,
        "display_name": character.display_name,
        "text": result.content,
        "emotion": result.emotion,
        "gesture": result.gesture,
    }


async def yield_speech_stream(
    character: CharacterTemplate,
    result: ActionResult,
) -> AsyncIterator[dict[str, Any]]:
    for event in iter_speech_stream_events(character, result):
        yield event
