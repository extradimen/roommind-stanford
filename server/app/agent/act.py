"""Action execution — decide output → world effects + NPC reply."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_stream import AgentMemoryStore, MemoryNode, active_plan
from app.agent.speech_safety import (
    PUBLIC_RESPONSE_DRAFT,
    focus_question_target_mismatch_reason,
    near_duplicate_obligation_utterance,
    near_duplicate_public_utterance,
    public_speech_act_mismatch,
    retrospective_role_substitution_reason,
    retain_safe_public_clauses,
    speech_rejection_reason,
)
from app.llm.client import LLMEmptyContentError, llm_client
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.orchestrator.common import NPCReply
from app.orchestrator.llm_binding import ResolvedLlm
from app.player_character import resolve_player_character
from app.public_ledger import (
    align_explicit_confirmation_intent,
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
    public_intent: dict[str, Any] | None = None


def public_participant_aliases(scenario: ScenarioTemplate) -> dict[str, list[str]]:
    """Return the registered public names that may own in-session work."""
    player = resolve_player_character(scenario)
    aliases = {
        "user": [
            str(value) for value in (
                player.get("display_name"), player.get("character_name"),
                player.get("job_title"),
            ) if value
        ]
    }
    aliases.update({
        character.character_id: [
            str(value) for value in (
                character.display_name, character.character_name,
                character.job_title, *(character.aliases or []),
            ) if value
        ]
        for character in scenario.characters
    })
    return aliases


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
    kind = str(intent.get("kind") or "statement")
    transition = str(intent.get("transition") or "proposed")
    field = str(intent.get("field") or "").replace("_", " ").strip()
    topic = field or subject.replace("_", " ")
    if re.match(
        r"^(?:can|could|would|will|what|when|where|why|how|please)\b",
        topic,
        flags=re.IGNORECASE,
    ):
        topic = "the current evidence"

    if kind == "outcome" and transition == "blocked":
        return (
            f"We do not have enough verified evidence to close {topic} in this meeting. "
            "We should defer the final decision and record the remaining condition and follow-up owner."
        )

    # A rejected renderer must not expose the orchestration vocabulary in the
    # meeting ("remains open", "responsible owner", field identifiers, etc.).
    # Recover with ordinary task language and preserve the validated lifecycle.
    if kind in {"artifact", "verification", "action"}:
        return (
            f"For {topic}, let's separate what we can verify in this meeting from "
            "the material that must follow afterward. I can address the evidence "
            "within my responsibility now."
        )
    if transition == "blocked" or kind == "issue":
        return (
            f"The remaining concern is {topic}. Let's state the evidence we have, "
            "the decision we can make today, and any follow-up that still needs an owner."
        )
    if character.relationship_to_player in {"ally", "advisor", "teammate"}:
        return (
            f"On {topic}, I suggest we use the evidence already stated to make the "
            "narrowest defensible decision, then record any external follow-up separately."
        )
    return (
        f"On {topic}, I can explain the evidence within my responsibility. Any final "
        "approval should follow after the remaining condition is stated clearly."
    )


def required_response_public_fallback(character: CharacterTemplate) -> str:
    """Last-resort public answer for a role that owns the current floor.

    This sentence deliberately carries no lifecycle transition or external
    evidence claim. It is safe to publish without a ledger commit and prevents
    a rejected model draft from silently transferring the role's floor.
    """
    role = " ".join(str(getattr(character, "job_title", None) or "participant").split())
    return (
        f"From my role as {role}, I cannot confirm the requested point beyond "
        "the public evidence already stated. It should remain unresolved until "
        "the responsible evidence is available."
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
    prior_utterances: list[str] | None = None,
    prior_public_utterances: list[dict[str, str]] | None = None,
    coordinator_focus: dict[str, Any] | None = None,
    participant_aliases: dict[str, list[str]] | None = None,
    interview_mode: bool = False,
    required_response: bool = False,
) -> tuple[str, str, str, bool]:
    """
    Stanford: NPC speech is grounded in the agent's active plan.
    The plan is passed in so the NPC knows *why* they are speaking,
    not just *what* was decided in the draft.
    """
    draft = draft.strip()
    if not draft:
        return idle_ack(reply_language), emotion, gesture, False
    if near_duplicate_public_utterance(draft, prior_utterances or []):
        emit(
            "dialogue.near_duplicate.suppressed",
            component="npc_speech_render",
            character_id=character.character_id,
            source="decision_draft",
        )
        draft = PUBLIC_RESPONSE_DRAFT
    if near_duplicate_obligation_utterance(
        draft, prior_public_utterances or [],
        speaker_id=character.character_id,
        focus=coordinator_focus,
        public_intent=validated_intent,
    ):
        emit(
            "dialogue.obligation_duplicate.suppressed",
            component="npc_speech_render",
            character_id=character.character_id,
            obligation_id=(coordinator_focus or {}).get("obligation_id"),
            source="decision_draft",
        )
        draft = PUBLIC_RESPONSE_DRAFT

    # The decision model already produced public-facing speech together with
    # its structured intent.  If that draft passes the exact same boundary
    # checks, publish it directly instead of asking a second model call to
    # paraphrase the whole utterance.  G3.4's unconditional paraphrase step was
    # the main source of draft-echo rejections and visible fallback loops.
    draft_is_instruction = bool(re.match(
        r"^(?:state|say|explain|respond|ask|tell|mention|note|clarify|discuss)\b",
        draft,
        flags=re.IGNORECASE,
    ))
    if draft != PUBLIC_RESPONSE_DRAFT and not draft_is_instruction:
        draft_rejection = retrospective_role_substitution_reason(
            draft,
            speaker_id=character.character_id,
            participant_aliases=participant_aliases,
            validated_intent=validated_intent,
            interview_mode=interview_mode,
        ) or (
            "speech_act_mismatch"
            if public_speech_act_mismatch(reasoning, draft)
            else speech_rejection_reason(
                draft,
                active_plan_text=active_plan_text,
                public_context=f"{conversation_context}\n{user_input}",
                validated_intent=validated_intent,
                protected_secrets=list(
                    (character.private_state or {}).get("protected_secrets") or []
                ),
                private_constraints=[
                    *list((character.private_state or {}).get("discoverable_information") or []),
                    *list((character.private_state or {}).get("hidden_agenda") or []),
                ],
                participant_aliases=participant_aliases,
            )
        ) or focus_question_target_mismatch_reason(
            draft,
            speaker_id=character.character_id,
            focus=coordinator_focus,
            public_intent=validated_intent,
            participant_aliases=participant_aliases,
        )
        if not draft_rejection:
            emit(
                "dialogue.validated_draft.used",
                component="npc_speech_render",
                character_id=character.character_id,
            )
            return draft, emotion, gesture, True
        repaired_draft = retain_safe_public_clauses(
            draft, validated_intent=validated_intent
        )
        if repaired_draft and repaired_draft != draft:
            repaired_rejection = retrospective_role_substitution_reason(
                repaired_draft,
                speaker_id=character.character_id,
                participant_aliases=participant_aliases,
                validated_intent=validated_intent,
                interview_mode=interview_mode,
            ) or (
                "speech_act_mismatch"
                if public_speech_act_mismatch(reasoning, repaired_draft)
                else speech_rejection_reason(
                    repaired_draft,
                    active_plan_text=active_plan_text,
                    public_context=f"{conversation_context}\n{user_input}",
                    validated_intent=validated_intent,
                    protected_secrets=list(
                        (character.private_state or {}).get("protected_secrets") or []
                    ),
                    private_constraints=[
                        *list((character.private_state or {}).get("discoverable_information") or []),
                        *list((character.private_state or {}).get("hidden_agenda") or []),
                    ],
                    participant_aliases=participant_aliases,
                )
            ) or focus_question_target_mismatch_reason(
                repaired_draft,
                speaker_id=character.character_id,
                focus=coordinator_focus,
                public_intent=validated_intent,
                participant_aliases=participant_aliases,
            )
            if not repaired_rejection and near_duplicate_public_utterance(
                repaired_draft, prior_utterances or []
            ):
                repaired_rejection = "near_duplicate_same_speaker"
            if not repaired_rejection and near_duplicate_obligation_utterance(
                repaired_draft, prior_public_utterances or [],
                speaker_id=character.character_id,
                focus=coordinator_focus,
                public_intent=validated_intent,
            ):
                repaired_rejection = "near_duplicate_cross_role_obligation"
            if not repaired_rejection:
                emit(
                    "dialogue.public_clause_repair.used",
                    component="npc_speech_render",
                    character_id=character.character_id,
                    rejection_reason=draft_rejection,
                )
                return repaired_draft, emotion, gesture, True

    lang_rule = speech_language_rule(reply_language)

    npc_prompt = f"""You are playing {character.display_name} ({character.persona}).
You are in a multi-role task simulation. Speak naturally in 1-2 sentences based on your plan and intent.

Intent for this turn (from your decision): {reasoning}
Core content to convey: {draft}
Validated public-world intent: {validated_intent or {"kind": "statement", "transition": "proposed"}}
Current task-critical focus and authorized response owners: {coordinator_focus or {}}

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
- Do not expose field identifiers or orchestration phrases such as "remains open",
  "responsible owner", or "final outcome". Use ordinary role-appropriate language.
- Do not promise or request the same external upload again. State the substantive
  evidence available now and treat an unavailable file as a post-meeting follow-up.
- A question asking whether something happened is not evidence that it happened.
  Never convert a question or request for confirmation into an affirmative fact.
- When the current focus lists owner_ids, route questions about that focus only
  to one of those owners. Do not ask another role to certify the owner's work.
- A completed current-world operation (deployment, containment, upload, archive,
  health check, verification, publication, or similar side effect) may be reported
  only when the validated intent names a registered simulated tool result. Otherwise
  speak about the proposed next action, a condition, or an external follow-up.
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
                max_tokens=min(max(npc_llm.max_tokens, 1024), 1536),
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
        if public_speech_act_mismatch(reasoning, cleaned):
            rejection = "speech_act_mismatch"
            emit(
                "llm.public_output.rejected",
                component="npc_speech_render",
                character_id=character.character_id,
                rejection_reason=rejection,
                retrying=attempt == 0,
            )
            continue
        if near_duplicate_public_utterance(cleaned, prior_utterances or []):
            rejection = "near_duplicate_same_speaker"
            emit(
                "llm.public_output.rejected",
                component="npc_speech_render",
                character_id=character.character_id,
                rejection_reason=rejection,
                retrying=attempt == 0,
            )
            continue
        if near_duplicate_obligation_utterance(
            cleaned, prior_public_utterances or [],
            speaker_id=character.character_id,
            focus=coordinator_focus,
            public_intent=validated_intent,
        ):
            rejection = "near_duplicate_cross_role_obligation"
            emit(
                "dialogue.obligation_duplicate.suppressed",
                component="npc_speech_render",
                character_id=character.character_id,
                obligation_id=(coordinator_focus or {}).get("obligation_id"),
                source="rendered_candidate",
            )
            continue
        rejection = retrospective_role_substitution_reason(
            cleaned,
            speaker_id=character.character_id,
            participant_aliases=participant_aliases,
            validated_intent=validated_intent,
            interview_mode=interview_mode,
        ) or speech_rejection_reason(
            cleaned,
            active_plan_text=active_plan_text,
            public_context=f"{conversation_context}\n{user_input}",
            validated_intent=validated_intent,
            public_draft_text=draft,
            protected_secrets=list(
                (character.private_state or {}).get("protected_secrets") or []
            ),
            private_constraints=[
                *list((character.private_state or {}).get("discoverable_information") or []),
                *list((character.private_state or {}).get("hidden_agenda") or []),
            ],
            participant_aliases=participant_aliases,
        ) or focus_question_target_mismatch_reason(
            cleaned,
            speaker_id=character.character_id,
            focus=coordinator_focus,
            public_intent=validated_intent,
            participant_aliases=participant_aliases,
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
    fallback_intent_rendered = True
    if fallback and near_duplicate_public_utterance(fallback, prior_utterances or []):
        emit(
            "dialogue.near_duplicate.suppressed",
            component="npc_speech_render",
            character_id=character.character_id,
            source="configured_public_fallback",
        )
        fallback = ""
    if fallback and near_duplicate_obligation_utterance(
        fallback, prior_public_utterances or [],
        speaker_id=character.character_id,
        focus=coordinator_focus,
        public_intent=validated_intent,
    ):
        emit(
            "dialogue.obligation_duplicate.suppressed",
            component="npc_speech_render",
            character_id=character.character_id,
            obligation_id=(coordinator_focus or {}).get("obligation_id"),
            source="configured_public_fallback",
        )
        fallback = ""
    if fallback and public_speech_act_mismatch(reasoning, fallback):
        fallback = ""
    if fallback:
        fallback_rejection = speech_rejection_reason(
            fallback,
            active_plan_text=active_plan_text,
            public_draft_text=draft,
            public_context=f"{conversation_context}\n{user_input}",
            validated_intent=validated_intent,
            protected_secrets=list(
                (character.private_state or {}).get("protected_secrets") or []
            ),
            private_constraints=[
                *list((character.private_state or {}).get("discoverable_information") or []),
                *list((character.private_state or {}).get("hidden_agenda") or []),
            ],
            participant_aliases=participant_aliases,
        ) or focus_question_target_mismatch_reason(
            fallback,
            speaker_id=character.character_id,
            focus=coordinator_focus,
            public_intent=validated_intent,
            participant_aliases=participant_aliases,
        )
        if fallback_rejection:
            fallback = ""
    if not fallback and required_response:
        # An explicitly addressed participant owns the public floor.  Letting
        # a rejected renderer collapse to silence permits a later participant
        # (or the autonomous player) to answer on their behalf.  Use the same
        # bounded, role-aware fallback and pass it through the full publication
        # boundary before allowing that floor to advance.
        fallback_subject = str(
            (validated_intent or {}).get("subject") or "the current question"
        ).replace("_", " ")
        candidates = [
            contextual_public_fallback(character, validated_intent),
            (
                f"For {fallback_subject}, I do not have a new verified fact to add. "
                "I can answer a narrower question within my responsibility."
            ),
            (
                f"I cannot confirm anything further about {fallback_subject} from "
                "the evidence currently stated. The remaining point should stay "
                "unresolved until it is supported."
            ),
        ]
        for candidate in candidates:
            candidate_rejection = (
                "near_duplicate_same_speaker"
                if near_duplicate_public_utterance(candidate, prior_utterances or [])
                else ""
            ) or (
                "near_duplicate_obligation"
                if near_duplicate_obligation_utterance(
                    candidate,
                    prior_public_utterances or [],
                    speaker_id=character.character_id,
                    focus=coordinator_focus,
                    public_intent=validated_intent,
                )
                else ""
            ) or speech_rejection_reason(
                candidate,
                active_plan_text=active_plan_text,
                public_draft_text=draft,
                public_context=f"{conversation_context}\n{user_input}",
                validated_intent=validated_intent,
                protected_secrets=list(
                    (character.private_state or {}).get("protected_secrets") or []
                ),
                private_constraints=[
                    *list((character.private_state or {}).get("discoverable_information") or []),
                    *list((character.private_state or {}).get("hidden_agenda") or []),
                ],
                participant_aliases=participant_aliases,
            ) or focus_question_target_mismatch_reason(
                candidate,
                speaker_id=character.character_id,
                focus=coordinator_focus,
                public_intent=validated_intent,
                participant_aliases=participant_aliases,
            )
            if not candidate_rejection:
                fallback = candidate
                break
        if not fallback:
            # The validated lifecycle intent can itself be the reason every
            # contextual candidate is rejected.  The addressed role still
            # owns this floor, so make one final publication-only attempt
            # with no state transition attached.  ``_apply_speak`` repeats
            # this boundary after quote grounding and clears the intent,
            # ensuring this answer cannot mutate the public ledger.
            candidate = required_response_public_fallback(character)
            candidate_rejection = (
                "near_duplicate_same_speaker"
                if near_duplicate_public_utterance(candidate, prior_utterances or [])
                else ""
            ) or speech_rejection_reason(
                candidate,
                active_plan_text=active_plan_text,
                public_draft_text=draft,
                public_context=f"{conversation_context}\n{user_input}",
                validated_intent=None,
                protected_secrets=list(
                    (character.private_state or {}).get("protected_secrets") or []
                ),
                private_constraints=[
                    *list((character.private_state or {}).get("discoverable_information") or []),
                    *list((character.private_state or {}).get("hidden_agenda") or []),
                ],
                participant_aliases=participant_aliases,
            )
            if not candidate_rejection:
                fallback = candidate
                fallback_intent_rendered = False
                emit(
                    "dialogue.required_response.fallback_used",
                    component="npc_speech_render",
                    character_id=character.character_id,
                    reason=rejection or "contextual_candidates_rejected",
                )
    if not fallback:
        # A reusable deterministic sentence is visibly artificial and became
        # the dominant G3.4/G3.5 dialogue failure.  After two bounded repairs,
        # silence is safer and more realistic than publishing orchestration
        # language.  The multi-party orchestrator may try another participant.
        emit(
            "dialogue.silent_recovery.used",
            component="npc_speech_render",
            character_id=character.character_id,
            rejection_reason=rejection or "configured_reply_unavailable",
        )
        return "", emotion, gesture, False
    emit(
        "dialogue.safe_fallback.used",
        component="npc_speech_render",
        character_id=character.character_id,
        rejection_reason=rejection or "configured_reply_unavailable",
        fallback_kind="configured_public_reply",
    )
    return fallback, emotion, gesture, fallback_intent_rendered


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
    participant_aliases: dict[str, list[str]] | None = None,
    interview_mode: bool = False,
    required_response: bool = False,
) -> ActionResult:
    plan = active_plan(nodes)
    prior_utterances = [
        str((node.meta or {}).get("display_text") or "")
        for node in nodes
        if node.node_type == "action" and (node.meta or {}).get("display_text")
    ][-4:]
    prior_public_utterances = [
        {
            "speaker_id": event.actor_id,
            "content": event.content,
            "obligation_id": str((event.meta or {}).get("obligation_id") or ""),
        }
        for event in ((timeline.events if timeline is not None else [])[-12:])
        if event.event_type in {"user_speech", "npc_speech"}
    ]
    coordinator_focus = (
        ((task_state or {}).get("progress") or {}).get("focus") or {}
    )
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
        prior_utterances=prior_utterances,
        prior_public_utterances=prior_public_utterances,
        coordinator_focus=coordinator_focus,
        participant_aliases=participant_aliases,
        interview_mode=interview_mode,
        required_response=required_response,
    )
    if decision.public_intent and content.strip():
        decision.public_intent = ground_public_intent_in_quote(
            decision.public_intent, content
        )
        if decision.public_intent.get("quote_grounding") == "material_clause":
            emit(
                "public_ledger.intent.clause_grounded",
                character_id=character.character_id,
                turn_id=turn_id,
                field=decision.public_intent.get("field"),
                transition=decision.public_intent.get("transition"),
            )

        # Quote grounding can lower an apparently valid structured transition
        # after the renderer has produced the final public words.  Re-run the
        # public guard against that grounded state before publishing anything;
        # otherwise rejected state could still leak as accepted speech.
        rejection = speech_rejection_reason(
            content,
            active_plan_text=plan.content if plan else "",
            public_context=f"{conversation_context}\n{user_input}",
            validated_intent=decision.public_intent,
            participant_aliases=participant_aliases,
        )
        if rejection:
            repaired = retain_safe_public_clauses(
                content, validated_intent=decision.public_intent,
            )
            repaired_rejection = (
                speech_rejection_reason(
                    repaired,
                    active_plan_text=plan.content if plan else "",
                    public_context=f"{conversation_context}\n{user_input}",
                    validated_intent=decision.public_intent,
                    participant_aliases=participant_aliases,
                )
                if repaired else rejection
            )
            if repaired and not repaired_rejection:
                content = repaired
                decision.public_intent = ground_public_intent_in_quote(
                    decision.public_intent, content
                )
                emit(
                    "llm.public_output.clause_repaired",
                    component="agent_act",
                    character_id=character.character_id,
                    turn_id=turn_id,
                    reason=rejection,
                )
            else:
                emit(
                    "llm.public_output.rejected",
                    component="agent_act",
                    character_id=character.character_id,
                    turn_id=turn_id,
                    reason=rejection,
                )
                if required_response:
                    last_resort = required_response_public_fallback(character)
                    last_resort_rejection = speech_rejection_reason(
                        last_resort,
                        active_plan_text=plan.content if plan else "",
                        public_context=f"{conversation_context}\n{user_input}",
                        validated_intent=None,
                        participant_aliases=participant_aliases,
                    )
                    if not last_resort_rejection:
                        content = last_resort
                        decision.public_intent = {}
                        intent_rendered = False
                        emit(
                            "dialogue.required_response.fallback_used",
                            component="agent_act",
                            character_id=character.character_id,
                            turn_id=turn_id,
                            reason=rejection,
                        )
                    else:
                        content = ""
                        intent_rendered = False
                else:
                    content = ""
                    intent_rendered = False
                if not content:
                    emit(
                        "dialogue.silent_recovery.used",
                        component="agent_act",
                        character_id=character.character_id,
                        turn_id=turn_id,
                        reason="post_grounding_public_output_rejected",
                    )

    result.spoke = bool(content.strip())
    result.content = content
    result.emotion = emotion
    result.gesture = gesture

    if decision.public_intent and result.spoke:
        # Preserve the validated conversational target even when an ordinary
        # question/statement does not create a public-ledger event.  G4.1 lost
        # this metadata and had to guess floor ownership from display text.
        result.public_intent = dict(decision.public_intent)

    if (
        task_state is not None
        and decision.public_intent
        and decision.public_intent.get("commit_allowed", True)
        and intent_rendered
        and result.spoke
    ):
        ledger_event = commit_public_intent(
            task_state,
            intent=decision.public_intent,
            public_quote=content,
            tick=tick,
        )
        result.public_ledger_event = ledger_event

    if timeline is not None and result.spoke:
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
                "obligation_id": str((coordinator_focus or {}).get("obligation_id") or ""),
            },
        )
        result.world_events.append(evt)

    if not result.spoke:
        return result

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
    task_config: dict[str, Any] | None = None,
    allow_retrospective: bool = False,
    participant_aliases: dict[str, list[str]] | None = None,
    required_response: bool = False,
) -> ActionResult:
    """Execute a structured decision: memory writes + optional speech on world line."""

    decision.public_intent = align_explicit_confirmation_intent(
        character=character,
        intent=decision.public_intent,
        public_quote=decision.speak_draft if decision.action.lower() == "speak" else "",
        state=task_state,
    )
    if decision.public_intent.get("alignment") == "explicit_authorized_confirmation":
        emit(
            "task_state.confirmation_intent.aligned",
            character_id=character.character_id,
            turn_id=turn_id,
            field=decision.public_intent.get("field"),
        )
    decision.public_intent = validate_public_intent(
        character=character,
        intent=decision.public_intent,
        turn_id=turn_id,
        state=task_state,
        task_config=task_config,
        allow_retrospective=allow_retrospective,
    )
    if decision.action.lower() == "speak" and decision.speak_draft.strip():
        # Ground the model's own proposed quote before rendering.  This makes
        # transition validation and public wording one atomic decision, while
        # the second check in ``_apply_speak`` protects the final paraphrase.
        decision.public_intent = ground_public_intent_in_quote(
            decision.public_intent, decision.speak_draft,
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
                participant_aliases=participant_aliases,
                interview_mode=allow_retrospective,
                required_response=required_response,
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
                participant_aliases=participant_aliases,
                interview_mode=allow_retrospective,
                required_response=required_response,
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
            participant_aliases=participant_aliases,
            interview_mode=allow_retrospective,
            required_response=required_response,
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
            participant_aliases=participant_aliases,
            interview_mode=allow_retrospective,
            required_response=required_response,
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
    required_response: bool = False,
) -> ActionResult | None:
    """When no NPC spoke this turn, force one reply from the active plan."""
    plan = active_plan(nodes)
    if not plan and not user_input.strip():
        return None

    draft = PUBLIC_RESPONSE_DRAFT
    reasoning = f"Respond from current plan ({scenario.title} / {current_phase})"
    focus = (((task_state or {}).get("progress") or {}).get("focus") or {})
    resolving = focus.get("kind") == "outcome_resolution"
    fallback_subject = str(focus.get("subject") or "current open issue")
    decision = AgentDecision(
        action="speak",
        reasoning=reasoning,
        speak_draft=draft,
        public_intent=validate_public_intent(
            character=character,
            intent={
                "kind": "outcome" if resolving else "statement",
                "subject": fallback_subject,
                "transition": "blocked" if resolving else "proposed",
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
        participant_aliases=public_participant_aliases(scenario),
        interview_mode=allow_retrospective,
        required_response=required_response,
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
        public_intent=(
            result.public_intent
            or (result.public_ledger_event or {}).get("validated_intent")
        ),
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
