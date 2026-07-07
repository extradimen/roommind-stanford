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
#   - keyword boost for negotiation-critical signals
#   - length / event-type adjustments
# This score is stored permanently on the node and never recomputed.

_NEGOTIATION_KEYWORDS: list[tuple[str, float]] = [
    # price / cost
    ("价格", 2.0), ("单价", 2.0), ("报价", 2.0), ("成本", 1.5), ("费用", 1.5),
    ("price", 2.0), ("cost", 1.5), ("offer", 2.0), ("quote", 2.0),
    # contract / terms
    ("合同", 2.0), ("条款", 1.5), ("违约", 2.0), ("赔偿", 2.0),
    ("contract", 2.0), ("clause", 1.5), ("penalty", 2.0),
    # delivery / quantity
    ("交货", 1.5), ("交期", 1.5), ("数量", 1.0), ("批次", 1.0),
    ("delivery", 1.5), ("quantity", 1.0),
    # commitment words
    ("同意", 2.0), ("接受", 2.0), ("拒绝", 2.0), ("底线", 2.5), ("让步", 2.5),
    ("红线", 2.5), ("妥协", 2.0), ("坚持", 1.5),
    ("agree", 2.0), ("accept", 2.0), ("reject", 2.0), ("concede", 2.5),
    # payment
    ("付款", 1.5), ("账期", 1.5), ("预付", 1.5), ("定金", 1.5),
    ("payment", 1.5), ("deposit", 1.5),
]


def score_importance(content: str, event_type: str) -> float:
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
    for kw, weight in _NEGOTIATION_KEYWORDS:
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

_SYNONYM_MAP: dict[str, list[str]] = {
    "价格": ["单价", "报价", "费用", "成本", "价钱"],
    "单价": ["价格", "报价", "费用"],
    "合同": ["条款", "协议", "文件"],
    "底线": ["红线", "最低", "不能接受"],
    "让步": ["妥协", "退步", "折中"],
    "同意": ["接受", "认可", "ok", "好"],
    "拒绝": ["不同意", "不接受", "不行"],
    "交货": ["交期", "到货", "发货", "delivery"],
    "price": ["cost", "fee", "rate", "quote"],
    "agree": ["accept", "ok", "yes", "sure"],
    "reject": ["refuse", "no", "deny"],
}


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
    lang: str = "zh",
) -> str:
    """Natural-language observation from this agent's POV (no redundant name prefix)."""
    if event.event_type == "user_speech":
        return observation_user_speech(event.content, lang)
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
    reply_language: str = "zh",
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
        importance = score_importance(event.content, event.event_type)
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
