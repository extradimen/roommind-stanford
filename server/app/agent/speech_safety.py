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
    r"\b(?:i(?:['’]ve| have)?|we(?:['’]ve| have)?)\s+(?:just\s+)?(?:sent|emailed|forwarded|submitted|archived|stored|streamed)\b",
    r"\b(?:has|have|had)\s+been\s+(?:attached|uploaded|sent|emailed|forwarded|submitted|archived|stored|streamed)\b",
    r"\b(?:attached|uploaded)\s+(?:is|are|you(?:'ll| will) find)\b",
    r"\b(?:the\s+)?attachment\s+(?:contains|includes|is|has)\b",
    r"\b(?:archive|file|document|report|letter|draft|package)\s+(?:upload|submission|transfer)\s+(?:is\s+)?(?:complete|completed|verified)\b",
    r"\b(?:upload|submission|transfer)\s+(?:is\s+)?(?:complete|completed|verified)\b",
    r"\bplease\s+find\s+(?:the\s+)?(?:attached|enclosed)\b",
    r"\b(?:see|review|check)\s+(?:the\s+)?attached\b",
    r"\b(?:download|open|access)\s+(?:it|the\s+(?:file|document|report))\s+(?:at|here)\b",
    r"\b(?:checksum|hash)(?:es)?\s+(?:has|have)?\s*(?:been\s+)?(?:verified|validated|matched|confirmed)\b",
    r"\b(?:checksum|hash)(?:es)?\s+match(?:es|ed)?\b",
)
_URL_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:https?|ftp|s3|repo|file)://[^\s<>\]\[\)\(]+",
    flags=re.IGNORECASE,
)
_HASH_RE = re.compile(r"(?<![A-Za-z0-9])[a-fA-F0-9]{32,64}(?![A-Za-z0-9])")
_ARTIFACT_REQUEST_PREFIX_RE = re.compile(
    r"\b(?:(?:could|can|would|will)\s+you|please\s+(?:confirm|send|forward|provide)|"
    r"confirm\s+(?:whether|if|once)|ask(?:ing)?\s+(?:whether|if))\b",
    flags=re.IGNORECASE,
)


def _contains_unsupported_artifact_claim(text: str) -> bool:
    """Separate impossible completed claims from legitimate requests/promises."""
    sentences = re.split(r"(?<=[.!?])\s+|[;]\s*", text)
    for sentence in sentences:
        for pattern in _UNSUPPORTED_ARTIFACT_PATTERNS:
            match = re.search(pattern, sentence, flags=re.IGNORECASE)
            if not match:
                continue
            # Asking another participant to confirm/provide evidence does not
            # itself assert that an external side effect occurred.  The later
            # answer is still rejected if it invents completed delivery.
            if _ARTIFACT_REQUEST_PREFIX_RE.search(sentence[:match.start()]):
                continue
            return True
    return False


def unsupported_evidence_reason(content: str, *, public_context: str = "") -> str | None:
    """Reject newly invented external evidence before it enters public dialogue.

    Text simulations can state material contents inline, but they cannot really
    attach/upload files or create verifiable links and hashes.  Existing public
    URLs/hashes may be quoted; newly generated ones are rejected.
    """
    text = " ".join((content or "").split()).strip()
    context = " ".join((public_context or "").split())
    if _contains_unsupported_artifact_claim(text):
        return "unsupported_artifact_claim"
    for value in _URL_RE.findall(text):
        if value not in context:
            return "unsupported_url"
    for value in _HASH_RE.findall(text):
        if value not in context:
            return "unsupported_hash"
    return None


def speech_rejection_reason(
    content: str, *, active_plan_text: str = "", public_context: str = "",
    validated_intent: dict | None = None,
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

    # G3: wording may not upgrade a transition that the public-world ledger
    # downgraded. This closes the gap where natural-language rendering claimed
    # completion after the action validator accepted only a commitment.
    intent = validated_intent or {}
    transition = str(intent.get("transition") or "")
    if transition in {"proposed", "committed", "in_progress", "blocked"}:
        for sentence in re.split(r"(?<=[.!?])\s+|[;]\s*", text):
            terminal_claim = re.search(
                r"\b(?:(?:it|this|that|the\s+[\w -]+)\s+(?:is|was|has been)|"
                r"(?:we|i)\s+(?:have\s+|['’]ve\s+)?)"
                r"(?:completed|submitted|uploaded|sent|verified|approved|accepted|executed)\b",
                sentence,
                flags=re.IGNORECASE,
            )
            if terminal_claim and not re.search(
                r"\b(?:if|once|when|after|before|unless|until)\b",
                sentence[:terminal_claim.start()],
                flags=re.IGNORECASE,
            ):
                return "speech_exceeds_validated_lifecycle"

    if text[-1] not in ".!?\"'”’":
        return "truncated"
    return None


def player_speech_rejection_reason(
    content: str, *, public_context: str = "", validated_intent: dict | None = None
) -> str | None:
    """Reject malformed structured output accidentally exposed as player dialogue."""
    text = (content or "").strip()
    if text.startswith(("{", "[", "```")):
        return "structured_output"
    lowered = text.casefold()
    if '"content"' in lowered and '"intent"' in lowered:
        return "structured_output"
    return speech_rejection_reason(
        text, public_context=public_context, validated_intent=validated_intent
    )
