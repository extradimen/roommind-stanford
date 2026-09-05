"""Perception — what each agent notices from the world timeline."""

from __future__ import annotations

import re
from typing import Any

from app.models.db import CharacterTemplate
from app.i18n.reply_language import (
    character_display_name,
    observation_other_speech,
    observation_self_speech,
    observation_state_change,
    observation_user_speech,
)
from app.world.timeline import WorldEvent

# ---------------------------------------------------------------------------
# Importance scoring
# ---------------------------------------------------------------------------
# Stanford paper: importance is rated 1-10 by LLM at write time.
# Here we use a two-tier heuristic that avoids an extra LLM call:
#   - scenario-configured relevance-signal boost
#   - length / event-type adjustments
# This score is stored permanently on the node and never recomputed.

def score_importance(content: str, event_type: str, relevance_signals: list[Any] | None = None) -> float:
    """
    Permanent importance score stored at write time (Stanford: LLM rates 1-10).
    We use a deterministic heuristic to avoid the extra LLM call.
    Returns a float in [1.0, 10.0].
    """
    text = content.lower()
    score = 3.0

    # Event-type base boost
    if event_type == "user_speech":
        score += 2.0          # user always important
    elif event_type == "npc_speech":
        score += 1.0
    elif event_type == "agent_action":
        score += 0.5

    # Keyword boosts (capped so single word can't explode score)
    keyword_boost = 0.0
    configured: list[tuple[str, float]] = []
    for item in relevance_signals or []:
        if isinstance(item, str):
            configured.append((item, 1.5))
        elif isinstance(item, dict) and item.get("keyword"):
            configured.append((str(item["keyword"]), float(item.get("weight", 1.5))))
    for kw, weight in configured:
        if kw in text:
            keyword_boost += weight
    score += min(keyword_boost, 4.0)   # cap keyword contribution at 4 pts

    # Length bonus: longer utterances carry more information
    if len(content) > 120:
        score += 0.5
    elif len(content) > 60:
        score += 0.25

    return round(min(10.0, max(1.0, score)), 2)


# ---------------------------------------------------------------------------
# Relevance scoring  (Stanford: embedding cosine similarity)
# ---------------------------------------------------------------------------
# Full embedding would require a vector DB column.  Until then we use an
# *expanded* token-overlap approach:
#   1. Expand query / text tokens with a synonym map
#   2. Score = |overlap| / |query_tokens| (Jaccard-style, query-normalised)
# This is still a proxy, but it handles synonym drift ("价格" ↔ "单价").

_SYNONYM_MAP: dict[str, list[str]] = {}


def _expand_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for t in tokens:
        for syn in _SYNONYM_MAP.get(t, []):
            expanded.add(syn)
    return expanded


def _tokenize(text: str) -> set[str]:
    # Chinese single chars (meaningful) + western words ≥2 chars
    chars = set(re.findall(r"[\u4e00-\u9fff]{1,4}", text.lower()))
    words = set(re.findall(r"[a-zA-Z]{2,}", text.lower()))
    return chars | words


def relevance_score(query: str, text: str) -> float:
    """
    Expanded token-overlap relevance (proxy for embedding cosine).
    Returns float in [0.0, 1.0].
    """
    if not query.strip() or not text.strip():
        return 0.0
    q_tokens = _expand_tokens(_tokenize(query))
    t_tokens = _expand_tokens(_tokenize(text))
    if not q_tokens:
        return 0.0
    overlap = len(q_tokens & t_tokens)
    return round(min(1.0, overlap / len(q_tokens)), 4)


# ---------------------------------------------------------------------------
# Observation formatting
# ---------------------------------------------------------------------------

def format_observation(
    agent: CharacterTemplate,
    event: WorldEvent,
    *,
    lang: str = "en",
) -> str:
    """Natural-language observation from this agent's POV (no redundant name prefix)."""
    if event.event_type == "user_speech":
        speaker = str(event.meta.get("display_name") or event.meta.get("character_name") or "Player")
        return observation_user_speech(event.content, lang, speaker_name=speaker)
    if event.event_type == "npc_speech":
        if event.actor_id == agent.character_id:
            return observation_self_speech(event.content, lang)
        raw_name = event.meta.get("display_name") or event.actor_id
        name = character_display_name(str(event.actor_id), str(raw_name), lang)
        return observation_other_speech(name, event.content, lang)
    if event.event_type == "state_change":
        return observation_state_change(event.content, lang)
    if event.event_type == "agent_action":
        if event.actor_id == agent.character_id:
            return event.content
        raw_name = event.meta.get("display_name") or event.actor_id
        name = character_display_name(str(event.actor_id), str(raw_name), lang)
        return f"{name} {event.content}"
    return event.content


def perceive_events(
    agent: CharacterTemplate,
    events: list[WorldEvent],
    *,
    private_only_self: bool = True,
    reply_language: str = "en",
    relevance_signals: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Filter world events → per-agent observations.
    Each observation gets a permanent importance score (stored at write time).
    """
    observations: list[dict[str, Any]] = []
    for event in events:
        if event.event_type == "npc_speech" and event.actor_id == agent.character_id:
            if private_only_self:
                continue
        if event.event_type not in ("user_speech", "npc_speech", "state_change", "agent_action"):
            continue
        content = format_observation(agent, event, lang=reply_language)
        importance = score_importance(event.content, event.event_type, relevance_signals)
        observations.append(
            {
                "content": content,
                "importance": importance,
                "source_event_id": event.event_id,
                "event_type": event.event_type,
                "raw": event.content,
            }
        )
    return observations
