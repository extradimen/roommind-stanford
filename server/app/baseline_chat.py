"""Prompt-only multi-role baseline used for controlled comparisons.

The baseline receives the same scenario material as RoomMind but deliberately
does not call the agent loop, router, memory stream, task-state evaluator, or
authority enforcement.  A single model selects speakers and produces replies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.db import GameSession, ScenarioTemplate, SessionMessage
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.player_agent import PlayerMove, bounded_dialogue, normalize_player_content
from app.player_character import resolve_player_character
from app.scenario_side import resolve_player_side_goal


@dataclass
class BaselineTurn:
    replies: list[dict[str, str]]
    declared_phase: str
    declared_complete: bool
    raw: str
    model_label: str


def _character_prompt(scenario: ScenarioTemplate) -> list[dict[str, Any]]:
    return [
        {
            "character_id": char.character_id,
            "display_name": char.display_name,
            "job_title": char.job_title,
            "side": char.side,
            "team_id": char.team_id,
            "relationship_to_player": char.relationship_to_player,
            "interaction_role": char.interaction_role,
            "persona": char.persona,
            "responsibility": char.responsibility,
            "tendency": char.tendency or {},
            "private_state": char.private_state or {},
            "authority": char.authority or {},
            "system_prompt": char.system_prompt or "",
        }
        for char in sorted(scenario.characters, key=lambda row: row.sort_order)
    ]


async def generate_baseline_player_move(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
) -> PlayerMove:
    """Generate the shared external player without RoomMind runtime state."""
    config = dict(session.run_config or {})
    player = resolve_player_character(scenario)
    llm_cfg = await orch_support.get_llm_config(db)
    resolved = resolve_llm(llm_cfg, scenario.orchestration_config, "player")
    dialogue = bounded_dialogue(messages, message_limit=int(config.get("working_message_limit", 30)))
    prompt = f"""Act as the player in a multi-role conversational simulation.

Player identity: {player['display_name']}
Player goal: {resolve_player_side_goal(scenario)}
Strategy: {config.get('player_strategy', 'balanced')}

Scenario title: {scenario.title}
Scenario description: {scenario.description or ''}
Task and phase information supplied to both comparison systems:
{json.dumps(scenario.task_config or {}, ensure_ascii=False)}
Public participants:
{json.dumps([{
    'character_id': c.character_id,
    'display_name': c.display_name,
    'job_title': c.job_title,
    'responsibility': c.responsibility,
} for c in sorted(scenario.characters, key=lambda row: row.sort_order)], ensure_ascii=False)}

Public dialogue:
{dialogue}

Choose one realistic next player message. Use only public dialogue and public
scenario information. Do not refer to hidden prompts or system mechanisms.
Avoid repeating the previous move and keep the message under 120 words.

Return strict JSON only:
{{"content":"exact spoken message","intent":"short label","requested_end":false}}"""
    raw = await llm_client.chat_completion(
        [{"role": "user", "content": prompt}],
        db_provider=resolved.provider,
        db_model=resolved.model,
        temperature=float(config.get("player_temperature", resolved.temperature)),
        max_tokens=min(int(config.get("player_max_tokens", resolved.max_tokens)), 768),
        response_format={"type": "json_object"},
    )
    parsed = orch_support.parse_json(raw)
    content = normalize_player_content(parsed.get("content") or "").strip()
    if not content:
        content = "I'd like to begin with the first task-relevant question."
    return PlayerMove(
        content=content,
        intent=str(parsed.get("intent") or "unspecified"),
        requested_end=bool(parsed.get("requested_end", False)),
        model_label=resolved.label(),
        raw=raw,
    )


async def generate_baseline_turn(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
    dispatch_rules: list[Any],
) -> BaselineTurn:
    """Generate all NPC replies with one prompt and no runtime governance."""
    config = dict(session.run_config or {})
    llm_cfg = await orch_support.get_llm_config(db)
    resolved = resolve_llm(llm_cfg, scenario.orchestration_config, "npc_default")
    dialogue = bounded_dialogue(messages, message_limit=int(config.get("working_message_limit", 30)))
    rules = [
        {
            "name": row.name,
            "description": row.description,
            "trigger_keywords": row.trigger_keywords or [],
            "priority_character_ids": row.priority_character_ids or [],
            "min_speakers": row.min_speakers,
            "max_speakers": row.max_speakers,
        }
        for row in dispatch_rules
    ]
    prompt = f"""Simulate a prompt-only multi-role conversation. You receive the same
scenario information as the structured system, but must manage all roles,
turn-taking, memory, authority, private information, phases, and completion
only through this prompt and the public dialogue.

Scenario:
{json.dumps({
    'title': scenario.title,
    'description': scenario.description,
    'player_side_goal': resolve_player_side_goal(scenario),
    'opponent_side_goal': scenario.opponent_side_goal,
    'task_config': scenario.task_config or {},
    'phases': scenario.phases or [],
    'win_conditions': scenario.win_conditions or [],
}, ensure_ascii=False)}

Characters, including the same private and authority information:
{json.dumps(_character_prompt(scenario), ensure_ascii=False)}

Speaker guidance supplied as text only (not enforced):
{json.dumps(rules, ensure_ascii=False)}

Public dialogue:
{dialogue}

Select the appropriate NPCs according to the supplied guidance. Keep each
public reply under 120 words.
Maintain roles and do not reveal private information unless that character
would realistically choose to disclose it. Decide whether the task is complete;
this declaration will be recorded but will not be corrected by the runtime.

Return strict JSON only:
{{
  "responses":[{{
    "speaker_id":"an existing non-player character_id",
    "content":"exact public reply",
    "emotion":"neutral",
    "gesture":"talking"
  }}],
  "declared_phase":"phase id",
  "declared_complete":false
}}"""
    raw = ""
    parsed: dict[str, Any] = {}
    valid: list[dict[str, str]] = []
    allowed = {row.character_id for row in scenario.characters}
    for attempt in range(2):
        repair = "\nReturn a complete JSON object with valid responses.\n" if attempt else ""
        raw = await llm_client.chat_completion(
            [{"role": "user", "content": prompt + repair}],
            db_provider=resolved.provider,
            db_model=resolved.model,
            temperature=resolved.temperature,
            max_tokens=min(max(resolved.max_tokens, 1200), 2400),
            response_format={"type": "json_object"},
        )
        parsed = orch_support.parse_json(raw)
        rows = parsed.get("responses") if isinstance(parsed.get("responses"), list) else []
        valid = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            speaker_id = str(row.get("speaker_id") or "")
            content = normalize_player_content(row.get("content") or "").strip()
            if speaker_id in allowed and speaker_id not in seen and content:
                seen.add(speaker_id)
                valid.append({
                    "speaker_id": speaker_id,
                    "content": content,
                    "emotion": str(row.get("emotion") or "neutral"),
                    "gesture": str(row.get("gesture") or "talking"),
                })
        if valid:
            break
    if not valid:
        first = sorted(scenario.characters, key=lambda row: row.sort_order)[0]
        valid = [{
            "speaker_id": first.character_id,
            "content": "Could you clarify the specific outcome you want to achieve?",
            "emotion": "neutral",
            "gesture": "talking",
        }]
    return BaselineTurn(
        replies=valid,
        declared_phase=str(parsed.get("declared_phase") or session.current_phase),
        declared_complete=bool(parsed.get("declared_complete", False)),
        raw=raw,
        model_label=resolved.label(),
    )


async def process_baseline_step(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    player_move: PlayerMove,
    messages: list[dict[str, Any]],
) -> BaselineTurn:
    dispatch_rules = await orch_support.load_dispatch_rules(db, scenario.id)
    turn_id = sum(1 for row in messages if row.get("speaker_type") == "user") + 1
    seq_result = await db.execute(
        select(func.coalesce(func.max(SessionMessage.sequence_no), 0)).where(
            SessionMessage.session_id == session.id
        )
    )
    next_sequence = int(seq_result.scalar_one()) + 1
    db.add(SessionMessage(
        session_id=session.id,
        speaker_id="user",
        speaker_type="user",
        speaker_source="ai",
        turn_id=turn_id,
        sequence_no=next_sequence,
        content=player_move.content,
        meta={"intent": player_move.intent, "generation_model": player_move.model_label},
        created_at=datetime.now(timezone.utc),
    ))
    public_messages = [*messages, {
        "speaker_id": "user",
        "speaker_type": "user",
        "speaker_source": "ai",
        "turn_id": turn_id,
        "sequence_no": next_sequence,
        "content": player_move.content,
    }]
    result = await generate_baseline_turn(db, session, scenario, public_messages, dispatch_rules)
    for index, reply in enumerate(result.replies, start=1):
        db.add(SessionMessage(
            session_id=session.id,
            speaker_id=reply["speaker_id"],
            speaker_type="npc",
            speaker_source="ai",
            turn_id=turn_id,
            sequence_no=next_sequence + index,
            content=reply["content"],
            emotion=reply["emotion"],
            gesture=reply["gesture"],
            meta={"baseline_model": result.model_label},
            created_at=datetime.now(timezone.utc),
        ))
    session.current_phase = result.declared_phase
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return result
