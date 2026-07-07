"""Build agent memory payloads for admin / game debug UIs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.i18n.reply_language import action_speak_summary
from app.models.db import AgentMemoryNode, CharacterTemplate, GameSession, ScenarioTemplate


def serialize_memory_node(row: AgentMemoryNode) -> dict[str, Any]:
    return {
        "id": row.id,
        "node_type": row.node_type,
        "content": row.content,
        "importance": row.importance,
        "turn_id": row.turn_id,
        "tick": row.tick,
        "is_active": row.is_active,
        "source_event_ids": row.source_event_ids or [],
        "meta": row.meta or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _action_nodes_from_timeline(
    world_timeline: list[Any],
    character_id: str,
    reply_language: str = "en",
) -> list[dict[str, Any]]:
    """Backfill action entries from world line for sessions before action memory nodes."""
    actions: list[dict[str, Any]] = []
    for raw in world_timeline:
        if not isinstance(raw, dict):
            continue
        if raw.get("actor_id") != character_id:
            continue
        event_type = raw.get("event_type")
        turn_id = int(raw.get("turn_id", 0))
        tick = int(raw.get("tick", 0))
        meta = dict(raw.get("meta") or {})
        event_id = str(raw.get("event_id", ""))

        if event_type == "npc_speech":
            text = str(raw.get("content", ""))
            actions.append(
                {
                    "id": None,
                    "node_type": "action",
                    "content": action_speak_summary(text, reply_language),
                    "importance": 6.0,
                    "turn_id": turn_id,
                    "tick": tick,
                    "is_active": False,
                    "source_event_ids": [event_id] if event_id else [],
                    "meta": {
                        "action_kind": "speak",
                        "emotion": meta.get("emotion"),
                        "gesture": meta.get("gesture"),
                        "display_text": text,
                        "from_timeline": True,
                    },
                    "created_at": None,
                }
            )
        elif event_type == "agent_action":
            actions.append(
                {
                    "id": None,
                    "node_type": "action",
                    "content": str(raw.get("content", "")),
                    "importance": 5.0,
                    "turn_id": turn_id,
                    "tick": tick,
                    "is_active": False,
                    "source_event_ids": [event_id] if event_id else [],
                    "meta": {
                        "action_kind": meta.get("action_kind", "agent_action"),
                        "from_timeline": True,
                    },
                    "created_at": None,
                }
            )
    return actions


def _merge_action_nodes(
    memory_nodes: list[dict[str, Any]],
    timeline_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing = {
        (n.get("turn_id"), n.get("tick"), n.get("content"))
        for n in memory_nodes
        if n.get("node_type") == "action"
    }
    merged = list(memory_nodes)
    for action in timeline_actions:
        key = (action.get("turn_id"), action.get("tick"), action.get("content"))
        if key in existing:
            continue
        merged.append(action)
        existing.add(key)
    merged.sort(
        key=lambda n: (
            int(n.get("turn_id", 0)),
            int(n.get("tick", 0)),
            str(n.get("node_type", "")),
        )
    )
    return merged


async def load_agent_memories_grouped(
    db: AsyncSession,
    session_id: int,
    world_timeline: list[Any] | None = None,
    reply_language: str = "en",
) -> dict[str, list[dict[str, Any]]]:
    result = await db.execute(
        select(AgentMemoryNode)
        .where(AgentMemoryNode.session_id == session_id)
        .order_by(AgentMemoryNode.character_id, AgentMemoryNode.turn_id, AgentMemoryNode.id)
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.character_id, []).append(serialize_memory_node(row))

    timeline = world_timeline or []
    character_ids = set(grouped.keys())
    for raw in timeline:
        if isinstance(raw, dict) and raw.get("actor_id"):
            character_ids.add(str(raw["actor_id"]))

    for cid in character_ids:
        memory_nodes = grouped.get(cid, [])
        timeline_actions = _action_nodes_from_timeline(timeline, cid, reply_language)
        grouped[cid] = _merge_action_nodes(memory_nodes, timeline_actions)

    return grouped


async def load_character_names(
    db: AsyncSession,
    scenario_id: int,
) -> dict[str, str]:
    result = await db.execute(
        select(CharacterTemplate).where(CharacterTemplate.scenario_id == scenario_id)
    )
    return {c.character_id: c.display_name for c in result.scalars().all()}


async def build_session_agent_memories_payload(
    db: AsyncSession,
    session: GameSession,
) -> dict[str, Any]:
    shared = session.shared_state or {}
    last_debug = shared.get("_last_debug", {}) if isinstance(shared, dict) else {}
    agents_debug = last_debug.get("agents", {}) if isinstance(last_debug, dict) else {}

    character_names = await load_character_names(db, session.scenario_id)

    world_timeline = shared.get("world_timeline", []) if isinstance(shared, dict) else []
    if not isinstance(world_timeline, list):
        world_timeline = []

    reply_language = "en"

    agents = await load_agent_memories_grouped(db, session.id, world_timeline, reply_language)

    return {
        "session_uuid": session.session_uuid,
        "orchestration_mode": session.orchestration_mode,
        "character_names": character_names,
        "agents": agents,
        "world_timeline": world_timeline,
        "last_agent_debug": agents_debug if isinstance(agents_debug, dict) else {},
        "last_turn_id": last_debug.get("turn_id") if isinstance(last_debug, dict) else None,
    }
