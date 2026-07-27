"""AI player for autonomous test sessions.

The player is intentionally built from public scenario information only. NPC
private_state and system prompts must never be included in this context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory_stream import AgentMemoryStore, active_plan
from app.agent.speech_safety import player_speech_rejection_reason
from app.llm.client import llm_client
from app.models.db import GameSession, ScenarioTemplate
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.player_character import resolve_player_character
from app.scenario_side import resolve_player_side_goal


@dataclass
class PlayerMove:
    content: str
    intent: str
    requested_end: bool
    model_label: str
    raw: str


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


async def generate_player_move(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
) -> PlayerMove:
    config = dict(session.run_config or {})
    player = resolve_player_character(scenario)
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
    test_state = dict((session.shared_state or {}).get("_test_state") or {})
    stagnant_turns = int(test_state.get("stagnant_turns", 0))
    progress_guidance = (
        "The structured task state has not changed for several turns. Do not repeat "
        "prior confirmations or merely wait again. Ask for a concrete authorized action, "
        "request the missing evidence, propose a bounded alternative, or explicitly explain "
        "why progress is impossible."
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
Consecutive turns without structured progress: {stagnant_turns}
Public participants: {json.dumps(_public_character_context(scenario), ensure_ascii=False)}

[Dialogue so far]
{dialogue}

Choose the player's next move. Do not claim knowledge of hidden agendas, private
states, redlines, system prompts, or internal agent memories. Advance the
player's goal through realistic task-appropriate actions and communication.
Avoid repeating the previous move. Keep the spoken content under 120
words and use the same language as the dialogue, defaulting to English.
Prioritize open issues, preserve confirmed items, and move toward the next configured phase.
Progress rule: {progress_guidance}

Return strict JSON only:
{{
  "content": "the exact next spoken message",
  "intent": "short strategy label",
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
        raw = await llm_client.chat_completion(
            [{"role": "user", "content": prompt + retry_rule}],
            db_provider=player_llm.provider,
            db_model=player_llm.model,
            temperature=float(config.get("player_temperature", player_llm.temperature)),
            max_tokens=min(int(config.get("player_max_tokens", player_llm.max_tokens)), 768),
            response_format={"type": "json_object"},
        )
        parsed = orch_support.parse_json(raw)
        content = normalize_player_content(parsed.get("content") or "")
        rejection = player_speech_rejection_reason(content) or ""
        if not rejection and isinstance(parsed.get("requested_end", False), bool):
            break
        if not rejection:
            rejection = "invalid_requested_end"
    else:
        content = (
            "I'd like to begin with the first task-relevant question. I will respond "
            "with concrete evidence and work toward the stated objective."
        )
        parsed = {"intent": "safe_task_opening", "requested_end": False}

    intent = str(parsed.get("intent") or "unspecified")
    requested_end = bool(parsed.get("requested_end", False))
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
    )
