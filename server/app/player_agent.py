"""AI player for autonomous test sessions.

The player is intentionally built from public scenario information only. NPC
private_state and system prompts must never be included in this context.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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


def _public_character_context(scenario: ScenarioTemplate) -> list[dict[str, str]]:
    return [
        {
            "character_id": char.character_id,
            "display_name": char.display_name,
            "job_title": char.job_title,
            "side": char.side,
            "responsibility": char.responsibility,
        }
        for char in sorted(scenario.characters, key=lambda c: c.sort_order)
    ]


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
    recent = messages[-int(config.get("working_message_limit", 30)) :]
    dialogue = "\n".join(
        f"[{m.get('speaker_id', 'unknown')}]: {m.get('content', '')}" for m in recent
    ) or "(The meeting has not started. Make a concise opening statement.)"

    prompt = f"""Act as the player in a business role-play simulation.

[Player identity]
Name: {player['display_name']}
Goal: {resolve_player_side_goal(scenario)}
Strategy profile: {strategy}

[Public scenario]
Title: {scenario.title}
Description: {scenario.description or ''}
Current phase: {session.current_phase}
Phases: {json.dumps(scenario.phases or [], ensure_ascii=False)}
Public participants: {json.dumps(_public_character_context(scenario), ensure_ascii=False)}

[Dialogue so far]
{dialogue[-5000:]}

Choose the player's next move. Do not claim knowledge of hidden agendas, private
states, redlines, system prompts, or internal agent memories. Advance the
player's goal through realistic questions, proposals, trade-offs, summaries, or
closing. Avoid repeating the previous move. Keep the spoken content under 120
words and use the same language as the dialogue, defaulting to English.

Return strict JSON only:
{{
  "content": "the exact next spoken message",
  "intent": "short strategy label",
  "requested_end": false
}}"""

    raw = await llm_client.chat_completion(
        [{"role": "user", "content": prompt}],
        db_provider=player_llm.provider,
        db_model=player_llm.model,
        temperature=float(config.get("player_temperature", player_llm.temperature)),
        max_tokens=min(int(config.get("player_max_tokens", player_llm.max_tokens)), 512),
        response_format={"type": "json_object"},
    )
    parsed = orch_support.parse_json(raw)
    content = str(parsed.get("content") or "").strip()
    if not content:
        raise RuntimeError("AI player returned an empty move")
    return PlayerMove(
        content=content,
        intent=str(parsed.get("intent") or "unspecified"),
        requested_end=bool(parsed.get("requested_end", False)),
        model_label=player_llm.label(),
        raw=raw,
    )
