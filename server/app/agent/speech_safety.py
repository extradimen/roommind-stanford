"""Safety checks separating private agent cognition from public dialogue."""

from __future__ import annotations

import re


PUBLIC_RESPONSE_DRAFT = (
    "Respond directly and naturally to the latest public statement. Advance the "
    "negotiation without revealing private goals, internal plans, hidden knowledge, "
    "redlines, or reservation values."
)

_INTERNAL_SPEECH_MARKERS = (
    "private knowledge",
    "my current plan",
    "my plan is",
    "my bottom line",
    "i will first",
    "internal note",
    "real floor",
    "reservation value",
)
_TRUNCATED_LAST_WORDS = {
    "a", "an", "and", "at", "but", "for", "if", "in", "is", "no", "non",
    "of", "or", "the", "to", "with",
}


def speech_rejection_reason(content: str, *, active_plan_text: str = "") -> str | None:
    """Reject obvious internal-plan echoes and visibly truncated public speech."""
    text = " ".join((content or "").split()).strip()
    if not text:
        return "empty"

    lowered = text.casefold()
    if any(marker in lowered for marker in _INTERNAL_SPEECH_MARKERS):
        return "internal_language"

    plan = " ".join((active_plan_text or "").split()).strip().casefold()
    if plan and (lowered == plan or (len(plan) >= 48 and lowered.startswith(plan[:48]))):
        return "active_plan_echo"

    last_word_match = re.search(r"([A-Za-z]+)[^A-Za-z]*$", text)
    last_word = last_word_match.group(1).casefold() if last_word_match else ""
    if text[-1] not in ".!?\"'" and last_word in _TRUNCATED_LAST_WORDS:
        return "truncated"
    return None
