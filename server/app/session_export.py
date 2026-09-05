"""Export full session payloads for analysis (dialogue, agent memory, decisions)."""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import io
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.debug_payload import build_session_agent_memories_payload, load_agent_memories_grouped, load_character_names
from app.external_observer import build_external_observation
from app.models.db import CharacterTemplate, EpisodeMemory, GameSession, ScenarioTemplate, SessionMessage
from app.orchestrator.defaults import merge_orchestration_config
from app.player_character import resolve_player_character
from app.task_state import public_task_result

SESSION_EXPORT_FORMAT = "roommind-session-bundle"
SESSION_EXPORT_VERSION = 3


TRANSCRIPT_COLUMNS = [
    "session_uuid", "scenario_id", "scenario_slug", "session_mode",
    "turn_id", "sequence_no", "created_at", "speaker_id", "speaker_type",
    "speaker_source", "character_name", "job_title", "team_id", "relationship_to_player",
    "interaction_role", "content",
    "emotion", "gesture",
]


def transcript_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    session = bundle.get("session") or {}
    scenario = bundle.get("scenario") or {}
    rows: list[dict[str, Any]] = []
    for message in bundle.get("messages") or []:
        speaker = message.get("speaker") or {}
        rows.append({
            "session_uuid": session.get("session_uuid"),
            "scenario_id": scenario.get("id"),
            "scenario_slug": scenario.get("slug"),
            "session_mode": session.get("session_mode"),
            "turn_id": message.get("turn_id"),
            "sequence_no": message.get("sequence_no"),
            "created_at": message.get("created_at"),
            "speaker_id": message.get("speaker_id"),
            "speaker_type": message.get("speaker_type"),
            "speaker_source": message.get("speaker_source"),
            "character_name": speaker.get("character_name"),
            "job_title": speaker.get("job_title"),
            "team_id": speaker.get("team_id"),
            "relationship_to_player": speaker.get("relationship_to_player"),
            "interaction_role": speaker.get("interaction_role"),
            "content": message.get("content"),
            "emotion": message.get("emotion"),
            "gesture": message.get("gesture"),
        })
    return rows


def transcript_csv(bundle: dict[str, Any]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=TRANSCRIPT_COLUMNS)
    writer.writeheader()
    writer.writerows(transcript_rows(bundle))
    return out.getvalue()


def transcript_jsonl(bundle: dict[str, Any]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in transcript_rows(bundle)) + "\n"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def serialize_message(message: SessionMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "speaker_id": message.speaker_id,
        "speaker_type": message.speaker_type,
        "speaker_source": message.speaker_source,
        "turn_id": message.turn_id,
        "sequence_no": message.sequence_no,
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
    """Group chat + world line + agent nodes by persisted turn id."""
    grouped: dict[int, list[SessionMessage]] = {}
    legacy_turn = 0
    for message in messages:
        turn_id = message.turn_id
        if turn_id <= 0:
            if message.speaker_type == "user":
                legacy_turn += 1
            turn_id = legacy_turn
        if turn_id > 0:
            grouped.setdefault(turn_id, []).append(message)

    turns: list[dict[str, Any]] = []
    for turn_id in sorted(grouped):
        ordered = sorted(grouped[turn_id], key=lambda m: (m.sequence_no, m.id))
        player_messages = [serialize_message(m) for m in ordered if m.speaker_type == "user"]
        npc_replies = [serialize_message(m) for m in ordered if m.speaker_type == "npc"]
        turns.append({
            "turn_id": turn_id,
            "user_message": player_messages[0] if player_messages else None,
            "messages": [serialize_message(m) for m in ordered],
            "npc_replies": npc_replies,
            "world_timeline": _timeline_for_turn(world_timeline, turn_id),
            "agent_memories": _agent_slice_for_turn(agent_memories, turn_id),
            "agent_decisions": _agent_decisions_for_turn(agent_memories, turn_id),
        })
    return turns


async def build_session_export_bundle(db: AsyncSession, session: GameSession) -> dict[str, Any]:
    scenario_result = await db.execute(
        select(ScenarioTemplate).where(ScenarioTemplate.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()

    speaker_directory: dict[str, dict[str, Any]] = {}
    if scenario:
        player = resolve_player_character(scenario)
        speaker_directory["user"] = {
            **player,
            "side": "player",
            "role": "player",
            "team_id": "player",
            "relationship_to_player": "self",
            "interaction_role": "player",
        }
        char_result = await db.execute(
            select(CharacterTemplate)
            .where(CharacterTemplate.scenario_id == scenario.id)
            .order_by(CharacterTemplate.sort_order, CharacterTemplate.id)
        )
        for char in char_result.scalars().all():
            speaker_directory[char.character_id] = {
                "character_id": char.character_id,
                "character_name": char.character_name,
                "job_title": char.job_title,
                "display_name": char.display_name,
                "side": char.side,
                "role": "npc",
                "team_id": char.team_id,
                "relationship_to_player": char.relationship_to_player,
                "interaction_role": char.interaction_role,
                "authority": char.authority or {},
            }

    msg_result = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.sequence_no, SessionMessage.id)
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
    serialized_messages = []
    for message in messages:
        row = serialize_message(message)
        row["speaker"] = speaker_directory.get(message.speaker_id, {
            "character_id": message.speaker_id,
            "display_name": message.speaker_id,
            "role": message.speaker_type,
        })
        serialized_messages.append(row)

    bundle = {
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
            "session_mode": session.session_mode,
            "run_config": session.run_config or {},
            "status": session.status,
            "created_at": _iso(session.created_at),
            "updated_at": _iso(session.updated_at),
        },
        "scenario": {
            "id": scenario.id if scenario else session.scenario_id,
            "slug": scenario.slug if scenario else None,
            "title": scenario.title if scenario else None,
            "schema_version": 2 if scenario else None,
            "task_config": scenario.task_config if scenario else None,
        },
        "character_names": character_names,
        "speaker_directory": speaker_directory,
        "orchestration_config": orch_cfg,
        "messages": serialized_messages,
        "dialogue_turns": dialogue_turns,
        "world_timeline": world_timeline,
        "agent_memories": agent_memories,
        "agent_progress": agent_progress,
        "last_debug": last_debug,
        "episode_memories": episode_memories,
        "shared_state": shared,
        "task_result": {} if session.session_mode == "baseline" else public_task_result(shared.get("task_state") or {}),
        "test_result": dict(shared.get("_test_state") or {}),
        "baseline_result": dict(shared.get("_baseline_state") or {}),
        "external_evaluation": dict(shared.get("_external_evaluation") or {}),
        "performance_trace": list(shared.get("_performance_trace") or []),
    }
    bundle["external_observation"] = build_external_observation(bundle)
    return bundle


def build_public_session_export_bundle(full: dict[str, Any]) -> dict[str, Any]:
    """Return the learner-safe transcript without private cognition or debug state."""
    messages: list[dict[str, Any]] = []
    for raw in full.get("messages") or []:
        message = {
            key: raw.get(key)
            for key in (
                "id", "speaker_id", "speaker_type", "speaker_source", "turn_id",
                "sequence_no", "content", "emotion", "gesture", "created_at", "speaker",
            )
        }
        messages.append(message)

    grouped: dict[int, list[dict[str, Any]]] = {}
    for message in messages:
        turn_id = int(message.get("turn_id") or 0)
        if turn_id > 0:
            grouped.setdefault(turn_id, []).append(message)
    dialogue_turns = []
    for turn_id in sorted(grouped):
        ordered = sorted(grouped[turn_id], key=lambda m: (int(m.get("sequence_no") or 0), int(m.get("id") or 0)))
        player = [m for m in ordered if m.get("speaker_type") == "user"]
        dialogue_turns.append({
            "turn_id": turn_id,
            "user_message": player[0] if player else None,
            "messages": ordered,
            "npc_replies": [m for m in ordered if m.get("speaker_type") == "npc"],
        })

    export_meta = dict(full.get("export_meta") or {})
    export_meta["format"] = "roommind-public-session-transcript"
    export_meta["note"] = (
        "Learner-safe public transcript. Private state, agent cognition, memory, "
        "reasoning, orchestration configuration, and debug data are excluded."
    )
    return {
        "export_meta": export_meta,
        "session": full.get("session") or {},
        "scenario": full.get("scenario") or {},
        "speaker_directory": full.get("speaker_directory") or {},
        "messages": messages,
        "dialogue_turns": dialogue_turns,
        "task_result": full.get("task_result") or {},
        "test_result": full.get("test_result") or {},
        "baseline_result": full.get("baseline_result") or {},
        "external_observation": full.get("external_observation") or {},
        "external_evaluation": full.get("external_evaluation") or {},
        "performance_trace": full.get("performance_trace") or [],
    }
