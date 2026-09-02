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
_PROTECTED_STOPWORDS = {
    "a", "an", "and", "are", "exact", "has", "have", "is", "of", "our",
    "the", "their", "to", "we", "with",
}

_LIFECYCLE_RANK = {
    "proposed": 0,
    "committed": 1,
    "in_progress": 2,
    "submitted": 3,
    "verified": 4,
    "accepted": 5,
}

_STRONG_PUBLIC_CLAIMS = (
    (4, re.compile(
        r"\b(?:has|have|had)\s+"
        r"(?:already\s+|now\s+)?(?:confirmed|verified|validated)\b",
        flags=re.IGNORECASE,
    )),
    (5, re.compile(
        r"\b(?:has|have|had)\s+"
        r"(?:already\s+|now\s+)?"
        r"(?:approved|accepted|finalized|resolved|complete|completed|executed)\b",
        flags=re.IGNORECASE,
    )),
    (4, re.compile(
        r"\b(?:is|are|was|were|has been|have been)\s+"
        r"(?:already\s+|now\s+|fully\s+)?"
        r"(?:confirmed|verified|validated|aligned|grounded)\b",
        flags=re.IGNORECASE,
    )),
    (5, re.compile(
        r"\b(?:is|are|was|were|has been|have been)\s+"
        r"(?:already\s+|now\s+|fully\s+)?"
        r"(?:approved|accepted|finalized|resolved|complete|completed)\b",
        flags=re.IGNORECASE,
    )),
    (5, re.compile(
        r"\b(?:will|shall)\s+be\s+(?:already\s+|fully\s+)?"
        r"(?:confirmed|verified|validated|approved|accepted|finalized|"
        r"resolved|complete|completed)\b",
        flags=re.IGNORECASE,
    )),
    (3, re.compile(
        r"\b(?:have|has|had)\s+(?:already\s+|now\s+)?"
        r"(?:submitted|provided|delivered|shared|presented)\b",
        flags=re.IGNORECASE,
    )),
    (2, re.compile(
        r"\b(?:i(?:'m| am)|we(?:'re| are)|they(?:'re| are)|"
        r"[a-z][\w .'-]{0,60}\s+(?:is|are))\s+"
        r"(?:now\s+)?(?:working|reviewing|preparing|executing|implementing|"
        r"verifying|investigating)\b",
        flags=re.IGNORECASE,
    )),
    (1, re.compile(
        r"\b(?:i|we)\s+(?:will|shall|commit(?:ted)?\s+to|agree\s+to|"
        r"undertake\s+to|plan\s+to)\b",
        flags=re.IGNORECASE,
    )),
    (5, re.compile(
        r"\b(?:ready\s+to|can\s+now|will\s+now)\s+"
        r"(?:proceed|move\s+forward|finalize|close)\b",
        flags=re.IGNORECASE,
    )),
)

_NON_ASSERTIVE_PREFIX_RE = re.compile(
    r"\b(?:if|once|when|after|before|unless|until|whether|need(?:s)?\s+to|"
    r"must|should|could|would|please|cannot|can't|not|without|await(?:ing)?|"
    r"require(?:s|d)?\s+(?:us\s+|them\s+|him\s+|her\s+|you\s+)?to)\b",
    flags=re.IGNORECASE,
)

_RETROSPECTIVE_ANCHOR_RE = re.compile(
    r"\b(?:in\s+(?:my|our)\s+(?:previous|prior|former)\s+"
    r"(?:role|job|team|company|organization)|previously|historically|"
    r"in\s+the\s+past|last\s+(?:year|quarter|month|week)|at\s+the\s+time|"
    r"back\s+then|when\s+(?:i|we)\s+(?:led|managed|worked|served|built|"
    r"delivered|handled|joined|was|were)|during\s+(?:my|our|that|the)\s+"
    r"(?:tenure|project|initiative|engagement|incident|launch)|"
    r"(?:i|we)\s+once\b|in\s+20\d{2}\b|"
    # Natural interview answers often begin directly with a past-tense action
    # rather than the exact phrase "in my previous role".
    r"(?:i|we)\s+(?:led|managed|owned|built|delivered|handled|resolved|"
    r"launched|designed|implemented|partnered|introduced|created|ran|used|"
    r"worked|aligned|facilitated|negotiated|coordinated|shipped|reduced|"
    r"increased|improved|measured|tested|learned)\b|"
    r"(?:one|a)\s+(?:example|project|initiative|incident|launch)\s+"
    r"(?:was|involved|began)\b)",
    flags=re.IGNORECASE,
)


def retrospective_claim_grounded(text: str) -> bool:
    """Return whether public wording actually locates a claim in the past."""
    return bool(_RETROSPECTIVE_ANCHOR_RE.search(" ".join((text or "").split())))


def _speech_exceeds_validated_lifecycle(text: str, intent: dict) -> bool:
    """Detect public assertions stronger than the prevalidated transition.

    The natural-language renderer is untrusted just like the decision model.
    This check covers first- and third-person lifecycle claims so a fallback or
    renderer cannot say that another participant confirmed/approved/completed
    something when the authoritative intent is only proposed or committed.
    """
    if (
        str(intent.get("simulation_scope") or "") == "retrospective"
        and retrospective_claim_grounded(text)
    ):
        return False
    transition = str(intent.get("transition") or "proposed")
    allowed_rank = _LIFECYCLE_RANK.get(transition, 0)
    for sentence in re.split(r"(?<=[.!?])\s+|[;]\s*", text):
        for claimed_rank, pattern in _STRONG_PUBLIC_CLAIMS:
            for match in pattern.finditer(sentence):
                prefix = sentence[max(0, match.start() - 72):match.start()]
                if _NON_ASSERTIVE_PREFIX_RE.search(prefix):
                    continue
                if claimed_rank > allowed_rank:
                    return True
    return False


def protected_information_reason(
    content: str, *, protected_secrets: list[str] | None = None,
) -> str | None:
    """Reject distinctive values or phrases copied from protected role state."""
    text = " ".join((content or "").casefold().split())
    text_tokens = re.findall(r"[\w.%+-]+", text)
    text_ngrams = {
        tuple(text_tokens[index:index + 3])
        for index in range(max(0, len(text_tokens) - 2))
    }
    for raw_secret in protected_secrets or []:
        secret = " ".join(str(raw_secret or "").casefold().split())
        if not secret:
            continue
        # Numeric terms paired with their business unit/currency are highly
        # distinctive and must never be repeated from a protected secret.
        for match in re.findall(
            r"(?<![\w.])\d+(?:\.\d+)?\s*(?:%|rmb|cny|usd|eur|gbp|days?|months?|years?|units?)",
            secret,
        ):
            if match in text:
                return "protected_information_leak"
        tokens = [
            token for token in re.findall(r"[\w.%+-]+", secret)
            if token not in _PROTECTED_STOPWORDS and not token.isdigit()
        ]
        if len(tokens) >= 3:
            secret_ngrams = {
                tuple(tokens[index:index + 3])
                for index in range(len(tokens) - 2)
            }
            if text_ngrams.intersection(secret_ngrams):
                return "protected_information_leak"
        elif len(tokens) == 2 and " ".join(tokens) in text:
            return "protected_information_leak"
    return None


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


def _contains_live_artifact_presentation(text: str) -> bool:
    """Detect a purported artifact being supplied in the current dialogue.

    Retrospective interviews may truthfully discuss artifacts used in a past
    job. They still cannot manufacture a file in the current text session.
    """
    lowered = text.casefold()
    patterns = (
        r"\b(?:see|review|open|download)\s+(?:the\s+)?attached\b",
        r"\battached\s+(?:is|are)\b",
        r"\b(?:here(?:'s| is| are)|please find)\b[^.!?]{0,100}\battached\b",
        r"\b(?:i|we)(?:'ve| have)\s+(?:just\s+)?(?:attached|uploaded|emailed|sent)\b",
        r"\b(?:i|we)\s+just\s+(?:attached|uploaded|emailed|sent)\b",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def unsupported_evidence_reason(
    content: str, *, public_context: str = "",
    allow_retrospective_artifact_claims: bool = False,
) -> str | None:
    """Reject newly invented external evidence before it enters public dialogue.

    Text simulations can state material contents inline, but they cannot really
    attach/upload files or create verifiable links and hashes.  Existing public
    URLs/hashes may be quoted; newly generated ones are rejected.
    """
    text = " ".join((content or "").split()).strip()
    context = " ".join((public_context or "").split())
    if _contains_unsupported_artifact_claim(text):
        if (
            not allow_retrospective_artifact_claims
            or _contains_live_artifact_presentation(text)
        ):
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
    protected_secrets: list[str] | None = None,
    public_draft_text: str = "",
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
    draft = " ".join((public_draft_text or "").split()).strip().casefold()
    if draft and (
        lowered == draft
        or (len(draft) >= 40 and lowered.startswith(draft[:40]))
    ):
        return "public_draft_echo"

    protected_reason = protected_information_reason(
        text, protected_secrets=protected_secrets
    )
    if protected_reason:
        return protected_reason

    intent = validated_intent or {}
    retrospective_grounded = retrospective_claim_grounded(text)
    unsupported = unsupported_evidence_reason(
        text,
        public_context=public_context,
        allow_retrospective_artifact_claims=(
            str(intent.get("simulation_scope") or "") == "retrospective"
            and retrospective_grounded
        ),
    )
    if unsupported:
        return unsupported
    if (
        str(intent.get("simulation_scope") or "") == "retrospective"
        and not retrospective_grounded
        # Questions and discussion moves can be mislabeled retrospective by
        # a structured-output model without asserting a historical fact. Only
        # reject wording that actually exceeds the proposed lifecycle. This
        # still blocks live claims such as "I am verifying it now".
        and _speech_exceeds_validated_lifecycle(text, intent)
    ):
        return "retrospective_scope_not_grounded_in_quote"

    # G3.2: the wording must be entailed by the approved lifecycle, including
    # third-party claims ("the director has confirmed") and closure language.
    if intent and _speech_exceeds_validated_lifecycle(text, intent):
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
