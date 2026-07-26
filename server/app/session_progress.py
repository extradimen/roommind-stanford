"""Deterministic session phase progression and agreement detection."""

from __future__ import annotations


def _phase(phases: list[str], names: tuple[str, ...], fallback_index: int) -> str:
    for phase in phases:
        lowered = phase.casefold()
        if any(name in lowered for name in names):
            return phase
    return phases[min(fallback_index, len(phases) - 1)]


def infer_session_phase(
    phases: list[str],
    *,
    turn_id: int,
    player_text: str,
    npc_texts: list[str],
    requested_end: bool = False,
) -> str:
    available = phases or ["opening", "discovery", "bargaining", "closing"]
    combined = " ".join([player_text, *npc_texts]).casefold()
    if requested_end or (turn_id >= 2 and any(word in combined for word in (
        "final offer", "finalize", "shake on", "sign the", "close the deal",
    ))):
        return _phase(available, ("clos", "agreement"), len(available) - 1)
    if turn_id >= 2 and any(word in combined for word in (
        "price", "rmb", "offer", "penalty", "payment terms", "liquidated damages",
    )):
        return _phase(available, ("bargain", "negotiat", "contract"), min(2, len(available) - 1))
    if turn_id >= 2 and any(word in combined for word in (
        "volume", "capacity", "clarify", "understand", "explain", "constraints",
    )):
        return _phase(available, ("discover", "information"), min(1, len(available) - 1))
    return available[0]


def has_mutual_agreement(player_text: str, npc_texts: list[str], *, turn_id: int) -> bool:
    if turn_id < 2:
        return False
    player = player_text.casefold()
    npc = " ".join(npc_texts).casefold()
    player_close = any(x in player for x in ("final offer", "shake on", "can we agree", "finalize"))
    npc_accept = any(x in npc for x in (
        "that works", "we have a deal", "agreed", "i accept", "we accept", "deal is agreed",
    ))
    return player_close and npc_accept
