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


def initial_public_ledger() -> dict[str, Any]:
    return {
        "schema": "roommind-public-world-ledger-v1",
        "version": LEDGER_VERSION,
        "simulation_clock": {"turn": 0, "tick": 0},
        "entities": {},
        "events": [],
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
    }


def _normalize_actor(value: Any) -> str:
    return "user" if str(value or "") == "player" else str(value or "")


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
    if kind == "action" and field and transition in {
        "in_progress", "submitted", "verified", "accepted",
    }:
        if field not in set(authority.get("can_execute") or []):
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
) -> dict[str, Any]:
    """Validate an agent's proposed public-world transition before wording it.

    External side effects cannot occur inside a text simulation. A completed
    action therefore needs an in-session scope and concrete inline result; an
    artifact submission needs its actual inline contents. Unsupported terminal
    claims are safely downgraded to commitments and remain auditable.
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
    actor_id = _normalize_actor(
        character.get("character_id") if isinstance(character, dict)
        else getattr(character, "character_id", "")
    )
    rejection = initial_rejection
    commit_allowed = True

    authority = (
        character.get("authority") if isinstance(character, dict)
        else getattr(character, "authority", None)
    ) or {}
    field = str(raw.get("field") or "")[:96]
    if kind == "action" and not field:
        executable = [str(value) for value in (authority.get("can_execute") or []) if value]
        subject_tokens = set(re.findall(r"[\w]+", subject.casefold().replace("-", "_")))
        matching = [
            value for value in executable
            if subject_tokens.intersection(value.casefold().split("_"))
        ]
        if len(matching) == 1:
            field = matching[0]

    if not _authority_allows(character, {**raw, "field": field, "transition": transition}):
        rejection = "actor_lacks_transition_authority"
        transition = "proposed"
    elif kind == "artifact" and transition in {"submitted", "verified", "accepted"} and not inline_content:
        rejection = "artifact_terminal_transition_requires_inline_content"
        transition = "committed"
    elif kind == "action" and transition in {"submitted", "verified", "accepted"}:
        if simulation_scope != "in_session" or not inline_content:
            rejection = "external_action_cannot_complete_without_in_session_result"
            transition = "committed"
    elif kind == "verification" and transition in {"verified", "accepted"} and not inline_content:
        rejection = "verification_requires_public_inline_evidence"
        transition = "proposed"

    # Material entities advance monotonically. Concrete in-session work may be
    # submitted immediately, but it cannot also verify and accept itself in the
    # same event. A later authorized participant must perform those transitions.
    if state is not None and kind in {"artifact", "action", "verification"}:
        ledger = ensure_public_ledger(state)
        subject_key = "_".join(subject.casefold().split())[:96]
        prior = (ledger.get("entities") or {}).get(f"{kind}:{subject_key}") or {}
        prior_lifecycle = str(prior.get("lifecycle") or "")
        rank = {name: index for index, name in enumerate(LIFECYCLE[:6])}
        if transition in {"submitted", "verified", "accepted"}:
            requested_rank = rank.get(transition, 0)
            prior_rank = rank.get(prior_lifecycle, -1)
            if prior_lifecycle and requested_rank <= prior_rank:
                rejection = rejection or "material_lifecycle_cannot_regress_or_repeat"
                transition = prior_lifecycle
                commit_allowed = False
            else:
                next_rank = prior_rank + 1 if prior_lifecycle else rank["submitted"]
                applied = LIFECYCLE[max(0, min(requested_rank, next_rank))]
                if applied != transition:
                    rejection = rejection or "material_lifecycle_requires_separate_transitions"
                    transition = applied

    return {
        "kind": kind,
        "subject": subject,
        "transition": transition,
        "actor_id": actor_id,
        "target_id": _normalize_actor(raw.get("target_id")),
        "field": field,
        "inline_content": inline_content,
        "simulation_scope": simulation_scope,
        "turn_id": int(turn_id),
        "validation": "downgraded" if rejection else "accepted",
        "validation_reason": rejection,
        "requested_transition": requested_transition,
        "commit_allowed": commit_allowed,
    }


def commit_public_intent(
    state: dict[str, Any], *, intent: dict[str, Any], public_quote: str, tick: int = 0
) -> dict[str, Any]:
    """Commit one prevalidated, publicly spoken transition to the ledger."""
    ledger = ensure_public_ledger(state)
    entities = ledger.setdefault("entities", {})
    events = ledger.setdefault("events", [])
    rejections = ledger.setdefault("rejections", [])
    subject_key = "_".join(str(intent.get("subject") or "unspecified").casefold().split())[:96]
    entity_id = f"{intent.get('kind')}:{subject_key}"
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
        "inline_content": str(intent.get("inline_content") or ""),
        "public_evidence": {"quote": str(public_quote or "")[:1000]},
        "provenance": "prevalidated_agent_intent",
        "validation": str(intent.get("validation") or "accepted"),
        "validation_reason": str(intent.get("validation_reason") or ""),
        "validated_intent": deepcopy(intent),
        "clock_valid": event_clock_tuple >= prior_clock_tuple,
    }
    events.append(event)
    if event["validation_reason"]:
        rejections.append({
            "event_id": event_id,
            "requested_transition": str(intent.get("requested_transition") or ""),
            "applied_transition": transition,
            "reason": event["validation_reason"],
        })
    entities[entity_id] = {
        **prior,
        "entity_id": entity_id,
        "kind": event["entity_kind"],
        "subject": event["subject"],
        "lifecycle": transition,
        "owner_id": event["actor_id"],
        "target_id": event["target_id"],
        "field": event["field"],
        "inline_content": event["inline_content"] or prior.get("inline_content", ""),
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
        if str(entity.get("kind") or "") != kind:
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
