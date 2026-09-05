"""Authoritative public-world ledger for G3 simulations.

The ledger is the shared source of truth for public facts and lifecycle state.
Private agent memories may interpret the meeting differently, but neither speech
nor an LLM-based extractor can directly manufacture a completed public action.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any


LEDGER_VERSION = 1
LIFECYCLE = (
    "proposed", "committed", "in_progress", "submitted", "verified",
    "accepted", "rejected", "blocked",
)
TERMINAL_LIFECYCLE = {"accepted", "rejected"}
MATERIAL_LIFECYCLE = {"submitted", "verified", "accepted", "rejected", "blocked"}
MATERIAL_ENTITY_KINDS = {"artifact", "action", "verification"}
CANONICAL_WORK_KINDS = MATERIAL_ENTITY_KINDS | {
    "issue", "proposal", "decision", "commitment", "schedule", "handoff", "outcome",
}
SIMULATION_SCOPES = {"discussion", "in_session", "external", "retrospective"}
EVIDENCE_SOURCES = {
    "scenario_seed", "public_statement", "simulated_tool_result", "external_followup",
}
_SUBJECT_QUALIFIERS = {
    "a", "an", "and", "the", "for", "of", "to", "with", "draft",
    "details", "detail", "summary", "update", "calculation", "calculate",
}


def initial_public_ledger() -> dict[str, Any]:
    return {
        "schema": "roommind-public-world-ledger-v1",
        "version": LEDGER_VERSION,
        "simulation_clock": {"turn": 0, "tick": 0},
        "entities": {},
        "events": [],
        "tool_results": {},
        "rejections": [],
        "event_counter": 0,
    }


def ensure_public_ledger(state: dict[str, Any]) -> dict[str, Any]:
    ledger = state.get("public_ledger")
    if not isinstance(ledger, dict) or ledger.get("schema") != "roommind-public-world-ledger-v1":
        ledger = initial_public_ledger()
        state["public_ledger"] = ledger
    ledger.setdefault("simulation_clock", {"turn": 0, "tick": 0})
    ledger.setdefault("entities", {})
    ledger.setdefault("events", [])
    ledger.setdefault("tool_results", {})
    ledger.setdefault("rejections", [])
    ledger.setdefault("event_counter", max([
        int(str(row.get("event_id") or "0").removeprefix("ple-") or 0)
        for row in ledger.get("events") or [] if isinstance(row, dict)
    ] or [0]))
    return ledger


def public_ledger_view(state: dict[str, Any], *, event_limit: int = 300) -> dict[str, Any]:
    ledger = ensure_public_ledger(state)
    return {
        "schema": ledger["schema"],
        "version": ledger.get("version", LEDGER_VERSION),
        "simulation_clock": deepcopy(ledger.get("simulation_clock") or {}),
        "entities": deepcopy(ledger.get("entities") or {}),
        "recent_events": deepcopy((ledger.get("events") or [])[-event_limit:]),
        "recent_rejections": deepcopy((ledger.get("rejections") or [])[-10:]),
        "tool_results": deepcopy(ledger.get("tool_results") or {}),
    }


def record_simulated_tool_result(
    state: dict[str, Any], *, result_id: str, actor_id: str, field: str,
    inline_content: str, turn_id: int,
) -> dict[str, Any]:
    """Register a trusted simulation-engine result before an agent cites it."""
    stable_id = str(result_id or "").strip()[:160]
    content = str(inline_content or "").strip()[:4000]
    if not stable_id or not content:
        raise ValueError("A simulated tool result requires an id and public content")
    result = {
        "result_id": stable_id,
        "actor_id": _normalize_actor(actor_id),
        "field": str(field or "")[:96],
        "inline_content": content,
        "turn_id": int(turn_id),
    }
    ensure_public_ledger(state).setdefault("tool_results", {})[stable_id] = result
    return result


def _normalize_actor(value: Any) -> str:
    return "user" if str(value or "") == "player" else str(value or "")


def _subject_key(value: Any) -> str:
    words = [
        token for token in re.findall(r"[\w-]+", str(value or "").casefold())
        if token and token not in _SUBJECT_QUALIFIERS
    ]
    return "_".join(words[:12])[:96] or "unspecified"


def _identity_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    # Unlike entity ids, evidence matching must inspect the whole public quote.
    # Reusing the 12-token ``_subject_key`` silently discarded late but highly
    # material phrases such as "customer-communication owner".
    for token in re.findall(r"[\w]+", str(value or "").casefold().replace("_", " ").replace("-", " ")):
        if token in _SUBJECT_QUALIFIERS:
            continue
        if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
            token = token[:-1]
        if token:
            tokens.add(token)
    return tokens


def _canonical_entity_id(
    ledger: dict[str, Any], *, kind: str, subject: str, field: str
) -> str:
    """Resolve model wording to a stable public entity identity.

    Configured fields are the strongest identity. Material work without a
    field shares one ``work:`` namespace across action/artifact/verification,
    so a later verification can advance the thing that was submitted. Obvious
    subject aliases are merged deterministically before a new entity is made.
    """
    if field:
        return f"field:{field}"
    key = _subject_key(subject)
    if kind not in CANONICAL_WORK_KINDS:
        return f"{kind}:{key}"
    wanted = _identity_tokens(key)
    best_id = ""
    best_score = 0.0
    for entity_id, entity in (ledger.get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        existing_kind = str(entity.get("kind") or "")
        if kind in MATERIAL_ENTITY_KINDS:
            if not str(entity_id).startswith("work:"):
                continue
        elif existing_kind not in CANONICAL_WORK_KINDS:
            continue
        aliases = [str(entity.get("subject") or ""), *(entity.get("aliases") or [])]
        for alias in aliases:
            existing = _identity_tokens(alias)
            overlap = wanted.intersection(existing)
            score = len(overlap) / len(wanted.union(existing)) if wanted and existing else 0.0
            subset = min(len(wanted), len(existing)) >= 2 and (
                wanted <= existing or existing <= wanted
            )
            if (score >= 0.67 or subset) and score > best_score:
                best_id, best_score = str(entity_id), score
    if best_id:
        return best_id
    return f"work:{key}" if kind in MATERIAL_ENTITY_KINDS else f"{kind}:{key}"


def _authority_allows(character: Any, intent: dict[str, Any]) -> bool:
    transition = str(intent.get("transition") or "proposed")
    field = str(intent.get("field") or "")
    kind = str(intent.get("kind") or "statement")
    authority = (
        character.get("authority") if isinstance(character, dict)
        else getattr(character, "authority", None)
    ) or {}
    if field and transition not in {"proposed", "rejected", "blocked"}:
        forbidden = set(authority.get("cannot_commit") or []) | set(authority.get("cannot_confirm") or [])
        if field in forbidden:
            return False
    if kind == "action" and transition in {"in_progress", "submitted", "verified", "accepted"}:
        if not field or field not in set(authority.get("can_execute") or []):
            return False
    if kind == "artifact" and transition in {"submitted", "verified", "accepted"}:
        artifact_authority = (
            set(authority.get("can_execute") or [])
            | set(authority.get("can_confirm") or [])
            | set(authority.get("can_provide") or [])
        )
        if not field or field not in artifact_authority:
            return False
    if kind == "verification" and transition in {"verified", "accepted"}:
        if not field or field not in set(authority.get("can_confirm") or []):
            return False
    if transition == "proposed" and field and authority.get("can_propose") is not None:
        return field in set(authority.get("can_propose") or [])
    if transition in {"accepted", "verified"} and field:
        return field in set(authority.get("can_confirm") or [])
    if transition == "accepted" and not field:
        return bool(authority.get("can_approve") or authority.get("can_confirm"))
    return True


def validate_public_intent(
    *, character: Any, intent: dict[str, Any] | None, turn_id: int,
    state: dict[str, Any] | None = None,
    allow_retrospective: bool = False,
) -> dict[str, Any]:
    """Validate an agent's proposed public-world transition before wording it.

    External side effects cannot occur inside a text simulation. A completed
    action therefore needs an in-session scope plus a trusted, pre-registered
    simulated-tool result; an artifact submission needs its actual inline
    contents. Unsupported terminal claims are safely downgraded to commitments
    and remain auditable.
    """
    raw = dict(intent or {})
    kind = str(raw.get("kind") or "statement").lower()
    initial_rejection = ""
    if kind not in {
        "statement", "fact", "proposal", "decision", "commitment", "action",
        "artifact", "verification", "schedule", "issue", "outcome", "handoff",
    }:
        kind = "statement"
        initial_rejection = "invalid_intent_kind"
    requested_transition = str(raw.get("transition") or "proposed").lower()
    transition = requested_transition
    if transition not in LIFECYCLE:
        transition = "proposed"
        initial_rejection = initial_rejection or "invalid_lifecycle_transition"
    subject = " ".join(str(raw.get("subject") or kind).split())[:240]
    inline_content = str(raw.get("inline_content") or "").strip()[:4000]
    simulation_scope = str(raw.get("simulation_scope") or "discussion").lower()
    if simulation_scope not in SIMULATION_SCOPES:
        simulation_scope = "discussion"
        initial_rejection = initial_rejection or "invalid_simulation_scope"
    elif simulation_scope == "retrospective" and not allow_retrospective:
        # The model cannot self-select a weaker evidence regime in a live
        # simulation. Retrospective claims are enabled only by scenario policy.
        simulation_scope = "discussion"
        initial_rejection = initial_rejection or "retrospective_scope_not_enabled"
    actor_id = _normalize_actor(
        character.get("character_id") if isinstance(character, dict)
        else getattr(character, "character_id", "")
    )
    rejection = initial_rejection
    commit_allowed = True
    field = str(raw.get("field") or "")[:96]
    target_id = _normalize_actor(raw.get("target_id"))
    evidence_source = str(raw.get("evidence_source") or "").lower()
    if not evidence_source:
        evidence_source = (
            "external_followup" if simulation_scope == "external" and transition == "committed"
            else "public_statement"
        )
    if evidence_source not in EVIDENCE_SOURCES:
        evidence_source = "public_statement"
        rejection = rejection or "invalid_evidence_source"
    tool_result_id = str(raw.get("tool_result_id") or "").strip()[:160]
    tool_result_registered = False
    if evidence_source == "scenario_seed":
        # Scenario facts enter through initialization, never through an agent's
        # self-authored public intent.
        evidence_source = "public_statement"
        rejection = rejection or "agent_cannot_create_scenario_seed_evidence"
    if evidence_source == "simulated_tool_result" and not tool_result_id:
        rejection = rejection or "simulated_tool_result_requires_id"
    if evidence_source == "simulated_tool_result" and state is not None and tool_result_id:
        registered_result = (
            ensure_public_ledger(state).get("tool_results") or {}
        ).get(tool_result_id)
        if (
            not isinstance(registered_result, dict)
            or _normalize_actor(registered_result.get("actor_id")) != actor_id
            or (field and str(registered_result.get("field") or "") != field)
            or str(registered_result.get("inline_content") or "").strip() != inline_content
        ):
            rejection = rejection or "unregistered_simulated_tool_result"
        else:
            tool_result_registered = True

    authority = (
        character.get("authority") if isinstance(character, dict)
        else getattr(character, "authority", None)
    ) or {}
    raw_value = raw.get("value")
    value = raw_value if isinstance(raw_value, (str, int, float, bool)) else None
    if raw_value is not None and value is None:
        rejection = rejection or "invalid_public_field_value"
    if kind in MATERIAL_ENTITY_KINDS and not field:
        capability_values = list(authority.get("can_execute") or [])
        if kind == "artifact":
            capability_values.extend(authority.get("can_provide") or [])
            capability_values.extend(authority.get("can_confirm") or [])
        elif kind == "verification":
            capability_values.extend(authority.get("can_verify") or [])
            capability_values.extend(authority.get("can_confirm") or [])
        executable = list(dict.fromkeys(
            str(value) for value in capability_values if value and str(value) != "*"
        ))
        subject_tokens = set(re.findall(r"[\w]+", subject.casefold().replace("-", "_")))
        matching = [
            value for value in executable
            if subject_tokens.intersection(value.casefold().split("_"))
        ]
        if len(matching) == 1:
            field = matching[0]

    if state is not None and field and target_id and kind == "handoff":
        matching_obligations = [
            row for row in (
                ((state.get("obligation_graph") or {}).get("obligations") or {}).values()
            )
            if isinstance(row, dict)
            and str(row.get("field") or "") == field
            and row.get("required_now") is True
        ]
        capable_targets = {
            str(value)
            for row in matching_obligations
            for value in (row.get("authorized_confirmer_ids") or [])
        }
        if capable_targets and target_id not in capable_targets:
            rejection = rejection or "target_lacks_obligation_authority"
            transition = "proposed"
            commit_allowed = False

    if simulation_scope == "retrospective":
        # Historical experience is a public claim, not a live world action.
        # Preserve the subject and evidence without completing current work.
        if kind in MATERIAL_ENTITY_KINDS or transition != "proposed":
            rejection = rejection or "retrospective_claim_not_live_transition"
        kind = "fact"
        transition = "proposed"
    elif not _authority_allows(character, {**raw, "kind": kind, "field": field, "transition": transition}):
        rejection = rejection or "actor_lacks_transition_authority"
        transition = "proposed"
    elif kind == "artifact" and transition in {"submitted", "verified", "accepted"} and not inline_content:
        rejection = rejection or "artifact_terminal_transition_requires_inline_content"
        transition = "committed"
    elif kind == "action" and transition in {"submitted", "verified", "accepted"}:
        if (
            simulation_scope != "in_session"
            or not inline_content
            or evidence_source != "simulated_tool_result"
            or not tool_result_id
            or not tool_result_registered
        ):
            rejection = rejection or "action_completion_requires_simulated_tool_result"
            transition = "committed"
    elif kind == "verification" and transition in {"verified", "accepted"} and not inline_content:
        rejection = rejection or "verification_requires_public_inline_evidence"
        transition = "proposed"
    if field and transition in {"verified", "accepted"} and value is None:
        rejection = rejection or "field_terminal_transition_requires_value"
        transition = "proposed"

    # Material entities advance monotonically. Concrete in-session work may be
    # submitted immediately, but it cannot also verify and accept itself in the
    # same event. A later authorized participant must perform those transitions.
    entity_id = ""
    if state is not None:
        ledger = ensure_public_ledger(state)
        entity_id = _canonical_entity_id(
            ledger, kind=kind, subject=subject, field=field
        )
    if state is not None and kind in MATERIAL_ENTITY_KINDS:
        prior = (ledger.get("entities") or {}).get(entity_id) or {}
        prior_lifecycle = str(prior.get("lifecycle") or "")
        rank = {name: index for index, name in enumerate(LIFECYCLE[:6])}
        requested_rank = rank.get(transition, -1)
        prior_rank = rank.get(prior_lifecycle, -1)
        if (
            prior_lifecycle in rank and transition in rank
            and requested_rank <= prior_rank
        ):
            rejection = rejection or "material_lifecycle_cannot_regress_or_repeat"
            transition = prior_lifecycle
            commit_allowed = False
        elif transition in {"submitted", "verified", "accepted"}:
            if not prior_lifecycle or requested_rank > prior_rank:
                next_rank = prior_rank + 1 if prior_lifecycle else rank["submitted"]
                applied = LIFECYCLE[max(0, min(requested_rank, next_rank))]
                if applied != transition:
                    rejection = rejection or "material_lifecycle_requires_separate_transitions"
                    transition = applied
    elif state is not None and field:
        # A later statement may discuss or challenge an accepted field, but it
        # cannot silently move the authoritative lifecycle backwards. Explicit
        # rejected/blocked transitions remain available for a real reversal.
        prior = (ledger.get("entities") or {}).get(entity_id) or {}
        prior_lifecycle = str(prior.get("lifecycle") or "")
        prior_value = prior.get("value")
        prior_actors = (prior.get("actors_by_transition") or {}).get(transition) or []
        if prior_lifecycle == transition and actor_id in {
            str(actor) for actor in prior_actors
        }:
            rejection = rejection or "field_lifecycle_repeat_by_actor"
            commit_allowed = False
        if (
            prior_lifecycle == "accepted" and transition == "accepted"
            and prior_value is not None and value != prior_value
        ):
            rejection = rejection or "accepted_field_value_conflict"
            transition = "proposed"
            commit_allowed = False
        rank = {name: index for index, name in enumerate(LIFECYCLE[:6])}
        if (
            prior_lifecycle in rank and transition in rank
            and rank[transition] < rank[prior_lifecycle]
        ):
            rejection = rejection or "field_lifecycle_cannot_regress"
            transition = prior_lifecycle
            commit_allowed = False
    elif state is not None and kind in CANONICAL_WORK_KINDS:
        prior = (ledger.get("entities") or {}).get(entity_id) or {}
        prior_actors = (prior.get("actors_by_transition") or {}).get(transition) or []
        if str(prior.get("lifecycle") or "") == transition and actor_id in {
            str(value) for value in prior_actors
        }:
            rejection = rejection or "nonmaterial_lifecycle_repeat_by_actor"
            commit_allowed = False

    return {
        "kind": kind,
        "subject": subject,
        "transition": transition,
        "actor_id": actor_id,
        "target_id": target_id,
        "field": field,
        "value": value,
        "inline_content": inline_content,
        "simulation_scope": simulation_scope,
        "evidence_source": evidence_source,
        "tool_result_id": tool_result_id,
        "turn_id": int(turn_id),
        "validation": "downgraded" if rejection else "accepted",
        "validation_reason": rejection,
        "requested_transition": requested_transition,
        "commit_allowed": commit_allowed,
        "entity_id": entity_id,
    }


_EXPLICIT_FIRST_PERSON_CONFIRMATION_RE = re.compile(
    r"\b(?:i|we)\s+(?:(?:can|hereby|now|fully|explicitly|formally)\s+)*"
    r"(?:confirm|accept|approve|agree(?:\s+to)?|endorse|sign\s+off(?:\s+on)?)\b|"
    r"\b(?:i|we)\s+consider\b[^.!?;]{0,120}\bcomplete\b",
    flags=re.IGNORECASE,
)
_CONDITIONAL_CONFIRMATION_RE = re.compile(
    r"\b(?:conditionally|subject\s+to|provided\s+that|assuming|pending|awaiting|"
    r"if|unless|once|when|before\s+(?:i|we)\s+(?:can|will))\b",
    flags=re.IGNORECASE,
)


def align_explicit_confirmation_intent(
    *, character: Any, intent: dict[str, Any] | None, public_quote: str,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Align an explicit authorized confirmation with its structured intent.

    Structured-output models occasionally label a plainly spoken confirmation
    as a generic ``statement/committed`` event.  The speech boundary then
    correctly rejects the stronger public words, silencing the role that was
    supposed to close the field.  This deterministic adapter upgrades only an
    unconditional first-person confirmation of an already-known field value,
    and only when the speaker has configured confirmation authority.  It never
    invents a value or infers agreement from a question, promise, or condition.
    """
    raw = dict(intent or {})
    variables = (state or {}).get("variables") or {}
    if not variables:
        return raw
    authority = (
        character.get("authority") if isinstance(character, dict)
        else getattr(character, "authority", None)
    ) or {}
    confirmable = {str(value) for value in (authority.get("can_confirm") or [])}
    if not confirmable:
        return raw

    clauses = [
        clause.strip()
        for clause in re.split(r"(?<=[.!?])\s+|;\s*", " ".join((public_quote or "").split()))
        if clause.strip() and not clause.strip().endswith("?")
    ]
    requested_field = str(raw.get("field") or "").strip()
    subject = str(raw.get("subject") or "").casefold().replace("_", " ")
    candidates = [
        field for field in variables
        if field in confirmable
        and (
            field == requested_field
            or field.casefold().replace("_", " ") in subject
            or subject in field.casefold().replace("_", " ")
        )
    ]
    if not candidates and requested_field in variables and requested_field in confirmable:
        candidates = [requested_field]
    if len(candidates) != 1:
        return raw
    field = candidates[0]
    field_tokens = {
        token for token in re.findall(r"[a-z0-9]+", field.casefold().replace("_", " "))
        if len(token) >= 3 and token not in {"the", "and", "complete", "completed"}
    }
    confirming_clause = next((
        clause for clause in clauses
        if _EXPLICIT_FIRST_PERSON_CONFIRMATION_RE.search(clause)
        and not _CONDITIONAL_CONFIRMATION_RE.search(clause)
        and (
            field.casefold().replace("_", " ") in clause.casefold().replace("_", " ")
            or (
                field_tokens
                and len({
                    token for token in field_tokens
                    if re.search(rf"\b{re.escape(token)}\b", clause, flags=re.IGNORECASE)
                }) >= min(2, len(field_tokens))
            )
        )
    ), "")
    if not confirming_clause:
        return raw
    current = variables.get(field) or {}
    value = current.get("value")
    if value is None:
        return raw
    return {
        **raw,
        "kind": "decision",
        "field": field,
        "value": value,
        "transition": "accepted",
        "simulation_scope": "discussion",
        "evidence_source": "public_statement",
        "alignment": "explicit_authorized_confirmation",
    }


def ground_public_intent_in_quote(
    intent: dict[str, Any] | None, public_quote: str,
    *, actor_aliases: list[str] | None = None,
) -> dict[str, Any]:
    """Require a material structured intent to be stated in public speech.

    The structured intent is model output and therefore untrusted.  Authority
    and lifecycle validation alone cannot distinguish "please provide X" from
    "I have provided X".  This final commit-boundary check prevents requests,
    questions, and internal annotations from mutating the public world.
    """
    grounded = dict(intent or {})
    if not grounded or not grounded.get("commit_allowed", True):
        return grounded
    transition = str(grounded.get("transition") or "proposed")
    quote = " ".join(str(public_quote or "").casefold().split())
    if transition != "proposed" and (
        quote.rstrip().endswith("?")
        or re.search(r"\b(?:please|could\s+you|can\s+you|would\s+you)\b", quote)
    ):
        prior_reason = str(grounded.get("validation_reason") or "")
        grounded["commit_allowed"] = False
        grounded["validation"] = "rejected"
        grounded["validation_reason"] = ";".join(filter(None, [
            prior_reason, "public_quote_is_request_not_transition",
        ]))
        return grounded
    subject = str(grounded.get("subject") or "").strip()
    field = str(grounded.get("field") or "").strip()
    expected_tokens = _identity_tokens(f"{subject} {field}") if (subject or field) else set()
    quote_tokens = _identity_tokens(quote)
    if expected_tokens and not expected_tokens.intersection(quote_tokens):
        prior_reason = str(grounded.get("validation_reason") or "")
        grounded["commit_allowed"] = False
        grounded["validation"] = "rejected"
        grounded["validation_reason"] = ";".join(filter(None, [
            prior_reason, "public_quote_does_not_support_subject",
        ]))
        return grounded
    value = grounded.get("value")
    if value is not None:
        if isinstance(value, bool):
            pattern = (
                r"\b(?:accept|accepted|agree|agreed|approve|approved|confirm|confirmed|"
                r"adopt|adopted|enable|enabled|active|activated|complete|completed|identified|ready|"
                r"cover|covers|covered|satisfy|satisfies|satisfied|meet|meets|met|"
                r"no\s+(?:further|remaining|additional)\s+questions?|yes|true)\b"
                if value else
                r"\b(?:reject|rejected|decline|declined|not|no|false|inactive|disable|disabled)\b"
            )
            value_supported = bool(re.search(pattern, quote))
        elif isinstance(value, (int, float)):
            value_supported = bool(re.search(
                rf"(?<![\w.]){re.escape(f'{float(value):g}')}(?![\w.])", quote
            ))
        else:
            normalized_value = str(value).strip().casefold()
            normalized_aliases = {
                str(alias or "").strip().casefold()
                for alias in (actor_aliases or []) if str(alias or "").strip()
            }
            first_person_identity = (
                normalized_value in normalized_aliases
                and bool(re.search(
                    r"\b(?:i\s+am|i['’]m|i\s+confirm\s+(?:that\s+)?i['’]m)\b"
                    r"[^.!?;]{0,60}\b(?:owner|assignee|lead|responsible)\b",
                    quote,
                ))
            )
            value_tokens = {
                token for token in re.findall(r"[\w]+", normalized_value.replace("_", " "))
                if len(token) >= 3
            }
            value_supported = (
                normalized_value in quote
                or normalized_value.replace("_", " ") in quote
                or first_person_identity
                or bool(
                value_tokens.intersection(_identity_tokens(quote))
                )
            )
        if not value_supported:
            prior_reason = str(grounded.get("validation_reason") or "")
            grounded["commit_allowed"] = False
            grounded["validation"] = "rejected"
            grounded["validation_reason"] = ";".join(filter(None, [
                prior_reason, "public_quote_does_not_support_value",
            ]))
            return grounded
    if transition == "proposed":
        return grounded
    patterns = {
        "committed": r"\b(?:i|we)\s+(?:will|shall|commit(?:ted)?\s+to|agree\s+to|undertake\s+to|plan\s+to)\b",
        "in_progress": r"\b(?:i(?:'m| am)|we(?:'re| are))\s+(?:now\s+)?(?:working|reviewing|preparing|executing|implementing|verifying|investigating)\b|\b(?:has|have)\s+(?:started|begun)\b",
        "submitted": r"\b(?:i|we)\s+(?:have\s+|['’]ve\s+)?(?:provided|submitted|delivered|shared|presented)\b|\bhere\s+(?:is|are)\b",
        "verified": r"\b(?:i|we)\s+(?:have\s+|['’]ve\s+)?(?:verified|validated|confirmed|checked)\b|\b(?:is|are|was|were|has been|have been)\s+(?:verified|validated|confirmed)\b",
        "accepted": r"\b(?:i|we)\s+(?:(?:can|hereby|now|fully|explicitly|formally)\s+)*(?:accept|approve|agree|confirm)\b|\b(?:i|we)(?:(?:\s+will|['’]ll)|(?:(?:\s+am|['’]m)\s+(?:pleased|ready)\s+to))?\s+(?:now\s+)?(?:mark|record|declare)\b[^.!?;]{0,100}\b(?:complete|completed|approval|approved|decision|agreement)|\b(?:i|we)\b[^.!?;]{0,80}\b(?:have|['’]ve)\s+no\s+(?:further|remaining|additional)\s+questions?|\b(?:i|we)(?:(?:\s+will|['’]ll))?\s+consider\b[^.!?;]{0,100}\bcomplete|\b(?:i|we)(?:(?:\s+am|['’]m|\s+are|['’]re))\s+(?:officially\s+)?(?:setting|assigning|designating|appointing)\b|\b(?:i|we)\s+(?:officially\s+)?(?:set|assign|designate|appoint)\b|\bconfirmed\s*[-—:]|\b(?:cover|covers|covered|satisfy|satisfies|satisfied|meet|meets|met)\b[^.!?;]{0,100}\b(?:evidence|requirement|criteria|need)|\b(?:is|are|has been|have been)\s+(?:explicitly\s+|formally\s+)?(?:accepted|approved|agreed|confirmed|finalized)\b|^(?:lock|set|assign|designate|appoint|confirm|approve)\b",
        "rejected": r"\b(?:i|we)\s+(?:reject|decline|cannot accept|do not accept)\b|\b(?:is|are|has been|have been)\s+rejected\b",
        "blocked": r"\b(?:i|we)\s+(?:cannot|can't|am unable|are unable)\b|\b(?:is|are|remains?)\s+blocked\b",
    }
    pattern = patterns.get(transition)
    if pattern and not re.search(pattern, quote, flags=re.IGNORECASE):
        prior_reason = str(grounded.get("validation_reason") or "")
        grounded["commit_allowed"] = False
        grounded["validation"] = "rejected"
        grounded["validation_reason"] = ";".join(filter(None, [
            prior_reason, "public_quote_does_not_support_transition",
        ]))
    return grounded


def commit_public_intent(
    state: dict[str, Any], *, intent: dict[str, Any], public_quote: str, tick: int = 0
) -> dict[str, Any]:
    """Commit one prevalidated, publicly spoken transition to the ledger."""
    ledger = ensure_public_ledger(state)
    entities = ledger.setdefault("entities", {})
    events = ledger.setdefault("events", [])
    rejections = ledger.setdefault("rejections", [])
    entity_id = str(intent.get("entity_id") or "") or _canonical_entity_id(
        ledger,
        kind=str(intent.get("kind") or "statement"),
        subject=str(intent.get("subject") or "unspecified"),
        field=str(intent.get("field") or ""),
    )
    prior = dict(entities.get(entity_id) or {})
    transition = str(intent.get("transition") or "proposed")
    event_counter = int(ledger.get("event_counter") or 0) + 1
    ledger["event_counter"] = event_counter
    event_id = f"ple-{event_counter:05d}"
    prior_clock = ledger.get("simulation_clock") or {}
    prior_clock_tuple = (int(prior_clock.get("turn") or 0), int(prior_clock.get("tick") or 0))
    event_clock_tuple = (int(intent.get("turn_id") or 0), int(tick))
    event = {
        "event_id": event_id,
        "turn_id": int(intent.get("turn_id") or 0),
        "tick": int(tick),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "entity_id": entity_id,
        "entity_kind": str(intent.get("kind") or "statement"),
        "subject": str(intent.get("subject") or ""),
        "transition_from": prior.get("lifecycle"),
        "transition_to": transition,
        "actor_id": str(intent.get("actor_id") or ""),
        "target_id": str(intent.get("target_id") or ""),
        "field": str(intent.get("field") or ""),
        "value": intent.get("value"),
        "inline_content": str(intent.get("inline_content") or ""),
        "public_evidence": {"quote": str(public_quote or "")[:1000]},
        "provenance": str(intent.get("evidence_source") or "public_statement"),
        "tool_result_id": str(intent.get("tool_result_id") or ""),
        "validation": str(intent.get("validation") or "accepted"),
        "validation_reason": str(intent.get("validation_reason") or ""),
        "validated_intent": deepcopy(intent),
        "clock_valid": event_clock_tuple >= prior_clock_tuple,
        "committed": event_clock_tuple >= prior_clock_tuple,
    }
    if not event["clock_valid"]:
        rejections.append({
            "event_id": event_id,
            "requested_transition": str(intent.get("requested_transition") or ""),
            "applied_transition": "none",
            "reason": "simulation_clock_regression",
        })
        ledger["rejections"] = rejections[-100:]
        return event
    events.append(event)
    if event["validation_reason"]:
        rejections.append({
            "event_id": event_id,
            "requested_transition": str(intent.get("requested_transition") or ""),
            "applied_transition": transition,
            "reason": event["validation_reason"],
        })
    actors_by_transition = dict(prior.get("actors_by_transition") or {})
    actors = list(actors_by_transition.get(transition) or [])
    if event["actor_id"] and event["actor_id"] not in actors:
        actors.append(event["actor_id"])
    actors_by_transition[transition] = actors
    aliases = list(dict.fromkeys([
        *(prior.get("aliases") or []), event["subject"],
    ]))[-20:]
    entities[entity_id] = {
        **prior,
        "entity_id": entity_id,
        "kind": event["entity_kind"],
        "kinds": list(dict.fromkeys([*(prior.get("kinds") or []), event["entity_kind"]])),
        "subject": event["subject"],
        "aliases": aliases,
        "lifecycle": transition,
        "owner_id": event["actor_id"],
        "actors_by_transition": actors_by_transition,
        "target_id": event["target_id"],
        "field": event["field"],
        "value": event["value"] if event["value"] is not None else prior.get("value"),
        "inline_content": event["inline_content"] or prior.get("inline_content", ""),
        "evidence_source": event["provenance"],
        "tool_result_id": event["tool_result_id"] or prior.get("tool_result_id", ""),
        "last_event_id": event_id,
        "last_transition_turn": event["turn_id"],
    }
    if event["clock_valid"]:
        ledger["simulation_clock"] = {"turn": event["turn_id"], "tick": int(tick)}
    ledger["events"] = events[-300:]
    ledger["rejections"] = rejections[-100:]
    return event


def ledger_has_support(
    state: dict[str, Any], *, kind: str, subject: str, minimum: set[str],
    field: str = "",
) -> bool:
    ledger = ensure_public_ledger(state)
    wanted = {token for token in "_".join(subject.casefold().split()).split("_") if token}
    for entity in (ledger.get("entities") or {}).values():
        entity_kinds = {
            str(entity.get("kind") or ""),
            *(str(value) for value in (entity.get("kinds") or [])),
        }
        if kind not in entity_kinds:
            continue
        if field and str(entity.get("field") or "") == field and entity.get("lifecycle") in minimum:
            return True
        existing = set("_".join(str(entity.get("subject") or "").casefold().split()).split("_"))
        overlap = wanted.intersection(existing)
        similarity = len(overlap) / len(wanted.union(existing)) if wanted and existing else 0.0
        stable_match = len(overlap) >= 2 and (
            similarity >= 0.5 or wanted <= existing or existing <= wanted
        )
        if stable_match and entity.get("lifecycle") in minimum:
            return True
    return False
