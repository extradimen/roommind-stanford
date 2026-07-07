"""Export full session payloads for analysis (dialogue, agent memory, decisions)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.debug_payload import build_session_agent_memories_payload, load_agent_memories_grouped, load_character_names
from app.models.db import EpisodeMemory, GameSession, ScenarioTemplate, SessionMessage
from app.orchestrator.defaults import merge_orchestration_config

SESSION_EXPORT_FORMAT = "roommind-session-bundle"
SESSION_EXPORT_VERSION = 1


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def serialize_message(message: SessionMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "speaker_id": message.speaker_id,
        "speaker_type": message.speaker_type,
        "content": message.content,
        "emotion": message.emotion,
        "gesture": message.gesture,
        "meta": message.meta or {},
        "created_at": _iso(message.created_at),
    }


def _timeline_for_turn(world_timeline: list[Any], turn_id: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw in world_timeline:
        if not isinstance(raw, dict):
            continue
        if int(raw.get("turn_id", -1)) == turn_id:
            events.append(raw)
    events.sort(key=lambda e: (int(e.get("tick", 0)), str(e.get("event_id", ""))))
    return events


def _agent_slice_for_turn(
    agent_memories: dict[str, list[dict[str, Any]]],
    turn_id: int,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for cid, nodes in agent_memories.items():
        picked = [n for n in nodes if int(n.get("turn_id", -1)) == turn_id]
        if picked:
            out[cid] = picked
    return out


def _agent_decisions_for_turn(
    agent_memories: dict[str, list[dict[str, Any]]],
    turn_id: int,
) -> dict[str, dict[str, Any]]:
    """Summarize decision-relevant fields per character for one turn."""
    decisions: dict[str, dict[str, Any]] = {}
    for cid, nodes in agent_memories.items():
        actions = [n for n in nodes if n.get("node_type") == "action" and int(n.get("turn_id", -1)) == turn_id]
        observations = [
            n for n in nodes if n.get("node_type") == "observation" and int(n.get("turn_id", -1)) == turn_id
        ]
        reflections = [
            n for n in nodes if n.get("node_type") == "reflection" and int(n.get("turn_id", -1)) == turn_id
        ]
        if not actions and not observations and not reflections:
            continue
        speak_text = ""
        action_kind = ""
        for act in actions:
            meta = act.get("meta") or {}
            if meta.get("display_text"):
                speak_text = str(meta["display_text"])
            action_kind = str(meta.get("action_kind") or action_kind or "action")
        decisions[cid] = {
            "actions": actions,
            "observations": observations,
            "reflections": reflections,
            "action_kind": action_kind or None,
            "spoke_content": speak_text or None,
        }
    return decisions


def build_dialogue_turns(
    messages: list[SessionMessage],
    world_timeline: list[Any],
    agent_memories: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Group chat + world line + agent nodes by user turn."""
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for message in messages:
        if message.speaker_type == "user":
            if current:
                turn_id = int(current["turn_id"])
                current["world_timeline"] = _timeline_for_turn(world_timeline, turn_id)
                current["agent_memories"] = _agent_slice_for_turn(agent_memories, turn_id)
                current["agent_decisions"] = _agent_decisions_for_turn(agent_memories, turn_id)
                turns.append(current)
            current = {
                "turn_id": len(turns) + 1,
                "user_message": serialize_message(message),
                "npc_replies": [],
            }
        elif current is not None and message.speaker_type == "npc":
            current["npc_replies"].append(serialize_message(message))

    if current:
        turn_id = int(current["turn_id"])
        current["world_timeline"] = _timeline_for_turn(world_timeline, turn_id)
        current["agent_memories"] = _agent_slice_for_turn(agent_memories, turn_id)
        current["agent_decisions"] = _agent_decisions_for_turn(agent_memories, turn_id)
        turns.append(current)

    return turns


async def build_session_export_bundle(db: AsyncSession, session: GameSession) -> dict[str, Any]:
    scenario_result = await db.execute(
        select(ScenarioTemplate).where(ScenarioTemplate.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()

    msg_result = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.created_at)
    )
    messages = list(msg_result.scalars().all())

    ep_result = await db.execute(
        select(EpisodeMemory)
        .where(EpisodeMemory.session_id == session.id)
        .order_by(EpisodeMemory.created_at)
    )
    episode_memories = [
        {
            "id": row.id,
            "event_type": row.event_type,
            "summary": row.summary,
            "actors": row.actors or [],
            "impact": row.impact or {},
            "visibility": row.visibility,
            "created_at": _iso(row.created_at),
        }
        for row in ep_result.scalars().all()
    ]

    shared = dict(session.shared_state or {})
    world_timeline = shared.get("world_timeline", [])
    if not isinstance(world_timeline, list):
        world_timeline = []

    reply_language = shared.get("_reply_language", "en")
    if reply_language != "en":
        reply_language = "en"

    character_names = await load_character_names(db, session.scenario_id)
    agent_memories = await load_agent_memories_grouped(
        db, session.id, world_timeline, str(reply_language)
    )
    agent_progress = await build_session_agent_memories_payload(db, session)

    last_debug = shared.get("_last_debug", {})
    if not isinstance(last_debug, dict):
        last_debug = {}

    orch_cfg = merge_orchestration_config(scenario.orchestration_config if scenario else None)
    dialogue_turns = build_dialogue_turns(messages, world_timeline, agent_memories)

    return {
        "export_meta": {
            "format": SESSION_EXPORT_FORMAT,
            "version": SESSION_EXPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session_uuid": session.session_uuid,
            "note": (
                "Full session export for analysis: dialogue, world timeline, agent memory streams, "
                "and per-turn grouping. shared_state._last_debug is only the most recent turn."
            ),
        },
        "session": {
            "session_uuid": session.session_uuid,
            "scenario_id": session.scenario_id,
            "user_id": session.user_id,
            "current_phase": session.current_phase,
            "orchestration_mode": session.orchestration_mode,
            "status": session.status,
            "created_at": _iso(session.created_at),
            "updated_at": _iso(session.updated_at),
        },
        "scenario": {
            "id": scenario.id if scenario else session.scenario_id,
            "slug": scenario.slug if scenario else None,
            "title": scenario.title if scenario else None,
        },
        "character_names": character_names,
        "orchestration_config": orch_cfg,
        "messages": [serialize_message(m) for m in messages],
        "dialogue_turns": dialogue_turns,
        "world_timeline": world_timeline,
        "agent_memories": agent_memories,
        "agent_progress": agent_progress,
        "last_debug": last_debug,
        "episode_memories": episode_memories,
        "shared_state": shared,
    }
