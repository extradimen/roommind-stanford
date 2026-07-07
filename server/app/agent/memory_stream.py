"""
Memory stream — Stanford Generative Agents architecture.

Retrieval score = α·recency + β·importance + γ·relevance

  recency    : exponential decay on turn distance (no LLM, pure math)
  importance : scored at write time by heuristic (stored permanently)
  relevance  : expanded token-overlap proxy for embedding cosine (no extra LLM)

All three dimensions are normalised to [0, 1] before combining (min-max,
per the Stanford paper) so that the weights α/β/γ are truly comparable.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AgentMemoryNode
from app.world.perception import relevance_score


@dataclass
class MemoryNode:
    node_id: str
    node_type: str          # observation | reflection | plan | action
    content: str
    importance: float       # 1-10, set permanently at write time
    turn_id: int
    tick: int
    source_event_ids: list[str] = field(default_factory=list)
    is_active: bool = True
    meta: dict[str, Any] = field(default_factory=dict)
    # last_accessed_turn tracks when this node was last retrieved
    # (mirrors Stanford's "last accessed time" for recency decay)
    last_accessed_turn: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_db(cls, row: AgentMemoryNode) -> "MemoryNode":
        return cls(
            node_id=str(row.id),
            node_type=row.node_type,
            content=row.content,
            importance=float(row.importance),
            turn_id=int(row.turn_id),
            tick=int(row.tick),
            source_event_ids=list(row.source_event_ids or []),
            is_active=bool(row.is_active),
            meta=dict(row.meta or {}),
            # Store last_accessed_turn in meta so it persists across loads
            last_accessed_turn=int((row.meta or {}).get("last_accessed_turn", row.turn_id)),
        )


class AgentMemoryStore:
    def __init__(self, session_id: int, character_id: str) -> None:
        self.session_id   = session_id
        self.character_id = character_id

    async def load_all(self, db: AsyncSession) -> list[MemoryNode]:
        result = await db.execute(
            select(AgentMemoryNode)
            .where(
                AgentMemoryNode.session_id   == self.session_id,
                AgentMemoryNode.character_id == self.character_id,
            )
            .order_by(AgentMemoryNode.turn_id, AgentMemoryNode.tick, AgentMemoryNode.id)
        )
        return [MemoryNode.from_db(r) for r in result.scalars().all()]

    async def append(
        self,
        db: AsyncSession,
        *,
        node_type: str,
        content: str,
        importance: float,
        turn_id: int,
        tick: int = 0,
        source_event_ids: list[str] | None = None,
        is_active: bool = True,
        meta: dict[str, Any] | None = None,
    ) -> MemoryNode:
        if node_type == "plan" and is_active:
            await self.deactivate_plans(db)

        merged_meta = dict(meta or {})
        merged_meta["last_accessed_turn"] = turn_id  # initialise to write time

        row = AgentMemoryNode(
            session_id=self.session_id,
            character_id=self.character_id,
            node_type=node_type,
            content=content.strip(),
            importance=min(10.0, max(1.0, float(importance))),
            turn_id=turn_id,
            tick=tick,
            source_event_ids=source_event_ids or [],
            is_active=is_active,
            meta=merged_meta,
        )
        db.add(row)
        await db.flush()
        return MemoryNode.from_db(row)

    async def update_last_accessed(
        self, db: AsyncSession, node_ids: list[str], current_turn: int
    ) -> None:
        """
        Stanford: recency is based on last-accessed time, not creation time.
        Call this after retrieval to keep frequently-used memories fresh.
        """
        if not node_ids:
            return
        result = await db.execute(
            select(AgentMemoryNode).where(
                AgentMemoryNode.session_id   == self.session_id,
                AgentMemoryNode.character_id == self.character_id,
                AgentMemoryNode.id.in_([int(nid) for nid in node_ids]),
            )
        )
        for row in result.scalars().all():
            meta = dict(row.meta or {})
            meta["last_accessed_turn"] = current_turn
            row.meta = meta

    async def deactivate_plans(self, db: AsyncSession) -> None:
        result = await db.execute(
            select(AgentMemoryNode).where(
                AgentMemoryNode.session_id   == self.session_id,
                AgentMemoryNode.character_id == self.character_id,
                AgentMemoryNode.node_type    == "plan",
                AgentMemoryNode.is_active.is_(True),
            )
        )
        for row in result.scalars().all():
            row.is_active = False


def _minmax_normalise(values: list[float]) -> list[float]:
    """Normalise a list of floats to [0, 1] using min-max scaling."""
    if not values:
        return values
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 if v > 0 else 0.0 for v in values]
    return [(v - lo) / (hi - lo) for v in values]


def retrieve_memories(
    nodes: list[MemoryNode],
    *,
    query: str,
    current_turn: int,
    k: int = 10,
    alpha: float = 1.0,
    beta: float = 1.0,
    gamma: float = 1.0,
    decay: float = 8.0,
) -> list[tuple[MemoryNode, float]]:
    """
    Stanford retrieval: score = α·recency + β·importance + γ·relevance

    recency    uses last_accessed_turn (not creation turn) so frequently
               retrieved memories stay fresh — mirrors Stanford's design.
    importance is the permanent score set at write time.
    relevance  is expanded token-overlap (proxy for embedding cosine).

    All three raw scores are min-max normalised before weighting (per paper).
    """
    eligible = [
        n for n in nodes
        if not (n.node_type == "plan" and not n.is_active)
    ]
    if not eligible:
        return []

    # Raw scores
    raw_recency    = [math.exp(-max(0, current_turn - n.last_accessed_turn) / decay) for n in eligible]
    raw_importance = [n.importance / 10.0 for n in eligible]
    raw_relevance  = [relevance_score(query, n.content) for n in eligible]

    # Min-max normalise each dimension
    norm_recency    = _minmax_normalise(raw_recency)
    norm_importance = _minmax_normalise(raw_importance)
    norm_relevance  = _minmax_normalise(raw_relevance)

    scored: list[tuple[MemoryNode, float]] = []
    for i, node in enumerate(eligible):
        score = (
            alpha * norm_recency[i]
            + beta  * norm_importance[i]
            + gamma * norm_relevance[i]
        )
        scored.append((node, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:k]


def active_plan(nodes: list[MemoryNode]) -> MemoryNode | None:
    plans = [n for n in nodes if n.node_type == "plan" and n.is_active]
    return plans[-1] if plans else None


def importance_accumulator(nodes: list[MemoryNode], since_turn: int) -> float:
    """Sum of observation importance since a given turn (used to trigger reflection)."""
    return sum(
        n.importance
        for n in nodes
        if n.node_type == "observation" and n.turn_id >= since_turn
    )
