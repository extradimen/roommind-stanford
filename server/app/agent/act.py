"""Action execution — decide output → world effects + NPC reply."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_stream import AgentMemoryStore, MemoryNode, active_plan
from app.agent.speech_safety import PUBLIC_RESPONSE_DRAFT, speech_rejection_reason
from app.llm.client import LLMEmptyContentError, llm_client
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.orchestrator.common import NPCReply
from app.orchestrator.llm_binding import ResolvedLlm
from app.public_ledger import (
    commit_public_intent,
    ground_public_intent_in_quote,
    validate_public_intent,
)
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
from app.telemetry import emit


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
    public_intent: dict[str, Any] = field(default_factory=dict)
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
    public_ledger_event: dict[str, Any] | None = None


def configured_public_fallback(configured: dict[str, Any] | None) -> str:
    """Return only fallback text explicitly authored as public dialogue.

    ``fallback_actions.default`` is an internal action instruction consumed by
    agent cognition and must never be copied into the meeting transcript.
    """
    return str((configured or {}).get("public_reply") or "").strip()


def contextual_public_fallback(
    character: CharacterTemplate,
    validated_intent: dict[str, Any] | None,
) -> str:
    """Return a conservative role-specific reply after renderer rejection.

    A single global clarification sentence can become a self-sustaining loop
    in autonomous sessions. This fallback remains non-committal while keeping
    the validated public subject and the speaker's public responsibility.
    """
    intent = validated_intent or {}
    subject = " ".join(str(intent.get("subject") or "the current issue").split())
    if len(subject) > 120:
        subject = subject[:117].rstrip() + "..."
    role = " ".join(
        str(character.job_title or character.responsibility or "role").split()
    )
    if len(role) > 80:
        role = role[:77].rstrip() + "..."
    if character.relationship_to_player in {"ally", "advisor", "teammate"}:
        return (
            f"From my {role} perspective, the next useful step on {subject} is to "
            "identify the responsible evidence owner and the specific decision still needed."
        )
    return (
        f"From my {role} perspective, {subject} remains open. I can discuss the "
        "available evidence now, but I cannot confirm a final outcome without the responsible owner."
    )


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
    reply_language: str = "en",
    validated_intent: dict[str, Any] | None = None,
) -> tuple[str, str, str, bool]:
    """
    Stanford: NPC speech is grounded in the agent's active plan.
    The plan is passed in so the NPC knows *why* they are speaking,
    not just *what* was decided in the draft.
    """
    draft = draft.strip()
    if not draft:
        return idle_ack(reply_language), emotion, gesture, False

    lang_rule = speech_language_rule(reply_language)

    npc_prompt = f"""You are playing {character.display_name} ({character.persona}).
You are in a multi-role task simulation. Speak naturally in 1-2 sentences based on your plan and intent.

Intent for this turn (from your decision): {reasoning}
Core content to convey: {draft}
Validated public-world intent: {validated_intent or {"kind": "statement", "transition": "proposed"}}

Recent dialogue:
{conversation_context[-600:]}

The user just said: {user_input}

Requirements:
- Speak like a real participant in this configured task; do not repeat the prompt
- Reflect your persona: {character.persona}
- Stay within these authority and action limits: {character.authority}
- Treat private goals, internal plans, hidden knowledge, redlines, and reservation
  values as secret. Never quote, summarize, or label them in public speech.
- Do not say phrases such as "my plan is", "I will first", "private knowledge",
  "real floor", or "reservation value".
- Finish every sentence; never return a visibly cut-off fragment.
- Never claim a stronger lifecycle state than the validated public-world intent.
- If the intent was downgraded, describe only the applied transition (for
  example, a commitment), not the requested completed action.
{lang_rule}
- Output only what you say aloud; no JSON or explanation

"""

    if character.system_prompt:
        npc_prompt = character.system_prompt + "\n\n" + npc_prompt

    rejection = ""
    for attempt in range(2):
        retry_rule = (
            f"\nPrevious candidate was rejected ({rejection}). Generate a fresh, complete, "
            "public-facing reply only.\n"
            if attempt
            else ""
        )
        try:
            content = await llm_client.chat_completion(
                [{"role": "user", "content": npc_prompt + retry_rule}],
                db_provider=npc_llm.provider,
                db_model=npc_llm.model,
                temperature=npc_llm.temperature,
                max_tokens=min(max(npc_llm.max_tokens, 512), 1024),
            )
        except LLMEmptyContentError:
            rejection = "empty_model_response"
            emit(
                "llm.degraded_fallback",
                component="npc_speech_render",
                character_id=character.character_id,
                fallback_action="retry_then_configured_reply",
            )
            continue
        cleaned = content.strip()
        rejection = speech_rejection_reason(
            cleaned,
            active_plan_text=active_plan_text,
            public_context=f"{conversation_context}\n{user_input}",
            validated_intent=validated_intent,
            public_draft_text=draft,
            protected_secrets=list(
                (character.private_state or {}).get("protected_secrets") or []
            ),
        ) or ""
        if rejection:
            emit(
                "llm.public_output.rejected",
                component="npc_speech_render",
                character_id=character.character_id,
                rejection_reason=rejection,
                retrying=attempt == 0,
            )
        if not rejection:
            return cleaned, emotion, gesture, True

    configured = character.fallback_actions or {}
    # ``fallback_actions.default`` is an internal action instruction (for
    # example, "Ask for the missing commercial conditions"), not dialogue.
    # Older code exposed that instruction verbatim after two rejected model
    # candidates.  Only an explicitly authored public reply may be spoken.
    fallback = configured_public_fallback(configured)
    if fallback and speech_rejection_reason(
        fallback,
        active_plan_text=active_plan_text,
        public_draft_text=draft,
        public_context=f"{conversation_context}\n{user_input}",
        validated_intent=validated_intent,
        protected_secrets=list(
            (character.private_state or {}).get("protected_secrets") or []
        ),
    ):
        fallback = ""
    if not fallback:
        fallback = contextual_public_fallback(character, validated_intent)
    if speech_rejection_reason(
        fallback,
        active_plan_text=active_plan_text,
        public_draft_text=draft,
        public_context=f"{conversation_context}\n{user_input}",
        validated_intent=validated_intent,
        protected_secrets=list(
            (character.private_state or {}).get("protected_secrets") or []
        ),
    ):
        fallback = "I cannot confirm a final outcome from the evidence currently on record."
    return fallback, emotion, gesture, False


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
    reply_language: str = "en",
    task_state: dict[str, Any] | None = None,
) -> ActionResult:
    plan = active_plan(nodes)
    content, emotion, gesture, intent_rendered = await render_npc_speech(
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
        validated_intent=decision.public_intent,
    )
    result.spoke = True
    result.content = content
    result.emotion = emotion
    result.gesture = gesture

    if decision.public_intent:
        decision.public_intent = ground_public_intent_in_quote(
            decision.public_intent, content
        )

    if (
        task_state is not None
        and decision.public_intent
        and decision.public_intent.get("commit_allowed", True)
        and intent_rendered
    ):
        ledger_event = commit_public_intent(
            task_state,
            intent=decision.public_intent,
            public_quote=content,
            tick=tick,
        )
        result.public_ledger_event = ledger_event

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
    reply_language: str = "en",
    task_state: dict[str, Any] | None = None,
    allow_retrospective: bool = False,
) -> ActionResult:
    """Execute a structured decision: memory writes + optional speech on world line."""

    decision.public_intent = validate_public_intent(
        character=character,
        intent=decision.public_intent,
        turn_id=turn_id,
        state=task_state,
        allow_retrospective=allow_retrospective,
    )
    emit(
        "public_ledger.intent.validated",
        actor_id=character.character_id,
        turn_id=turn_id,
        kind=decision.public_intent.get("kind"),
        requested_transition=decision.public_intent.get("requested_transition"),
        applied_transition=decision.public_intent.get("transition"),
        validation=decision.public_intent.get("validation"),
        validation_reason=decision.public_intent.get("validation_reason"),
        commit_allowed=decision.public_intent.get("commit_allowed"),
    )

    action = decision.action.lower()
    result = ActionResult(
        character_id=character.character_id,
        action=action,
        reasoning=decision.reasoning,
    )

    if action == "speak" and speak_quota_remaining <= 0:
        action = "wait"
        result.action = "wait"
        result.reasoning = decision.reasoning + " [speaking quota full; waiting instead]"

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

        if speak_quota_remaining > 0 and decision.speak_draft.strip():
            draft = decision.speak_draft.strip()
            result.action = "update_plan+speak"
            result.reasoning = decision.reasoning + " → updated plan and spoke"
            return await _apply_speak(
                result,
                db=db,
                store=store,
                nodes=nodes,
                character=character,
                conversation_context=conversation_context,
                user_input=user_input,
                reasoning=decision.reasoning + " (after plan update)",
                draft=draft,
                npc_llm=npc_llm,
                decision=decision,
                turn_id=turn_id,
                tick=speak_tick,
                timeline=timeline,
                reply_language=reply_language,
                task_state=task_state,
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
            draft = decision.speak_draft.strip() or PUBLIC_RESPONSE_DRAFT
            result.action = "internal_note+speak"
            return await _apply_speak(
                result,
                db=db,
                store=store,
                nodes=nodes,
                character=character,
                conversation_context=conversation_context,
                user_input=user_input,
                reasoning=decision.reasoning + " (after internal note)",
                draft=draft,
                npc_llm=npc_llm,
                decision=decision,
                turn_id=turn_id,
                tick=tick,
                timeline=timeline,
                reply_language=reply_language,
                task_state=task_state,
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
            task_state=task_state,
        )

    if action == "wait" and speak_quota_remaining > 0 and mentioned:
        draft = PUBLIC_RESPONSE_DRAFT
        result.action = "wait→speak"
        result.reasoning = decision.reasoning + " → mentioned; speaking instead"
        return await _apply_speak(
            result,
            db=db,
            store=store,
            nodes=nodes,
            character=character,
            conversation_context=conversation_context,
            user_input=user_input,
            reasoning="Respond because the character was explicitly addressed",
            draft=draft,
            npc_llm=npc_llm,
            decision=decision,
            turn_id=turn_id,
            tick=tick,
            timeline=timeline,
            reply_language=reply_language,
            task_state=task_state,
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
    reply_language: str = "en",
    task_state: dict[str, Any] | None = None,
    allow_retrospective: bool = False,
) -> ActionResult | None:
    """When no NPC spoke this turn, force one reply from the active plan."""
    plan = active_plan(nodes)
    if not plan and not user_input.strip():
        return None

    draft = PUBLIC_RESPONSE_DRAFT
    reasoning = f"Respond from current plan ({scenario.title} / {current_phase})"
    decision = AgentDecision(
        action="speak",
        reasoning=reasoning,
        speak_draft=draft,
        public_intent=validate_public_intent(
            character=character,
            intent={
                "kind": "statement",
                "subject": "current open issue",
                "transition": "proposed",
                # A fallback is a current meeting response. Scenario policy may
                # permit explicit historical examples, but it cannot turn all
                # fallback speech into retrospective evidence.
                "simulation_scope": "discussion",
            },
            turn_id=turn_id,
            state=task_state,
            allow_retrospective=allow_retrospective,
        ),
    )
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
        task_state=task_state,
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
        public_intent=dict(raw.get("public_intent") or {}),
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
        public_intent=(result.public_ledger_event or {}).get("validated_intent"),
        public_ledger_event=result.public_ledger_event,
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
