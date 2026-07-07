"""Shared types and helpers for the generative-agent orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db import CharacterTemplate, DispatchRule, LLMConfig, ScenarioTemplate


@dataclass
class NPCReply:
    character_id: str
    display_name: str
    content: str
    emotion: str = "neutral"
    gesture: str = "talking"
    reasoning: str = ""


@dataclass
class OrchestratorResult:
    replies: list[NPCReply]
    phase: str
    shared_state: dict[str, Any]
    episode_events: list[dict[str, Any]] = field(default_factory=list)


def npc_replies_payload(replies: list[NPCReply]) -> list[dict[str, Any]]:
    return [
        {
            "type": "npc_speak",
            "speaker_id": r.character_id,
            "display_name": r.display_name,
            "text": r.content,
            "emotion": r.emotion,
            "gesture": r.gesture,
        }
        for r in replies
    ]


class OrchestratorSupport:
    async def get_llm_config(self, db: AsyncSession) -> LLMConfig | None:
        result = await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1))
        return result.scalar_one_or_none()

    async def load_scenario(self, db: AsyncSession, scenario_id: int) -> ScenarioTemplate:
        result = await db.execute(
            select(ScenarioTemplate)
            .where(ScenarioTemplate.id == scenario_id)
            .options(selectinload(ScenarioTemplate.characters))
        )
        scenario = result.scalar_one_or_none()
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return scenario

    async def load_dispatch_rules(self, db: AsyncSession, scenario_id: int) -> list[DispatchRule]:
        result = await db.execute(
            select(DispatchRule).where(
                DispatchRule.is_active.is_(True),
                (DispatchRule.scenario_id == scenario_id) | (DispatchRule.scenario_id.is_(None)),
            )
        )
        return list(result.scalars().all())

    def match_dispatch_rules(self, user_input: str, rules: list[DispatchRule]) -> list[str]:
        user_lower = user_input.lower()
        candidates: list[tuple[int, str]] = []
        for rule in rules:
            if not rule.trigger_keywords:
                continue
            for kw in rule.trigger_keywords:
                if kw.lower() in user_lower:
                    for idx, cid in enumerate(rule.priority_character_ids):
                        candidates.append((idx, cid))
                    break
        candidates.sort(key=lambda x: x[0])
        seen: set[str] = set()
        ordered: list[str] = []
        for _, cid in candidates:
            if cid not in seen:
                seen.add(cid)
                ordered.append(cid)
        return ordered

    def match_mentioned_characters(
        self, user_input: str, characters: list[CharacterTemplate]
    ) -> list[str]:
        hits: list[str] = []
        seen: set[str] = set()
        for c in characters:
            labels = [c.display_name]
            for sep in ("（", "("):
                if sep in c.display_name:
                    labels.append(c.display_name.split(sep)[0].strip())
            for label in labels:
                if len(label) >= 2 and label in user_input and c.character_id not in seen:
                    hits.append(c.character_id)
                    seen.add(c.character_id)
                    break
        return hits

    def parse_json(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        candidates = [text]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            candidates.append(text[start:end])

        for candidate in candidates:
            if not candidate:
                continue
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue

        return {"content": text}


orch_support = OrchestratorSupport()
