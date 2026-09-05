"""AI player for autonomous test sessions.

The player is intentionally built from public scenario information only. NPC
private_state and system prompts must never be included in this context.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_stream import AgentMemoryStore, active_plan
from app.agent.speech_safety import (
    near_duplicate_public_utterance,
    npc_directed_question_handoff_reason,
    player_speech_rejection_reason,
    resolve_direct_question_target,
    retain_safe_public_clauses,
)
from app.llm.client import LLMEmptyContentError, llm_client
from app.models.db import GameSession, ScenarioTemplate
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.player_character import resolve_player_character
from app.public_ledger import validate_public_intent
from app.scenario_side import resolve_player_side_goal
from app.telemetry import emit


@dataclass
class PlayerMove:
    content: str
    intent: str
    requested_end: bool
    model_label: str
    raw: str
    public_intent: dict[str, Any] | None = None


def normalize_player_content(value: Any) -> str:
    """Unwrap models that place a second JSON response inside content."""
    current: Any = value
    for _ in range(3):
        if not isinstance(current, str):
            return ""
        text = current.strip()
        if not text.startswith(("{", "[", "```")):
            return text
        parsed = orch_support.parse_json(text)
        nested = parsed.get("content") if isinstance(parsed, dict) else None
        if not isinstance(nested, str) or nested.strip() == text:
            return text
        current = nested
    return str(current).strip()


def _public_character_context(scenario: ScenarioTemplate) -> list[dict[str, str]]:
    return [
        {
            "character_id": char.character_id,
            "display_name": char.display_name,
            "job_title": char.job_title,
            "side": char.side,
            "team_id": char.team_id,
            "relationship_to_player": char.relationship_to_player,
            "interaction_role": char.interaction_role,
            "responsibility": char.responsibility,
        }
        for char in sorted(scenario.characters, key=lambda c: c.sort_order)
    ]


def _public_participant_aliases(
    scenario: ScenarioTemplate,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Build a public-only participant directory shared by both conditions."""
    player = resolve_player_character(scenario)
    aliases: dict[str, list[str]] = {
        "user": [
            str(value) for value in (
                player.get("display_name"), player.get("character_name"),
                player.get("job_title"),
            ) if value
        ],
    }
    labels = {
        "user": str(player.get("character_name") or player.get("display_name") or "Player")
    }
    for character in scenario.characters:
        aliases[character.character_id] = [
            str(value) for value in (
                character.display_name, character.character_name,
                character.job_title, *(character.aliases or []),
            ) if value
        ]
        labels[character.character_id] = str(
            character.character_name or character.display_name or character.character_id
        )
    return aliases, labels


def bounded_dialogue(
    messages: list[dict[str, Any]],
    *,
    message_limit: int = 30,
    character_limit: int = 5000,
) -> str:
    """Build recent public dialogue without allowing test prompts to grow forever."""
    safe_message_limit = max(1, min(int(message_limit), 100))
    safe_character_limit = max(500, min(int(character_limit), 12000))
    recent = messages[-safe_message_limit:]
    dialogue = "\n".join(
        f"[{m.get('speaker_id', 'unknown')}]: {m.get('content', '')}" for m in recent
    )
    if not dialogue:
        return "(The meeting has not started. Make a concise opening statement.)"
    return dialogue[-safe_character_limit:]


def public_acceptance_guard(task_config: dict[str, Any] | None) -> str:
    """Make public decision thresholds salient to the shared player policy."""
    root = (task_config or {}).get("completion_conditions") or {}
    rows = []
    for group in ("all", "any"):
        for condition in root.get(group) or []:
            if not isinstance(condition, dict) or not condition.get("field"):
                continue
            rows.append({
                "group": group,
                "field": condition.get("field"),
                "operator": condition.get("operator", "=="),
                "target": condition.get("value"),
                "required_status": condition.get("required_status", "confirmed"),
            })
    if not rows:
        return "No structured public decision threshold is configured."
    return (
        f"Public decision thresholds: {json.dumps(rows, ensure_ascii=False)}. "
        "Do not call a package final or explicitly accept a field value that fails "
        "the corresponding threshold. Acknowledge it only as an interim proposal, "
        "counteroffer, or explicitly bounded exception."
    )


def recent_player_utterances(messages: list[dict[str, Any]]) -> list[str]:
    return [
        str(message.get("content") or "")
        for message in messages
        if message.get("speaker_type") == "user" or message.get("speaker_id") == "user"
    ][-4:]


def pending_public_questions(
    messages: list[dict[str, Any]],
    *,
    participant_aliases: dict[str, list[str]] | None = None,
    participant_labels: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Return direct NPC questions since the player's most recent message."""
    tail: list[dict[str, Any]] = []
    for message in reversed(messages):
        if message.get("speaker_type") == "user" or message.get("speaker_id") == "user":
            break
        tail.append(message)
    questions: list[dict[str, str]] = []
    for message in reversed(tail):
        speaker_id = str(message.get("speaker_id") or "unknown")
        # A later utterance by the addressed NPC satisfies that floor
        # obligation.  Do not make the player hand the same question back
        # after the responsible role has already answered it.
        questions = [
            row for row in questions
            if row.get("target_id") in {"", "user"}
            or row.get("target_id") != speaker_id
        ]
        content = str(message.get("content") or "").strip()
        public_intent = ((message.get("meta") or {}).get("public_intent") or {})
        if "?" in content or resolve_direct_question_target(
            content,
            public_intent=public_intent,
            participant_aliases=participant_aliases,
        ):
            # Keep complete question sentences.  Taking the last N characters
            # of a long message used to start mid-word and leaked malformed
            # fragments into the next autonomous player turn.
            parts = re.split(r"(?<=[.!?])\s+|[\r\n]+", content)
            complete = [
                " ".join(part.split()) for part in parts
                if "?" in part or resolve_direct_question_target(
                    part,
                    public_intent=public_intent,
                    participant_aliases=participant_aliases,
                )
            ]
            question = complete[-1] if complete else ""
            question = re.sub(r"[`{}\[\]]", "", question).strip()
            if len(question) > 360:
                suffix = "?" if question.rstrip().endswith("?") else "."
                question = question[:360].rsplit(" ", 1)[0].rstrip(" ,;:?.") + suffix
            if not question:
                continue
            target_id = resolve_direct_question_target(
                question,
                public_intent=public_intent,
                participant_aliases=participant_aliases,
            )
            questions.append({
                "speaker_id": speaker_id,
                "question": question,
                "target_id": target_id,
                "target_display_name": str(
                    (participant_labels or {}).get(target_id) or target_id
                ),
            })
    return questions[-4:]


_EXPLICIT_NEW_EXAMPLE_RE = re.compile(
    r"\b(?:another|different|separate|new|other)\s+"
    r"(?:example|case|project|incident|initiative|experience|situation)\b|"
    r"\b(?:else|instead)\b",
    flags=re.IGNORECASE,
)


def retrospective_continuity_anchor(
    messages: list[dict[str, Any]],
    *,
    pending_questions: list[dict[str, str]],
    evidence_mode: str,
) -> str:
    """Expose the exact prior example for ambiguous interview follow-ups.

    A prose instruction to preserve continuity was not sufficient with every
    model: some follow-up answers silently changed projects and metrics.  The
    anchor is public dialogue, not hidden state, so both comparison conditions
    receive the same deterministic context.
    """
    if evidence_mode != "retrospective_claim":
        return ""
    latest_question = str((pending_questions[-1] if pending_questions else {}).get(
        "question"
    ) or "")
    if _EXPLICIT_NEW_EXAMPLE_RE.search(latest_question):
        return ""
    for message in reversed(messages):
        if message.get("speaker_type") != "user" and message.get("speaker_id") != "user":
            continue
        content = " ".join(str(message.get("content") or "").split()).strip()
        if content:
            return content[-1600:]
    return ""


def safe_comparison_player_fallback(
    *,
    evidence_mode: str,
    pending_questions: list[dict[str, str]],
    turn_id: int,
    prior_utterances: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Keep the shared comparison player moving after unusable model output.

    A retrospective interview needs a grounded answer rather than another
    generic request to clarify the same question. Live tasks receive a targeted
    evidence request. Rotating variants prevent exact-message fallback loops.
    """
    if evidence_mode == "retrospective_claim":
        question = " ".join(
            str((pending_questions[-1] if pending_questions else {}).get("question") or "")
            .split()
        ).casefold()
        if any(token in question for token in ("voices", "heard", "inclusive", "team")):
            variants = (
                "I used written input before the meeting, invited the least-heard functions to speak first, and recorded objections alongside the decision. That changed the rollout plan and made ownership clearer across the team.",
                "I created a structured review in which each function supplied one risk and one proposed adjustment. The final plan incorporated concerns that had not surfaced in the larger meeting and assigned follow-up owners explicitly.",
            )
        elif any(token in question for token in ("conflict", "engineering", "disagreement")):
            variants = (
                "In a previous role, engineering and product disagreed about scope and delivery risk. I made the constraints explicit, compared options against a shared success measure, and used a limited test to reach a decision without overruling the technical owner.",
                "I handled a similar disagreement by asking engineering to quantify the risk, asking product to quantify the user impact, and facilitating a phased option that both sides could test before a full commitment.",
            )
        elif any(token in question for token in ("evidence", "learn", "result")):
            variants = (
                "In that project, I compared the baseline, the test result, and the downstream operating impact. The lesson was to define the decision threshold before the test and revisit the choice when the evidence changed.",
                "I used the pre-change baseline, a limited rollout, and feedback from the affected teams. What I learned was to separate an attractive early signal from evidence strong enough to scale the decision.",
            )
        else:
            variants = (
                "In a previous role, I owned a comparable product decision by defining the user problem, comparing options against value, effort, and risk, and testing the preferred approach before rollout. I would judge the outcome against the baseline we agreed in advance.",
                "I led a similar decision by bringing product, engineering, and customer evidence into one trade-off review, choosing a limited rollout, and measuring the result before expanding the commitment.",
            )
        intent = {
            "kind": "fact",
            "subject": "prior cross-functional experience",
            "transition": "proposed",
            "simulation_scope": "retrospective",
        }
        return _nonduplicate_player_fallback(
            variants, intent=intent, turn_id=turn_id,
            prior_utterances=prior_utterances or [],
        )

    directed_target = str(
        (pending_questions[-1] if pending_questions else {}).get("target_id") or ""
    )
    if directed_target and directed_target != "user":
        target_label = str(
            pending_questions[-1].get("target_display_name") or directed_target
        )
        variants = (
            f"{target_label}, could you answer that question directly before we move on?",
            f"Let's keep ownership clear. {target_label}, could you respond with the evidence within your responsibility?",
            f"I won't answer on another role's behalf. {target_label}, could you address the question and identify any remaining uncertainty?",
        )
        return _nonduplicate_player_fallback(
            variants,
            intent={
                "kind": "handoff",
                "subject": "directed question ownership",
                "transition": "proposed",
                "target_id": directed_target,
                "simulation_scope": "discussion",
            },
            turn_id=turn_id,
            prior_utterances=prior_utterances or [],
        )

    target = "the participant closest to the issue"
    question = ""
    if pending_questions:
        target = pending_questions[-1].get("speaker_id") or target
        question = " ".join(
            str(pending_questions[-1].get("question") or "").split()
        ).strip()
    target_label = (
        target.replace("_", " ").title()
        if target != "the participant closest to the issue"
        else target
    )
    question_topic = question.rstrip(" ?")
    if len(question_topic) > 180:
        question_topic = question_topic[-180:].lstrip()
    if question_topic.casefold().startswith((
        "what can ", "what should ", "can we ", "could we ", "how should ",
    )):
        question_topic = "the decision we can support from the current evidence"
    asks_for_artifact = any(
        token in question.casefold()
        for token in ("upload", "attach", "file", "document", "report", "link", "checksum")
    )
    if asks_for_artifact:
        variants = (
            f"{target_label}, please summarize the relevant evidence here. We'll record the file itself as a follow-up rather than hold the meeting open for an upload.",
            f"Let's make the decision from evidence we can state now and assign the document as a post-meeting deliverable. {target_label}, what can you verify here?",
            f"We should not treat an external file as if it appeared in this meeting. {target_label}, please give us the substantive findings and the follow-up owner.",
        )
        subject = "external evidence follow-up"
    elif question_topic:
        variants = (
            f"On your question—{question_topic}—I cannot confirm more from what we have heard. {target_label}, what can you verify from your area?",
            f"Let's answer that directly: {question_topic}. {target_label}, what evidence can you add so we can decide?",
            f"For {question_topic}, I suggest we separate what we know from what still needs checking. {target_label}, what can you confirm now?",
        )
        subject = question_topic
    else:
        variants = (
            "We have enough to choose a bounded next step. I suggest we record the remaining uncertainty, name an owner, and close on that basis.",
            "I don't think another repetition will resolve this. Let's make the decision we can support now and assign the remaining check to a named owner.",
            "Let's agree on what we can decide today, then record the unresolved point and who will follow it up.",
        )
        subject = "conditional resolution of the current issue"
    intent = {
        "kind": "handoff" if asks_for_artifact else "issue",
        "subject": subject,
        "transition": "proposed",
        "target_id": target,
        "simulation_scope": "discussion",
    }
    return _nonduplicate_player_fallback(
        variants, intent=intent, turn_id=turn_id,
        prior_utterances=prior_utterances or [],
    )


def _nonduplicate_player_fallback(
    variants: tuple[str, ...],
    *,
    intent: dict[str, Any],
    turn_id: int,
    prior_utterances: list[str],
) -> tuple[str, dict[str, Any]]:
    """Apply the normal repetition guard to deterministic recovery speech."""
    start = (max(turn_id, 1) - 1) % len(variants)
    for offset in range(len(variants)):
        candidate = variants[(start + offset) % len(variants)]
        if not near_duplicate_public_utterance(candidate, prior_utterances):
            return candidate, intent

    # Repeating a recovery sentence is worse than ending a stalled autonomous
    # exchange.  This final line is published once and asks the test runner to
    # stop, preserving the unresolved state instead of fabricating progress.
    return (
        "We are not adding new evidence, so I will close here and leave the "
        "unresolved condition recorded for follow-up.",
        {
            "kind": "outcome",
            "subject": "bounded close without new evidence",
            "transition": "blocked",
            "simulation_scope": "discussion",
            "_requested_end": True,
        },
    )


async def generate_player_move(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
) -> PlayerMove:
    config = dict(session.run_config or {})
    player = resolve_player_character(scenario)
    evidence_mode = str((scenario.task_config or {}).get("evidence_mode") or (
        "retrospective_claim"
        if str((scenario.task_config or {}).get("task_type") or "") == "structured_interview"
        else "live_operation"
    ))
    llm_cfg = await orch_support.get_llm_config(db)
    player_llm = resolve_llm(llm_cfg, scenario.orchestration_config, "player")
    strategy = str(config.get("player_strategy") or "balanced")
    turn_id = sum(1 for message in messages if message.get("speaker_type") == "user") + 1
    player_store = AgentMemoryStore(session.id, "user")
    player_nodes = await player_store.load_all(db)
    player_plan = active_plan(player_nodes)
    if player_plan is None:
        player_plan = await player_store.append(
            db,
            node_type="plan",
            content=(
                f"Pursue the public player goal using a {strategy} strategy: "
                f"{resolve_player_side_goal(scenario)}"
            ),
            importance=8.0,
            turn_id=0,
            tick=0,
            is_active=True,
            meta={"visibility": "private", "source": "ai_player"},
        )
        player_nodes.append(player_plan)

    if turn_id > 1 and messages:
        public_observation = " | ".join(
            f"{m.get('speaker_id', 'unknown')}: {m.get('content', '')}"
            for m in messages[-6:]
        )
        await player_store.append(
            db,
            node_type="observation",
            content=f"Public dialogue reviewed before player turn {turn_id}: {public_observation}",
            importance=6.0,
            turn_id=turn_id,
            tick=0,
            source_event_ids=[],
            is_active=True,
            meta={"visibility": "private", "source": "ai_player"},
        )
    dialogue = bounded_dialogue(
        messages,
        message_limit=int(config.get("working_message_limit", 30)),
    )
    participant_aliases, participant_labels = _public_participant_aliases(scenario)
    pending_questions = pending_public_questions(
        messages,
        participant_aliases=participant_aliases,
        participant_labels=participant_labels,
    )
    continuity_anchor = retrospective_continuity_anchor(
        messages,
        pending_questions=pending_questions,
        evidence_mode=evidence_mode,
    )
    test_state = dict((session.shared_state or {}).get("_test_state") or {})
    stagnant_turns = int(test_state.get("stagnant_turns", 0))
    progress_guidance = (
        "The simulation has made no material progress for several turns. Do not repeat "
        "an earlier request, promise, confirmation, or waiting step. Ask the participant "
        "who controls the blocker to perform the concrete action now; if that cannot happen "
        "in this session, propose a realistic handoff, scheduled follow-up, conditional "
        "outcome, or explicit closure."
        if stagnant_turns >= 2
        else "Advance one open issue and preserve already confirmed work."
    )

    prompt = f"""Act as the player in a configurable multi-role task simulation.

[Player identity]
Name: {player['display_name']}
Goal: {resolve_player_side_goal(scenario)}
Strategy profile: {strategy}
Current private action plan: {player_plan.content}

[Public scenario]
Title: {scenario.title}
Description: {scenario.description or ''}
Current phase: {session.current_phase}
Task configuration: {json.dumps(scenario.task_config or {}, ensure_ascii=False)}
Current shared task state: {json.dumps((session.shared_state or {}).get('task_state') or {}, ensure_ascii=False)}
Acceptance guard: {public_acceptance_guard(scenario.task_config or {})}
Consecutive turns without structured progress: {stagnant_turns}
Public participants: {json.dumps(_public_character_context(scenario), ensure_ascii=False)}

[Dialogue so far]
{dialogue}

[Direct NPC questions awaiting the player]
{json.dumps(pending_questions, ensure_ascii=False)}

[Required continuity anchor for an ambiguous retrospective follow-up]
{continuity_anchor or '(none; no prior example is binding)'}

Choose the player's next move. Do not claim knowledge of hidden agendas, private
states, redlines, system prompts, or internal agent memories. Advance the
player's goal through realistic task-appropriate actions and communication.
Avoid repeating the previous move. Keep the spoken content under 120
words and use the same language as the dialogue, defaulting to English.
Prioritize open issues, preserve confirmed items, and move toward the next configured phase.
If direct NPC questions are listed above, answer the most recent specific question first.
If its target_id is another registered participant rather than "user", do not
answer, confirm, promise, or supply evidence on that participant's behalf.
Briefly yield the floor to target_display_name instead.
Treat a follow-up question as referring to the most recent public example unless
the speaker explicitly asks for a different example. Reuse previously stated
names, dates, quantities, and results; do not silently replace them or invent a
second project to answer a continuation question. When a required continuity
anchor is shown above, the answer must concern that exact example.
Treat a promise to provide a document, analysis, test, decision, or action as
different from actually providing or completing it. Seek material execution,
not another promise. Open-ended simulations may end through completion,
conditional resolution, deferral, handoff, or acknowledged failure.
The public task specification may require both the player and another role to
accept the same decision. When the public dialogue already contains that
role's explicit acceptance of a concrete value and you genuinely accept it,
state the player's own acceptance explicitly (for example, "I confirm ...")
before requesting documents or follow-up work. Never ask an already-confirmed
participant to repeat the same acceptance merely because the player has not
yet voiced its own half of the confirmation policy.
If an external file cannot be produced inside this text meeting, do not keep
requesting it. Ask for its substantive findings inline, assign the file as a
post-meeting deliverable, and proceed to a conditional decision or deferral.
A question asking whether something happened is not evidence that it happened.
Never turn a request for confirmation into an affirmative status or metric.
Evidence mode: {evidence_mode}. In retrospective_claim mode, describe past
experience as kind=fact, simulation_scope=retrospective, transition=proposed;
do not turn a historical narrative into a live completed simulation action.
Progress rule: {progress_guidance}

Return strict JSON only:
{{
  "content": "the exact next spoken message",
  "intent": "short strategy label",
  "public_intent": {{
    "kind": "statement|fact|proposal|decision|commitment|action|artifact|verification|schedule|issue|outcome|handoff",
    "subject": "one concise public subject",
    "transition": "proposed|committed|in_progress|submitted|verified|accepted|rejected|blocked",
    "target_id": "required character_id for a question/request; otherwise optional",
    "field": "optional configured state field",
    "value": "explicit public typed field value, otherwise null",
    "simulation_scope": "discussion|in_session|external|retrospective",
    "inline_content": "actual in-session result/content, otherwise empty",
    "evidence_source": "public_statement|simulated_tool_result|external_followup",
    "tool_result_id": "required only for a real simulation-supplied tool result, otherwise empty"
  }},
  "requested_end": false
}}"""

    raw = ""
    parsed: dict[str, Any] = {}
    content = ""
    rejection = ""
    for attempt in range(2):
        retry_rule = (
            f"\nYour previous response was rejected ({rejection}). Return one complete JSON "
            "object with a complete, punctuated content string and no extra text.\n"
            if attempt
            else ""
        )
        try:
            raw = await llm_client.chat_completion(
                [{"role": "user", "content": prompt + retry_rule}],
                db_provider=player_llm.provider,
                db_model=player_llm.model,
                temperature=float(config.get("player_temperature", player_llm.temperature)),
                max_tokens=min(
                    max(int(config.get("player_max_tokens", player_llm.max_tokens)), 1024),
                    1536,
                ),
                response_format={"type": "json_object"},
            )
        except LLMEmptyContentError:
            # An autonomous run must not lose all prior turns because one
            # reasoning-model response exhausted its visible output budget.
            rejection = "empty_model_response"
            emit(
                "llm.degraded_fallback",
                component="autonomous_player",
                fallback_action="retry_then_safe_message",
            )
            continue
        parsed = orch_support.parse_json(raw)
        content = normalize_player_content(parsed.get("content") or "")
        validated_intent = validate_public_intent(
            character={**player, "character_id": "user"},
            intent=parsed.get("public_intent"),
            turn_id=turn_id,
            allow_retrospective=evidence_mode == "retrospective_claim",
        )
        rejection = player_speech_rejection_reason(
            content, public_context=dialogue, validated_intent=validated_intent,
            participant_aliases=participant_aliases,
        ) or ""
        latest_target = str(
            (pending_questions[-1] if pending_questions else {}).get("target_id") or ""
        )
        if not rejection and latest_target and latest_target != "user":
            rejection = npc_directed_question_handoff_reason(
                content,
                target_id=latest_target,
                public_intent=validated_intent,
                participant_aliases=participant_aliases,
            ) or ""
        if not rejection and near_duplicate_public_utterance(
            content, recent_player_utterances(messages)
        ):
            rejection = "near_duplicate_same_speaker"
        if rejection and content:
            repaired = retain_safe_public_clauses(
                content, validated_intent=validated_intent
            )
            repaired_rejection = player_speech_rejection_reason(
                repaired, public_context=dialogue, validated_intent=validated_intent,
                participant_aliases=participant_aliases,
            ) if repaired else rejection
            if repaired and not repaired_rejection and near_duplicate_public_utterance(
                repaired, recent_player_utterances(messages)
            ):
                repaired_rejection = "near_duplicate_same_speaker"
            if repaired and not repaired_rejection:
                emit(
                    "dialogue.public_clause_repair.used",
                    component="player_agent",
                    rejection_reason=rejection,
                )
                content = repaired
                rejection = ""
        if rejection:
            emit(
                "llm.public_output.rejected",
                component="autonomous_player",
                rejection_reason=rejection,
                retrying=attempt == 0,
            )
        if not rejection and isinstance(parsed.get("requested_end", False), bool):
            break
        if not rejection:
            rejection = "invalid_requested_end"
    else:
        content = (
            "I'd like to begin with the first task-relevant question. I will respond "
            "with concrete evidence and work toward the stated objective."
        )
        parsed = {"intent": "safe_task_opening", "requested_end": False, "public_intent": {}}

    intent = str(parsed.get("intent") or "unspecified")
    requested_end = bool(parsed.get("requested_end", False))
    public_intent = validate_public_intent(
        character={**player, "character_id": "user"},
        intent=parsed.get("public_intent"),
        turn_id=turn_id,
        allow_retrospective=evidence_mode == "retrospective_claim",
    )
    emit(
        "public_ledger.intent.validated",
        actor_id="user", turn_id=turn_id, kind=public_intent.get("kind"),
        requested_transition=public_intent.get("requested_transition"),
        applied_transition=public_intent.get("transition"),
        validation=public_intent.get("validation"),
        validation_reason=public_intent.get("validation_reason"),
    )
    await player_store.append(
        db,
        node_type="action",
        content=f'Spoke: "{content}"',
        importance=6.5,
        turn_id=turn_id,
        tick=0,
        source_event_ids=[],
        is_active=False,
        meta={
            "action_kind": "speak",
            "intent": intent,
            "requested_end": requested_end,
            "generation_model": player_llm.label(),
            "visibility": "public_action",
        },
    )
    return PlayerMove(
        content=content,
        intent=intent,
        requested_end=requested_end,
        model_label=player_llm.label(),
        raw=raw,
        public_intent=public_intent,
    )


async def generate_comparison_player_move(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
) -> PlayerMove:
    """Shared, public-only player policy for controlled batch comparisons.

    Both conditions call this exact function. It deliberately cannot inspect
    RoomMind task state, phases, private memories, plans, or baseline internals.
    """
    config = dict(session.run_config or {})
    player = resolve_player_character(scenario)
    evidence_mode = str((scenario.task_config or {}).get("evidence_mode") or (
        "retrospective_claim"
        if str((scenario.task_config or {}).get("task_type") or "") == "structured_interview"
        else "live_operation"
    ))
    llm_cfg = await orch_support.get_llm_config(db)
    comparison_orch_cfg = dict(scenario.orchestration_config or {})
    comparison_orch_cfg["_comparison_lock_model"] = True
    resolved = resolve_llm(llm_cfg, comparison_orch_cfg, "player")
    dialogue = bounded_dialogue(
        messages,
        message_limit=int(config.get("working_message_limit", 30)),
    )
    participant_aliases, participant_labels = _public_participant_aliases(scenario)
    pending_questions = pending_public_questions(
        messages,
        participant_aliases=participant_aliases,
        participant_labels=participant_labels,
    )
    turn_id = sum(
        1 for message in messages if message.get("speaker_type") == "user"
    ) + 1
    latest_target = str(
        (pending_questions[-1] if pending_questions else {}).get("target_id") or ""
    )
    if latest_target and latest_target != "user":
        # Cross-role floor ownership is an interaction invariant, not a prose
        # preference.  Do not spend an LLM attempt hoping it will obey the
        # handoff instruction: publish the same minimal public-only handoff in
        # both controlled-comparison conditions.
        target_label = str(
            pending_questions[-1].get("target_display_name") or latest_target
        )
        content = (
            f"{target_label}, please answer the question directly from your area "
            "before we continue."
        )
        public_intent = validate_public_intent(
            character={**player, "character_id": "user"},
            intent={
                "kind": "handoff",
                "subject": "directed question ownership",
                "transition": "proposed",
                "target_id": latest_target,
                "simulation_scope": "discussion",
                "evidence_source": "public_statement",
            },
            turn_id=turn_id,
            allow_retrospective=evidence_mode == "retrospective_claim",
        )
        emit(
            "dialogue.cross_role_handoff.enforced",
            component="comparison_player",
            turn_id=turn_id,
            target_id=latest_target,
        )
        return PlayerMove(
            content=content,
            intent="enforced_cross_role_handoff",
            requested_end=False,
            model_label=resolved.label(),
            raw="",
            public_intent=public_intent,
        )
    continuity_anchor = retrospective_continuity_anchor(
        messages,
        pending_questions=pending_questions,
        evidence_mode=evidence_mode,
    )
    prompt = f"""Act as the external player in a controlled comparison of two
multi-role dialogue systems. The player policy must be identical in both
conditions and may use public information only.

Player identity: {player['display_name']}
Player goal: {resolve_player_side_goal(scenario)}
Strategy: {config.get('player_strategy', 'balanced')}

Public scenario title: {scenario.title}
Public scenario description: {scenario.description or ''}
Public task specification: {json.dumps(scenario.task_config or {}, ensure_ascii=False)}
Acceptance guard: {public_acceptance_guard(scenario.task_config or {})}
Evidence mode: {evidence_mode}
Public participants: {json.dumps(_public_character_context(scenario), ensure_ascii=False)}

Public dialogue:
{dialogue}

Direct NPC questions awaiting the player:
{json.dumps(pending_questions, ensure_ascii=False)}

Required continuity anchor for an ambiguous retrospective follow-up:
{continuity_anchor or '(none; no prior example is binding)'}

Choose one realistic next player message. Do not infer or mention hidden state,
private memories, agent architecture, internal phase, or system completion.
Advance an unresolved issue, preserve explicit agreements, avoid repetition,
and keep the message under 120 words. If direct NPC questions are listed,
answer the most recent specific question before introducing a new issue. If
the latest question's target_id is another registered participant rather than
"user", do not answer, confirm, promise, or supply evidence on that
participant's behalf. Briefly yield the floor to target_display_name instead. Use
the dialogue language, default English. Do not invent links, attachments,
measurements, approvals, live-system results, or facts controlled by another
participant. Ask the appropriate participant for missing evidence instead. If
the latest question follows up on a previously described example, continue that
same example and preserve its dates, quantities, participants, and results.
Introduce a new example only when the speaker explicitly requests one. When a
required continuity anchor is shown above, the answer must concern that exact
example. If an external file cannot be produced inside this text meeting, request its
substantive findings once, assign the file as a post-meeting deliverable, and
continue to a conditional decision or explicit deferral rather than looping.
A question asking whether something happened is not evidence that it happened;
do not convert questions or requests into affirmative findings.
The public task specification may require both the player and another role to
accept the same decision. When the public dialogue already contains that
role's explicit acceptance of a concrete value and you genuinely accept it,
state the player's own acceptance explicitly (for example, "I confirm ...")
before requesting documents or follow-up work. Do not ask an already-confirmed
participant to repeat the same acceptance merely because the player has not
yet voiced its own half of the confirmation policy. This rule uses only the
public transcript and applies identically in both comparison conditions.
In retrospective_claim mode, recount past experience as kind=fact,
simulation_scope=retrospective, transition=proposed. It is not a live action
completed by this text simulation.

Return strict JSON only:
{{"content":"exact spoken message","intent":"short label","requested_end":false,
"public_intent":{{"kind":"statement|fact|proposal|decision|commitment|action|artifact|verification|schedule|issue|outcome|handoff","subject":"one concise public subject","transition":"proposed|committed|in_progress|submitted|verified|accepted|rejected|blocked","target_id":"required character_id for a question/request; otherwise optional","field":"optional configured state field","value":"explicit public typed field value, otherwise null","simulation_scope":"discussion|in_session|external|retrospective","inline_content":"actual in-session result/content, otherwise empty","evidence_source":"public_statement|simulated_tool_result|external_followup","tool_result_id":"required only for a real simulation-supplied tool result, otherwise empty"}}}}"""
    raw = ""
    parsed: dict[str, Any] = {}
    content = ""
    rejection = ""
    for attempt in range(2):
        repair = (
            f"\nPrevious output was rejected ({rejection}). Return exactly one complete JSON object."
            if attempt else ""
        )
        try:
            raw = await llm_client.chat_completion(
                [{"role": "user", "content": prompt + repair}],
                db_provider=resolved.provider,
                db_model=resolved.model,
                temperature=float(config.get("player_temperature", 0.2)),
                max_tokens=min(
                    max(int(config.get("player_max_tokens", 1024)), 1024),
                    1536,
                ),
                response_format={"type": "json_object"},
            )
        except LLMEmptyContentError:
            rejection = "empty_model_response"
            emit(
                "llm.degraded_fallback",
                component="comparison_player",
                fallback_action="retry_then_clarification",
            )
            continue
        parsed = orch_support.parse_json(raw)
        content = normalize_player_content(parsed.get("content") or "").strip()
        validated_intent = validate_public_intent(
            character={**player, "character_id": "user"},
            intent=parsed.get("public_intent"),
            turn_id=turn_id,
            allow_retrospective=evidence_mode == "retrospective_claim",
        )
        rejection = player_speech_rejection_reason(
            content, public_context=dialogue, validated_intent=validated_intent,
            participant_aliases=participant_aliases,
        ) or ""
        latest_target = str(
            (pending_questions[-1] if pending_questions else {}).get("target_id") or ""
        )
        if not rejection and latest_target and latest_target != "user":
            rejection = npc_directed_question_handoff_reason(
                content,
                target_id=latest_target,
                public_intent=validated_intent,
                participant_aliases=participant_aliases,
            ) or ""
        if not rejection and near_duplicate_public_utterance(
            content, recent_player_utterances(messages)
        ):
            rejection = "near_duplicate_same_speaker"
        if rejection and content:
            repaired = retain_safe_public_clauses(
                content, validated_intent=validated_intent
            )
            repaired_rejection = player_speech_rejection_reason(
                repaired, public_context=dialogue, validated_intent=validated_intent,
                participant_aliases=participant_aliases,
            ) if repaired else rejection
            if repaired and not repaired_rejection and near_duplicate_public_utterance(
                repaired, recent_player_utterances(messages)
            ):
                repaired_rejection = "near_duplicate_same_speaker"
            if repaired and not repaired_rejection:
                emit(
                    "dialogue.public_clause_repair.used",
                    component="comparison_player",
                    rejection_reason=rejection,
                )
                content = repaired
                rejection = ""
        if rejection:
            emit(
                "llm.public_output.rejected",
                component="comparison_player",
                rejection_reason=rejection,
                retrying=attempt == 0,
            )
        if content and not rejection and isinstance(parsed.get("requested_end", False), bool):
            break
        rejection = rejection or "invalid_json_fields"
    if not content or rejection:
        content, fallback_intent = safe_comparison_player_fallback(
            evidence_mode=evidence_mode,
            pending_questions=pending_questions,
            turn_id=turn_id,
            prior_utterances=recent_player_utterances(messages),
        )
        fallback_requested_end = bool(fallback_intent.pop("_requested_end", False))
        parsed = {
            "intent": "safe_task_continuation",
            "requested_end": fallback_requested_end,
            "public_intent": fallback_intent,
        }
        emit(
            "dialogue.safe_fallback.used",
            component="comparison_player",
            rejection_reason=rejection or "invalid_json_fields",
            fallback_kind=(
                "retrospective_answer" if evidence_mode == "retrospective_claim"
                else "contextual_task_continuation"
            ),
        )
    public_intent = validate_public_intent(
        character={**player, "character_id": "user"},
        intent=parsed.get("public_intent"),
        turn_id=turn_id,
        allow_retrospective=evidence_mode == "retrospective_claim",
    )
    emit(
        "public_ledger.intent.validated",
        actor_id="user", turn_id=turn_id, kind=public_intent.get("kind"),
        requested_transition=public_intent.get("requested_transition"),
        applied_transition=public_intent.get("transition"),
        validation=public_intent.get("validation"),
        validation_reason=public_intent.get("validation_reason"),
    )
    return PlayerMove(
        content=content,
        intent=str(parsed.get("intent") or "unspecified"),
        requested_end=bool(parsed.get("requested_end", False)),
        model_label=resolved.label(),
        raw=raw,
        public_intent=public_intent,
    )
