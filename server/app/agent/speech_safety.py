"""Safety checks separating private agent cognition from public dialogue."""

from __future__ import annotations

import re

PUBLIC_RESPONSE_DRAFT = (
    "Respond directly and naturally to the latest public statement. Advance the "
    "configured task without revealing private goals, internal plans, hidden knowledge, "
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

_UNSUPPORTED_ARTIFACT_PATTERNS = (
    r"\b(?:i(?:['’]ve| have)?|we(?:['’]ve| have)?)\s+(?:attached|uploaded)\b",
    r"\b(?:attached|uploaded)\s+(?:is|are|you(?:'ll| will) find)\b",
    r"\bplease\s+find\s+(?:the\s+)?(?:attached|enclosed)\b",
    r"\b(?:download|open|access)\s+(?:it|the\s+(?:file|document|report))\s+(?:at|here)\b",
)
_URL_RE = re.compile(r"https?://[^\s<>\]\[\)\(]+", flags=re.IGNORECASE)
_HASH_RE = re.compile(r"(?<![A-Za-z0-9])[a-fA-F0-9]{32,64}(?![A-Za-z0-9])")


def unsupported_evidence_reason(content: str, *, public_context: str = "") -> str | None:
    """Reject newly invented external evidence before it enters public dialogue.

    Text simulations can state material contents inline, but they cannot really
    attach/upload files or create verifiable links and hashes.  Existing public
    URLs/hashes may be quoted; newly generated ones are rejected.
    """
    text = " ".join((content or "").split()).strip()
    context = " ".join((public_context or "").split())
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _UNSUPPORTED_ARTIFACT_PATTERNS):
        return "unsupported_artifact_claim"
    for value in _URL_RE.findall(text):
        if value not in context:
            return "unsupported_url"
    for value in _HASH_RE.findall(text):
        if value not in context:
            return "unsupported_hash"
    return None


def speech_rejection_reason(
    content: str, *, active_plan_text: str = "", public_context: str = ""
) -> str | None:
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

    unsupported = unsupported_evidence_reason(text, public_context=public_context)
    if unsupported:
        return unsupported

    if text[-1] not in ".!?\"'”’":
        return "truncated"
    return None


def player_speech_rejection_reason(content: str, *, public_context: str = "") -> str | None:
    """Reject malformed structured output accidentally exposed as player dialogue."""
    text = (content or "").strip()
    if text.startswith(("{", "[", "```")):
        return "structured_output"
    lowered = text.casefold()
    if '"content"' in lowered and '"intent"' in lowered:
        return "structured_output"
    return speech_rejection_reason(text, public_context=public_context)
