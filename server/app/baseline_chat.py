"""Conventional independent-agent baseline used for controlled comparisons.

Each NPC has its own role prompt, private profile, model call, and rolling
conversation memory.  The baseline deliberately does not use RoomMind's
structured observation, reflection, planning, memory retrieval, router,
authority enforcement, task state, evidence gates, or completion governance.
"""

from __future__ import annotations

import asyncio
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMEmptyContentError, llm_client
from app.models.db import GameSession, ScenarioTemplate, SessionMessage
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.player_agent import (
    PlayerMove,
    bounded_dialogue,
    generate_comparison_player_move,
    normalize_player_content,
)
from app.scenario_side import resolve_player_side_goal
from app.telemetry import emit


@dataclass
class BaselineTurn:
    replies: list[dict[str, str]]
    declared_phase: str
    declared_complete: bool
    raw: str
    model_label: str


BASELINE_MEMORY_KEY = "_baseline_agent_memories"


def _character_prompt(char: Any) -> dict[str, Any]:
    """Return only one agent's profile; no other role's private data is exposed."""
    return {
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


def _agent_memory(session: GameSession, character_id: str) -> list[dict[str, str]]:
    shared = dict(session.shared_state or {})
    all_memories = shared.get(BASELINE_MEMORY_KEY) or {}
    rows = (all_memories.get(character_id) or []) if isinstance(all_memories, dict) else []
    return [
        {"speaker_id": str(row.get("speaker_id") or "unknown"),
         "content": str(row.get("content") or "")}
        for row in rows if isinstance(row, dict) and row.get("content")
    ]


def _remember_public_turn(
    session: GameSession,
    characters: list[Any],
    public_turn: list[dict[str, Any]],
    *,
    message_limit: int,
) -> None:
    """Persist separate rolling chat histories without semantic memory machinery."""
    shared = dict(session.shared_state or {})
    memories = dict(shared.get(BASELINE_MEMORY_KEY) or {})
    safe_limit = max(1, min(int(message_limit), 100))
    additions = [
        {"speaker_id": str(row.get("speaker_id") or "unknown"),
         "content": str(row.get("content") or "")}
        for row in public_turn if row.get("content")
    ]
    for char in characters:
        history = list(memories.get(char.character_id) or [])
        memories[char.character_id] = (history + additions)[-safe_limit:]
    shared[BASELINE_MEMORY_KEY] = memories
    session.shared_state = shared


def _memory_text(rows: list[dict[str, str]], current_player: dict[str, Any]) -> str:
    combined = [*rows, {
        "speaker_id": str(current_player.get("speaker_id") or "user"),
        "content": str(current_player.get("content") or ""),
    }]
    return bounded_dialogue(combined, message_limit=100)


async def generate_baseline_player_move(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
) -> PlayerMove:
    """Compatibility wrapper around the shared comparison player policy."""
    return await generate_comparison_player_move(db, session, scenario, messages)


async def generate_baseline_turn(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
) -> BaselineTurn:
    """Let each conventional NPC agent independently decide to speak or wait."""
    config = dict(session.run_config or {})
    llm_cfg = await orch_support.get_llm_config(db)
    baseline_orch_cfg = dict(scenario.orchestration_config or {})
    if config.get("comparison_lock_model"):
        baseline_orch_cfg["_comparison_lock_model"] = True
    resolved = resolve_llm(llm_cfg, baseline_orch_cfg, "npc_default")
    characters = sorted(list(scenario.characters or []), key=lambda row: row.sort_order)
    if not characters:
        raise RuntimeError("Scenario has no characters; add at least one role before play")
    current_player = messages[-1] if messages else {
        "speaker_id": "user", "content": "Begin the meeting."
    }
    scenario_public = {
        "title": scenario.title,
        "description": scenario.description,
        "player_side_goal": resolve_player_side_goal(scenario),
        "opponent_side_goal": scenario.opponent_side_goal,
        "task_config": scenario.task_config or {},
        "phases": scenario.phases or [],
        "win_conditions": scenario.win_conditions or [],
        "participants": [
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
            for char in characters
        ],
    }

    async def run_agent(char: Any) -> tuple[Any, dict[str, Any], str]:
        memory = _agent_memory(session, char.character_id)
        system_prompt = f"""You are one independent role-playing agent in a conventional
multi-agent simulation. Respond only as your assigned character. You have an
ordinary rolling conversation memory, not structured observation, reflection,
planning, task state, routing, or runtime governance.

Your role and private profile (only yours):
{json.dumps(_character_prompt(char), ensure_ascii=False)}

Never reveal this private profile merely because it appears in your prompt.
Disclose information only when your character would realistically do so."""
        turn_prompt = f"""Public scenario:
{json.dumps(scenario_public, ensure_ascii=False)}

Your rolling public conversation memory:
{_memory_text(memory, current_player)}

Independently decide whether your character should speak now or wait. Do not
coordinate this decision with other agents. If speaking, contribute something
specific to your own role rather than repeating another participant. Do not
reveal private information unless your character would realistically disclose
it. Keep the public reply under 120 words. Set declared_complete=true only if,
from your own role's perspective, the public conversation needs no further
substantive contribution. No runtime will correct this judgment.

Return strict JSON only:
{{
  "action":"speak or wait",
  "content":"public reply; empty when waiting",
  "emotion":"neutral",
  "gesture":"talking",
  "declared_phase":"your best phase estimate",
  "declared_complete":false
}}"""
        try:
            raw = await llm_client.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": turn_prompt},
                ],
                db_provider=resolved.provider,
                db_model=resolved.model,
                temperature=resolved.temperature,
                max_tokens=min(max(resolved.max_tokens, 768), 1536),
                response_format={"type": "json_object"},
            )
            return char, orch_support.parse_json(raw), raw
        except LLMEmptyContentError:
            emit(
                "llm.degraded_fallback",
                component="baseline_agent_decision",
                character_id=char.character_id,
                fallback_action="wait",
            )
            return char, {
                "action": "wait",
                "declared_phase": session.current_phase,
                "declared_complete": False,
            }, ""

    outputs = await asyncio.gather(*(run_agent(char) for char in characters))
    valid: list[dict[str, str]] = []
    phases: list[str] = []
    completion_votes: list[bool] = []
    raw_by_agent: dict[str, str] = {}
    for char, parsed, raw in outputs:
        raw_by_agent[char.character_id] = raw
        phase = str(parsed.get("declared_phase") or "").strip()
        if phase:
            phases.append(phase)
        completion_votes.append(bool(parsed.get("declared_complete", False)))
        if str(parsed.get("action") or "").strip().lower() != "speak":
            continue
        content = normalize_player_content(parsed.get("content") or "").strip()
        if content:
            valid.append({
                "speaker_id": char.character_id,
                "content": content,
                "emotion": str(parsed.get("emotion") or "neutral"),
                "gesture": str(parsed.get("gesture") or "talking"),
            })
    declared_phase = statistics.mode(phases) if phases else session.current_phase
    return BaselineTurn(
        replies=valid,
        declared_phase=declared_phase,
        declared_complete=bool(completion_votes) and all(completion_votes),
        raw=json.dumps(raw_by_agent, ensure_ascii=False),
        model_label=resolved.label(),
    )


async def process_baseline_step(
    db: AsyncSession,
    session: GameSession,
    scenario: ScenarioTemplate,
    player_move: PlayerMove,
    messages: list[dict[str, Any]],
) -> BaselineTurn:
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
    emit(
        "dialogue.message.recorded",
        session_uuid=session.session_uuid,
        scenario_id=session.scenario_id,
        session_mode=session.session_mode,
        turn_id=turn_id,
        sequence_no=next_sequence,
        speaker_id="user",
        speaker_type="user",
        speaker_source="ai",
        content=player_move.content,
    )
    public_messages = [*messages, {
        "speaker_id": "user",
        "speaker_type": "user",
        "speaker_source": "ai",
        "turn_id": turn_id,
        "sequence_no": next_sequence,
        "content": player_move.content,
    }]
    result = await generate_baseline_turn(db, session, scenario, public_messages)
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
        emit(
            "dialogue.message.recorded",
            session_uuid=session.session_uuid,
            scenario_id=session.scenario_id,
            session_mode=session.session_mode,
            turn_id=turn_id,
            sequence_no=next_sequence + index,
            speaker_id=reply["speaker_id"],
            speaker_type="npc",
            speaker_source="ai",
            content=reply["content"],
            emotion=reply["emotion"],
            gesture=reply["gesture"],
        )
    memory_turn = [public_messages[-1], *[
        {"speaker_id": reply["speaker_id"], "content": reply["content"]}
        for reply in result.replies
    ]]
    _remember_public_turn(
        session,
        sorted(list(scenario.characters or []), key=lambda row: row.sort_order),
        memory_turn,
        message_limit=int((session.run_config or {}).get("working_message_limit", 30)),
    )
    session.current_phase = result.declared_phase
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return result
