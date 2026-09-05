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
    r"\b(?:is|are)\s+(?:now\s+)?attached\b",
    r"\battached\s+(?:below|here|herewith|for\s+(?:your\s+)?review)\b",
    r"\bplease\s+find\b[^.!?]{0,140}\b(?:attached|enclosed)\b",
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

# G3.6: classify visible operational completion from the words themselves,
# independently of the model-authored ``public_intent.kind``.  In G3.5 a model
# could label "containment is now active" as an ordinary statement and thereby
# bypass the source-typed action check.  These patterns intentionally target
# current-world side effects, not ordinary discussion outcomes such as agreeing
# a price or approving a plan.
_CURRENT_WORLD_OBJECT_RE = re.compile(
    r"\b(?:containment|isolation|firewall|traffic(?:\s+shift)?|rollback|rollout|"
    r"deployment|release|service|system|server|cluster|pod|node|snapshot|"
    r"memory\s+dump|health\s+check|status(?:[- ]page)?|public\s+update|"
    r"archive|upload|attachment|email|file|document|report|hash(?:es)?|checksum(?:s)?|log(?:s)?|"
    r"transaction(?:s)?|monitoring|metrics|telemetry)\b",
    flags=re.IGNORECASE,
)
_CURRENT_WORLD_TERMINAL_RE = re.compile(
    r"\b(?:is|are|was|were|remains?|has\s+(?:just\s+)?been|have\s+(?:just\s+)?been)\s+"
    r"(?:already\s+|now\s+|fully\s+|successfully\s+)?(?:active|activated|inactive|deactivated|"
    r"complete|completed|finished|deployed|published|posted|shared|uploaded|attached|sent|delivered|"
    r"blocked|isolated|disabled|enabled|redirected|shifted|"
    r"archived|captured|stored|restored|rolled\s+back|verified|validated|reviewed|"
    r"matched|secured|immutable|healthy|stable|green|applied|terminated)\b|"
    r"\b(?:has|have)\s+(?:already\s+|now\s+|fully\s+|all\s+)?"
    r"(?:completed|finished|deployed|published|posted|shared|uploaded|attached|sent|archived|"
    r"captured|stored|restored|rolled\s+back|verified|validated|reviewed|matched|secured|executed|"
    r"blocked|isolated|disabled|enabled|redirected|shifted|delivered)\b|"
    r"\b(?:i|we)\s+(?:have\s+|['’]ve\s+)?(?:activated|deactivated|completed|"
    r"finished|deployed|published|posted|shared|uploaded|attached|sent|archived|captured|"
    r"stored|restored|rolled\s+back|verified|validated|reviewed|matched|secured|executed|blocked|isolated|"
    r"disabled|enabled|redirected|shifted|delivered|applied|terminated)\b",
    flags=re.IGNORECASE,
)

_UNREGISTERED_OWNER_PATTERNS = (
    re.compile(
        r"\b(?:assign(?:ing)?|designate|appoint)\s+"
        r"(?P<name>[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)+)\s+"
        r"(?:\([^)]{1,80}\)\s+)?"
        r"(?:as|to)\b"
    ),
    re.compile(
        r"\b(?P<name>[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)+)\s+"
        r"(?:is|stays|will\s+be|can\s+be)\s+(?:the\s+)?"
        r"(?:primary\s+)?(?:[A-Za-z][A-Za-z-]*\s+){0,3}"
        r"(?:owner|lead|reviewer|assignee)\b"
    ),
)
_EXTERNAL_FOLLOWUP_QUOTE_RE = re.compile(
    r"\b(?:after\s+(?:this|the)\s+meeting|post[- ]meeting|offline|outside\s+"
    r"(?:this|the)\s+(?:meeting|session)|external\s+follow[- ]?up|follow[- ]?up\s+"
    r"(?:after|outside)|by\s+(?:end\s+of\s+day|tomorrow|next\s+(?:week|meeting)))\b",
    flags=re.IGNORECASE,
)


def unregistered_participant_assignment_reason(
    content: str,
    *,
    participant_aliases: dict[str, list[str] | tuple[str, ...]] | None = None,
    validated_intent: dict | None = None,
) -> str | None:
    """Reject assigning in-session responsibility to a participant who cannot act.

    External people may be discussed, but an autonomous meeting must not hand a
    blocking task to an invented name and then wait for that nonexistent agent.
    The deliberately narrow detector only covers explicit two-part personal-name
    ownership clauses.
    """
    intent = validated_intent or {}
    external_intent = (
        str(intent.get("simulation_scope") or "") == "external"
        or str(intent.get("evidence_source") or "") == "external_followup"
    )
    if external_intent and _EXTERNAL_FOLLOWUP_QUOTE_RE.search(content or ""):
        return None
    aliases = {
        " ".join(str(alias or "").casefold().split())
        for values in (participant_aliases or {}).values()
        for alias in (values or [])
        if str(alias or "").strip()
    }
    if not aliases:
        return None
    for sentence in re.split(r"(?<=[.!?])\s+|[;]\s*", content or ""):
        for pattern in _UNREGISTERED_OWNER_PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue
            name = " ".join(match.group("name").casefold().split())
            if name not in aliases:
                return "unregistered_participant_assignment"
    return None

_TERSE_TERMINAL_RE = re.compile(
    r"^(?:the\s+)?(?:sample\s+)?(?:log(?:\s+entries|s)?|attachment|email|file|"
    r"document|report|traffic|service|system)\s+(?:successfully\s+|now\s+)?"
    r"(?:attached|uploaded|sent|delivered|blocked|isolated|restored|verified|"
    r"completed|deployed)\b",
    flags=re.IGNORECASE,
)
_FUTURE_OR_CONDITIONAL_RE = re.compile(
    r"\b(?:if|once|when|after|before|until|unless|would|could|should|must|"
    r"will|shall|plan\s+to|intend\s+to|ready\s+to|need\s+to|expect(?:ed)?\s+to|"
    r"need\s+confirmation\s+that|need\s+to\s+confirm|verification\s+status|"
    r"in\s+progress|still\s+(?:running|pending|underway)|pending|awaiting)\b",
    flags=re.IGNORECASE,
)
_ARTIFACT_REQUEST_PREFIX_RE = re.compile(
    r"\b(?:(?:could|can|would|will)\s+you|please\s+(?:confirm|send|forward|provide)|"
    r"confirm\s+(?:whether|if|once)|ask(?:ing)?\s+(?:whether|if)|"
    r"(?:still\s+)?need\s+(?:confirmation\s+that|to\s+confirm(?:\s+whether|\s+if)?))\b",
    flags=re.IGNORECASE,
)
_PROTECTED_STOPWORDS = {
    "a", "an", "and", "are", "exact", "has", "have", "is", "of", "our",
    "the", "their", "to", "we", "with",
}

_REPETITION_STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "been", "before",
    "could", "from", "have", "into", "just", "please", "should", "that",
    "the", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "today", "under", "will", "with", "would", "you",
    "your",
}


def near_duplicate_public_utterance(
    content: str, prior_utterances: list[str] | tuple[str, ...]
) -> bool:
    """Detect a same-speaker near-repeat without judging topic semantics.

    Only the speaker's own recent public turns should be supplied.  The high
    overlap threshold deliberately permits another participant to restate or
    challenge a point, while blocking the promise/request paraphrase loops
    seen in long autonomous meetings.
    """
    normalized = " ".join((content or "").casefold().split()).strip()
    if not normalized:
        return False

    def tokens(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", value.casefold())
            if len(token) >= 3 and token not in _REPETITION_STOPWORDS
        }

    current_tokens = tokens(normalized)
    for prior in list(prior_utterances or ())[-4:]:
        previous = " ".join((prior or "").casefold().split()).strip()
        if not previous:
            continue
        if normalized == previous:
            return True
        previous_tokens = tokens(previous)
        minimum = min(len(current_tokens), len(previous_tokens))
        if minimum < 6:
            continue
        overlap = len(current_tokens.intersection(previous_tokens)) / minimum
        if overlap >= 0.84:
            return True
    return False


_PLAYER_RESPONSE_REASONING_RE = re.compile(
    r"\b(?:ask|asking|prompt|prompting|invite|inviting)\b"
    r"[^.!?]{0,120}\b(?:user|player|candidate|interviewee|participant)\b|"
    r"\b(?:user|player|candidate|interviewee|participant)\b"
    r"[^.!?]{0,80}\b(?:to\s+(?:answer|respond|explain|describe|share)|for\s+an?\s+answer)\b",
    flags=re.IGNORECASE,
)
_VISIBLE_RESPONSE_REQUEST_RE = re.compile(
    r"(?:\?|？)|\b(?:can|could|would|will)\s+you\b|"
    r"(?:^|[.!?]\s+)\s*(?:please\s+)?"
    r"(?:tell|describe|explain|share|walk|give|answer|respond|address)\b|"
    r"(?:^|[.!?]\s+)\s*[\w .'-]{2,60}[,—:-]\s*please\s+"
    r"(?:tell|describe|explain|share|walk|give|answer|respond|address)\b",
    flags=re.IGNORECASE,
)


def public_speech_act_mismatch(reasoning: str, content: str) -> bool:
    """Reject speech that contradicts the decision's intended floor action.

    Private reasoning is not proof of public facts, but it is useful for a
    narrow structural check: an agent that decided to ask the player a
    question must not publish a first-person answer on the player's behalf.
    """
    if not _PLAYER_RESPONSE_REASONING_RE.search(reasoning or ""):
        return False
    return not bool(_VISIBLE_RESPONSE_REQUEST_RE.search(content or ""))


def direct_question_to_player(
    content: str,
    *,
    public_intent: dict | None = None,
    npc_labels: list[str] | tuple[str, ...] = (),
    player_labels: list[str] | tuple[str, ...] = (),
    participant_aliases: dict[str, list[str] | tuple[str, ...]] | None = None,
) -> bool:
    """Detect when an NPC has explicitly handed the conversational floor to the player.

    Prefer a validated target id.  The text fallback is intentionally narrow:
    it requires a visible question/request and rejects utterances that name a
    different NPC as the addressee.
    """
    return resolve_direct_question_target(
        content,
        public_intent=public_intent,
        npc_labels=npc_labels,
        player_labels=player_labels,
        participant_aliases=participant_aliases,
    ) == "user"


def _direct_address_aliases(labels: list[str] | tuple[str, ...]) -> list[str]:
    aliases: list[str] = []
    for raw in labels:
        normalized = " ".join(str(raw or "").casefold().split()).strip()
        if len(normalized) < 2:
            continue
        aliases.append(normalized)
        # Real dialogue usually addresses a person by given name even when the
        # directory stores a full display name and title.
        bare = re.split(r"\s*[（(]", normalized, maxsplit=1)[0].strip()
        parts = re.findall(r"[\w'-]+", bare)
        if len(parts) >= 2 and len(parts[0]) >= 2:
            aliases.append(parts[0])
    return sorted(set(aliases), key=len, reverse=True)


def resolve_direct_question_target(
    content: str,
    *,
    public_intent: dict | None = None,
    npc_labels: list[str] | tuple[str, ...] = (),
    player_labels: list[str] | tuple[str, ...] = (),
    participant_aliases: dict[str, list[str] | tuple[str, ...]] | None = None,
) -> str:
    """Resolve the addressee of a visible direct question.

    Quote-level address wins over model-authored metadata.  When the quote does
    not name anyone, a validated registered ``target_id`` wins; only then does
    the conservative second-person fallback infer the player.  This makes the
    runtime rule and frozen forensic probe use the same deterministic contract.
    """
    intent = public_intent or {}
    text = " ".join((content or "").split()).strip()
    if not text or not _VISIBLE_RESPONSE_REQUEST_RE.search(text):
        return ""
    folded = text.casefold()
    aliases_by_id: dict[str, list[str]] = {
        str(actor_id): _direct_address_aliases(list(labels or []))
        for actor_id, labels in (participant_aliases or {}).items()
    }
    if not aliases_by_id:
        aliases_by_id = {
            "user": _direct_address_aliases(list(player_labels or [])),
            **{
                f"npc:{index}": _direct_address_aliases([label])
                for index, label in enumerate(npc_labels or ())
            },
        }

    named_matches: list[tuple[int, int, str]] = []
    for actor_id, aliases in aliases_by_id.items():
        for alias in aliases:
            patterns = (
                rf"(?:^|[.!?]\s+)\s*{re.escape(alias)}\s*[,—:-]",
                rf"\b(?:can|could|would|will)\s+you\s*,?\s*{re.escape(alias)}\b",
            )
            positions = [
                match.start()
                for pattern in patterns
                for match in [re.search(pattern, folded)]
                if match
            ]
            if positions:
                named_matches.append((min(positions), -len(alias), actor_id))
    if named_matches:
        return min(named_matches)[2]

    target_id = str(intent.get("target_id") or "").casefold().strip()
    if target_id in {"player", "candidate", "interviewee"}:
        target_id = "user"
    if target_id and (not aliases_by_id or target_id in aliases_by_id):
        return target_id
    if target_id:
        # Some providers return the requested participant's display name even
        # though the schema asks for an id.  Resolve it only against the frozen
        # directory; never accept an unregistered free-form actor.
        normalized_target = " ".join(target_id.split())
        matching_actors = [
            actor_id for actor_id, aliases in aliases_by_id.items()
            if normalized_target in aliases
        ]
        if len(matching_actors) == 1:
            return matching_actors[0]

    for label in _direct_address_aliases(list(player_labels or [])):
        if re.search(rf"\b{re.escape(label)}\b", folded):
            return "user"
    return "user" if re.search(r"\b(?:you|your)\b", folded) else ""


_CROSS_ROLE_SUBSTITUTION_RE = re.compile(
    r"\b(?:i|we)\s+(?:(?:can|do|will|would|must|should)\s+)?"
    r"(?:confirm|certify|verify|validate|report|provide|supply|share|commit|"
    r"promise|guarantee|approve|accept|reject|measure|calculate|conclude|"
    r"found|observed|tested|inspected|reviewed|completed|executed)\b",
    flags=re.IGNORECASE,
)


def npc_directed_question_handoff_reason(
    content: str,
    *,
    target_id: str,
    public_intent: dict | None = None,
    participant_aliases: dict[str, list[str] | tuple[str, ...]] | None = None,
) -> str | None:
    """Require the player to yield an NPC-directed question without answering it."""
    target = str(target_id or "").strip()
    if not target or target == "user":
        return None
    text = " ".join((content or "").split()).strip()
    if resolve_direct_question_target(
        text,
        public_intent=public_intent,
        participant_aliases=participant_aliases,
    ) != target:
        return "player_did_not_yield_npc_directed_question"
    if len(text.split()) > 45:
        return "player_expanded_npc_handoff"
    substitution_text = re.sub(
        r"\b(?:i|we)\s+(?:will|would|can|could|should|do)\s+not\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if _CROSS_ROLE_SUBSTITUTION_RE.search(substitution_text):
        return "player_answered_for_npc"
    return None


def normalized_public_propositions(content: str) -> list[dict[str, str]]:
    """Normalize visible completion claims before applying source policy.

    The model's intent label is not trusted.  Each complete public clause is
    reduced to an object, terminal predicate, and modality so active voice,
    passive voice, perfect aspect, and terse status fragments receive the same
    grounding rule.
    """
    propositions: list[dict[str, str]] = []
    normalized = " ".join((content or "").split())
    for clause in re.split(r"(?<=[.!?])\s+|[;]\s*", normalized):
        clause = clause.strip()
        if not clause or clause.rstrip().endswith("?"):
            continue
        terminal = _CURRENT_WORLD_TERMINAL_RE.search(clause) or _TERSE_TERMINAL_RE.search(clause)
        object_match = _CURRENT_WORLD_OBJECT_RE.search(clause)
        if not terminal or not object_match:
            continue
        prefix = clause[:terminal.start()]
        modality = "conditional" if _FUTURE_OR_CONDITIONAL_RE.search(prefix) else "asserted_current"
        predicate_tokens = re.findall(
            r"\b(?:active|activated|complete|completed|finished|deployed|published|"
            r"uploaded|attached|sent|posted|shared|delivered|archived|captured|stored|restored|"
            r"blocked|isolated|disabled|enabled|redirected|shifted|verified|"
            r"validated|reviewed|matched|secured|immutable|executed|healthy|stable|green)\b",
            terminal.group(0),
            flags=re.IGNORECASE,
        )
        object_text = object_match.group(0).casefold()
        propositions.append({
            "clause": clause,
            "object": object_text,
            "predicate": (predicate_tokens[-1].casefold() if predicate_tokens else "terminal"),
            "modality": modality,
            "kind": (
                "artifact"
                if re.search(r"\b(?:attachment|email|file|document|report|log)\b", object_text)
                else "action"
            ),
        })
    return propositions

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
    r"require(?:s|d)?\s+(?:us\s+|them\s+|him\s+|her\s+|you\s+)?to|"
    r"need\s+confirmation\s+that)\b",
    flags=re.IGNORECASE,
)

_EVIDENCE_ATTRIBUTION_RE = re.compile(
    r"\b(?:based\s+on\s+(?:the\s+)?(?:(?:current|available|present|existing)\s+)?"
    r"(?:evidence|metrics|logs|data|record)|"
    r"according\s+to\s+(?:the\s+)?(?:metrics|logs|data|report)|"
    r"(?:metrics|monitoring|logs|data|the\s+report)\s+"
    r"(?:show|shows|showed|confirm|confirms|confirmed|indicate|indicates|indicated)|"
    r"reported\s+(?:complete|completed|restored|recovered|healthy)|"
    r"showing\s+(?:no\s+)?(?:anomalies|errors|failures))\b",
    flags=re.IGNORECASE,
)

_EVIDENCE_STATUS_ASSERTION_RE = re.compile(
    r"\b(?:start(?:ed)?|initiated|begun|complete|completed|completion|"
    r"recover(?:ed|y)?|restor(?:ed|ation)|"
    r"verified|verification|validated|healthy|stable|normal\s+ranges?|"
    r"back\s+up|degraded|above\s+\d+|below\s+\d+|no\s+(?:errors|failures|anomalies))\b",
    flags=re.IGNORECASE,
)

_EVIDENCE_UNCERTAINTY_RE = re.compile(
    r"\b(?:cannot|can't|do\s+not|don't|not\s+enough|insufficient|unverified|"
    r"pending|defer|uncertain|no\s+basis|no\s+(?:confirmed|verified|verification))\b",
    flags=re.IGNORECASE,
)


def _question_only_evidence_claim(text: str, public_context: str) -> bool:
    """Reject treating questions as if they were affirmative evidence.

    In autonomous dialogue a model sometimes answers "is rollback complete?"
    with "rollback was reported complete" even though nobody supplied that
    fact.  If a response attributes a conclusion to evidence but the public
    record contains no declarative evidence statement, it must remain a
    question or conditional proposal.
    """
    supported_rows: list[tuple[str, set[str]]] = []
    for row in (public_context or "").splitlines():
        cleaned = " ".join(row.split()).strip()
        if not cleaned or "?" in cleaned:
            continue
        # Requests for confirmation describe an information gap, not evidence.
        if re.search(
            r"\b(?:need|request|ask|await|pending|could\s+you|please)\b",
            cleaned,
            flags=re.IGNORECASE,
        ):
            continue
        if _EVIDENCE_UNCERTAINTY_RE.search(cleaned):
            continue
        if not (
            _EVIDENCE_STATUS_ASSERTION_RE.search(cleaned)
            or _EVIDENCE_ATTRIBUTION_RE.search(cleaned)
        ):
            continue
        supported_rows.append((
            cleaned,
            {match.casefold() for match in _CURRENT_WORLD_OBJECT_RE.findall(cleaned)},
        ))
    # Evaluate each clause independently.  A later disclaimer such as "we
    # cannot confirm recovery" must not immunize an earlier invented positive
    # assertion such as "the rollback was started" in the same response.
    for clause in re.split(
        r"(?<=[.!?])\s+|;\s*|,\s+(?=(?:but|however|although|while|because)\b)",
        text,
        flags=re.IGNORECASE,
    ):
        if not _EVIDENCE_ATTRIBUTION_RE.search(clause):
            continue
        if _EVIDENCE_UNCERTAINTY_RE.search(clause):
            continue
        if not _EVIDENCE_STATUS_ASSERTION_RE.search(clause):
            continue
        claim_objects = {
            match.casefold() for match in _CURRENT_WORLD_OBJECT_RE.findall(clause)
        }
        if any(
            (not claim_objects) or bool(claim_objects & support_objects)
            for _, support_objects in supported_rows
        ):
            continue
        return True
    return False

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
    if any(
        row["kind"] == "artifact" and row["modality"] == "asserted_current"
        for row in normalized_public_propositions(text)
    ):
        return True
    sentences = re.split(r"(?<=[.!?])\s+|[;]\s*", text)
    for sentence in sentences:
        if _TERSE_TERMINAL_RE.search(sentence) and re.search(
            r"\b(?:log|attachment|email|file|document|report)\b",
            sentence,
            flags=re.IGNORECASE,
        ):
            return True
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


_LIVE_EVIDENTIARY_ARTIFACT_RE = re.compile(
    r"\b(?:performance|inspection|forensic|audit|test|survey|incident|financial|"
    r"capacity|compliance|quality|status)\s+(?:report|certificate|dashboard|log)|"
    r"\b(?:signed\s+contract|acceptance\s+certificate|invoice|bank\s+details|"
    r"memory\s+dump|snapshot|measurement(?:s)?|test\s+result(?:s)?)\b",
    flags=re.IGNORECASE,
)


def unsupported_live_evidentiary_artifact_reason(
    content: str, *, validated_intent: dict | None = None,
) -> str | None:
    """Require engine evidence for a purported live evidentiary artifact.

    A participant may compose a proposal, checklist or draft inline. A report,
    certificate, invoice, log or measurement presented as already available is
    evidence about the simulated world and therefore needs a registered tool
    result rather than model-authored prose alone.
    """
    text = " ".join((content or "").split()).strip()
    if not text or not _LIVE_EVIDENTIARY_ARTIFACT_RE.search(text):
        return None
    if not re.search(
        r"\b(?:here\s+(?:is|are)|please\s+find\s+below|"
        r"i(?:'ve| have)\s+(?:located|provided)|"
        r"we(?:'ve| have)\s+(?:located|provided)|the\s+following)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return None
    intent = validated_intent or {}
    tool_grounded = (
        str(intent.get("evidence_source") or "") == "simulated_tool_result"
        and bool(str(intent.get("tool_result_id") or "").strip())
        and str(intent.get("validation") or "") == "accepted"
    )
    return None if tool_grounded else "live_evidentiary_artifact_requires_simulated_tool_result"


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


def terminal_current_world_action_reason(
    content: str, *, validated_intent: dict | None = None,
) -> str | None:
    """Reject unsupported completed side effects in the visible transcript.

    The check is deliberately quote-driven.  A model cannot evade it by
    calling an action a ``statement`` or ``fact``.  A terminal operational
    claim is publishable only when intent validation has already matched it to
    a registered simulated tool result.
    """
    intent = validated_intent or {}
    if (
        str(intent.get("simulation_scope") or "") == "retrospective"
        and retrospective_claim_grounded(content)
    ):
        return None
    tool_grounded = (
        str(intent.get("evidence_source") or "") == "simulated_tool_result"
        and bool(str(intent.get("tool_result_id") or "").strip())
        and str(intent.get("validation") or "") == "accepted"
        and str(intent.get("transition") or "") in {"submitted", "verified", "accepted"}
    )
    if tool_grounded:
        return None
    if any(
        row["modality"] == "asserted_current"
        for row in normalized_public_propositions(content)
    ):
        return "current_world_completion_requires_simulated_tool_result"
    return None


def retain_safe_public_clauses(
    content: str, *, validated_intent: dict | None = None,
) -> str:
    """Keep safe clauses when only part of a draft invents a live result.

    This bounded repair never writes replacement facts.  It removes the
    offending clause and retains complete public clauses that independently
    pass the current-world check, avoiding a second whole-message paraphrase.
    """
    clauses = re.split(r"(?<=[.!?])\s+|(?<=;)\s*", " ".join((content or "").split()))
    kept = [
        clause.strip()
        for clause in clauses
        if clause.strip()
        and not terminal_current_world_action_reason(
            clause, validated_intent=validated_intent
        )
        and not unsupported_evidence_reason(
            clause,
            allow_retrospective_artifact_claims=(
                str((validated_intent or {}).get("simulation_scope") or "")
                == "retrospective"
                and retrospective_claim_grounded(clause)
            ),
        )
    ]
    return " ".join(kept).strip()


def speech_rejection_reason(
    content: str, *, active_plan_text: str = "", public_context: str = "",
    validated_intent: dict | None = None,
    protected_secrets: list[str] | None = None,
    public_draft_text: str = "",
    participant_aliases: dict[str, list[str] | tuple[str, ...]] | None = None,
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
    assignment_reason = unregistered_participant_assignment_reason(
        text,
        participant_aliases=participant_aliases,
        validated_intent=intent,
    )
    if assignment_reason:
        return assignment_reason

    live_artifact_reason = unsupported_live_evidentiary_artifact_reason(
        text, validated_intent=intent
    )
    if live_artifact_reason:
        return live_artifact_reason
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
        str(intent.get("simulation_scope") or "discussion") != "retrospective"
        and _question_only_evidence_claim(text, public_context)
    ):
        return "question_treated_as_public_evidence"
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

    current_world_reason = terminal_current_world_action_reason(
        text, validated_intent=intent
    )
    if current_world_reason:
        return current_world_reason

    if text[-1] not in ".!?\"'”’":
        return "truncated"
    return None


def player_speech_rejection_reason(
    content: str, *, public_context: str = "", validated_intent: dict | None = None,
    participant_aliases: dict[str, list[str] | tuple[str, ...]] | None = None,
) -> str | None:
    """Reject malformed structured output accidentally exposed as player dialogue."""
    text = (content or "").strip()
    if text.startswith(("{", "[", "```")):
        return "structured_output"
    lowered = text.casefold()
    if '"content"' in lowered and '"intent"' in lowered:
        return "structured_output"
    return speech_rejection_reason(
        text, public_context=public_context, validated_intent=validated_intent,
        participant_aliases=participant_aliases,
    )
