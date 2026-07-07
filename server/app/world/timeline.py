"""Append-only world timeline derived from group chat and state changes."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WorldEvent:
    event_id: str
    turn_id: int
    tick: int
    event_type: str  # user_speech | npc_speech | state_change | system
    actor_id: str
    content: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> WorldEvent:
        return cls(
            event_id=str(raw.get("event_id", uuid.uuid4().hex[:12])),
            turn_id=int(raw.get("turn_id", 0)),
            tick=int(raw.get("tick", 0)),
            event_type=str(raw.get("event_type", "system")),
            actor_id=str(raw.get("actor_id", "system")),
            content=str(raw.get("content", "")),
            meta=dict(raw.get("meta") or {}),
        )


class WorldTimeline:
    """Session-scoped world line stored in shared_state."""

    KEY = "world_timeline"

    def __init__(self, events: list[dict[str, Any]] | None = None) -> None:
        self.events: list[WorldEvent] = [
            WorldEvent.from_dict(e) for e in (events or []) if isinstance(e, dict)
        ]

    def append(
        self,
        *,
        turn_id: int,
        tick: int,
        event_type: str,
        actor_id: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> WorldEvent:
        evt = WorldEvent(
            event_id=uuid.uuid4().hex[:12],
            turn_id=turn_id,
            tick=tick,
            event_type=event_type,
            actor_id=actor_id,
            content=content,
            meta=meta or {},
        )
        self.events.append(evt)
        return evt

    def since_turn(self, turn_id: int) -> list[WorldEvent]:
        return [e for e in self.events if e.turn_id >= turn_id]

    def since_tick(self, turn_id: int, tick: int) -> list[WorldEvent]:
        return [
            e
            for e in self.events
            if e.turn_id > turn_id or (e.turn_id == turn_id and e.tick >= tick)
        ]

    def speech_context(self, limit: int = 30) -> str:
        lines: list[str] = []
        for e in self.events[-limit:]:
            if e.event_type in ("user_speech", "npc_speech"):
                lines.append(f"[{e.actor_id}]: {e.content}")
        return "\n".join(lines)

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.events]

    @classmethod
    def from_shared_state(cls, shared_state: dict[str, Any] | None) -> WorldTimeline:
        raw = (shared_state or {}).get(cls.KEY, [])
        if not isinstance(raw, list):
            return cls([])
        return cls(raw)

    def sync_messages(self, messages: list[dict[str, Any]], turn_id: int = 0) -> None:
        """Bootstrap timeline from existing session messages if empty."""
        if self.events:
            return
        tick = 0
        for m in messages:
            speaker_type = m.get("speaker_type", "user")
            speaker_id = str(m.get("speaker_id", "unknown"))
            content = str(m.get("content", ""))
            if speaker_type == "user":
                et = "user_speech"
            elif speaker_type == "npc":
                et = "npc_speech"
            else:
                et = "system"
            self.append(
                turn_id=turn_id,
                tick=tick,
                event_type=et,
                actor_id=speaker_id,
                content=content,
            )
            tick += 1
