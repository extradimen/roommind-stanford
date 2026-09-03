"""Schema-driven task-state extraction and deterministic completion evaluation."""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.models.db import CharacterTemplate
from app.telemetry import emit
from app.public_ledger import (
    MATERIAL_LIFECYCLE,
    commit_public_intent,
    ensure_public_ledger,
    ground_public_intent_in_quote,
    ledger_has_support,
    public_ledger_view,
    validate_public_intent,
)


ALLOWED_STATUSES = {"unknown", "proposed", "disputed", "confirmed", "rejected"}
ALLOWED_EVENT_TYPES = {
    "information_provided", "artifact_offered", "artifact_submitted",
    "artifact_reviewed", "action_committed", "action_completed", "decision",
    "blocker", "handoff", "schedule", "outcome",
}
ALLOWED_EVENT_STATUSES = {"proposed", "completed", "blocked", "rejected"}
TERMINAL_OUTCOMES = {"completed", "conditional", "deferred", "failed", "stalled"}
MATERIAL_WORK_STATUSES = {"submitted", "completed", "blocked", "rejected"}
_WORK_KEY_QUALIFIERS = {
    "a", "an", "and", "the", "for", "of", "to", "with",
    "draft", "details", "detail", "summary", "preparation", "update",
}
_CRITICAL_LANGUAGE_RE = re.compile(
    r"\b(?:need|required|must|blocking|blocker|cannot|can't|unable|depends? on|"
    r"prerequisite|before (?:we|i|the team) can|until)\b",
    flags=re.IGNORECASE,
)
logger = logging.getLogger(__name__)


def _subject_key(value: Any) -> str:
    words = re.findall(r"[\w\-]+", str(value or "").casefold(), flags=re.UNICODE)
    return "_".join(words[:12])[:96] or "unspecified"


def _work_key_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    for word in _subject_key(value).split("_"):
        if not word or word in _WORK_KEY_QUALIFIERS:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
            word = word[:-1]
        tokens.add(word)
    return tokens


def _resolve_work_item_key(raw: dict[str, Any], work_items: dict[str, Any]) -> tuple[str, str]:
    """Resolve a stable key and merge obvious wording variants deterministically."""
    subject = str(raw.get("subject") or raw.get("summary") or raw.get("event_type") or "unspecified").strip()[:240]
    supplied_key = raw.get("work_item_key")
    requested = _subject_key(supplied_key or subject)
    if requested in work_items:
        return requested, subject
    concise_words = [
        word for word in requested.split("_")
        if word and word not in _WORK_KEY_QUALIFIERS
    ]
    requested = "_".join(concise_words)[:96] or requested
    if requested in work_items:
        return requested, subject
    requested_tokens = _work_key_tokens(requested)
    best_key = ""
    best_score = 0.0
    for key in work_items:
        existing_tokens = _work_key_tokens(key)
        if not requested_tokens or not existing_tokens:
            continue
        overlap = requested_tokens & existing_tokens
        score = len(overlap) / len(requested_tokens | existing_tokens)
        subset_match = min(len(requested_tokens), len(existing_tokens)) >= 2 and (
            requested_tokens <= existing_tokens or existing_tokens <= requested_tokens
        )
        if (score >= 0.67 or subset_match) and score > best_score:
            best_key, best_score = key, score
    return (best_key or requested), subject


def _project_public_ledger(state: dict[str, Any]) -> None:
    """Project canonical ledger lifecycle into legacy read models.

    ``work_items`` remains for compatibility with scenario prompts and exports,
    but its material status is now a projection. A post-hoc language extractor
    can add descriptions; it cannot promote a ledger-backed item beyond the
    lifecycle the simulation actually executed.
    """
    work_items = state.setdefault("work_items", {})
    status_map = {
        "proposed": "proposed",
        "committed": "promised",
        "in_progress": "in_progress",
        "submitted": "submitted",
        "verified": "completed",
        "accepted": "completed",
        "rejected": "rejected",
        "blocked": "blocked",
    }
    for entity in (ensure_public_ledger(state).get("entities") or {}).values():
        if not isinstance(entity, dict) or entity.get("kind") not in {
            "action", "artifact", "verification", "decision", "commitment",
            "schedule", "issue", "outcome", "handoff",
        }:
            continue
        raw = {"subject": entity.get("subject"), "work_item_key": entity.get("subject")}
        key, subject = _resolve_work_item_key(raw, work_items)
        item = dict(work_items.get(key) or {})
        lifecycle = str(entity.get("lifecycle") or "proposed")
        item.update({
            "subject": item.get("subject") or subject,
            "kind": str(entity.get("kind") or item.get("kind") or "work_item"),
            "owner_id": str(entity.get("owner_id") or item.get("owner_id") or ""),
            "target_id": str(entity.get("target_id") or item.get("target_id") or ""),
            "ledger_entity_id": str(entity.get("entity_id") or ""),
            "ledger_lifecycle": lifecycle,
            "status": status_map.get(lifecycle, "proposed"),
            "last_transition_turn": int(entity.get("last_transition_turn") or 0),
        })
        if lifecycle == "committed":
            item.setdefault("promised_turn", int(entity.get("last_transition_turn") or 0))
        if lifecycle in {"submitted", "verified", "accepted", "rejected"}:
            item["resolved_turn"] = int(entity.get("last_transition_turn") or 0)
        work_items[key] = item
    state["work_items"] = work_items


def _project_field_ledger(
    task_config: dict[str, Any], state: dict[str, Any],
    characters: list[CharacterTemplate],
) -> None:
    """Project value-bearing canonical field events into the task read model."""
    schema = task_config.get("state_schema") or {}
    ledger = ensure_public_ledger(state)
    variables = state.setdefault("variables", {})
    character_confirmers: dict[str, set[str]] = {field: set() for field in schema}
    for character in characters:
        for field in (character.authority or {}).get("can_confirm", []):
            if field in character_confirmers:
                character_confirmers[field].add(character.character_id)
    for field, spec in schema.items():
        entity = (ledger.get("entities") or {}).get(f"field:{field}") or {}
        value, value_valid = _coerce_value(entity.get("value"), spec)
        lifecycle = str(entity.get("lifecycle") or "")
        if value is None or not value_valid or lifecycle not in {"proposed", "accepted"}:
            continue
        accepted_by = list(dict.fromkeys(
            str(actor) for actor in
            ((entity.get("actors_by_transition") or {}).get("accepted") or [])
        ))
        configured = set(spec.get("confirm_permissions") or [])
        if "player" in configured:
            configured.add("user")
        accepted_by = [
            actor for actor in accepted_by
            if not configured or actor in configured
        ]
        has_player = "user" in accepted_by
        has_counterpart = bool(
            (character_confirmers[field] | configured).intersection(accepted_by)
            - {"user", "player"}
        )
        policy = str(spec.get("confirmation_policy") or "responsible_participant")
        confirmed = {
            "player": has_player,
            "responsible_participant": has_counterpart,
            "player_and_authorized_counterpart": has_player and has_counterpart,
            "player_and_responsible_participant": has_player and has_counterpart,
            "player_and_assignee": has_player and has_counterpart,
        }.get(policy, False)
        current = variables.setdefault(field, {
            "value": None, "status": "unknown", "proposals": [],
            "confirmations": [], "evidence": [],
        })
        current["value"] = value
        current["status"] = "confirmed" if lifecycle == "accepted" and confirmed else "proposed"
        current["confirmations"] = accepted_by
        public_evidence = [
            dict(event.get("public_evidence") or {}, speaker_id=event.get("actor_id"))
            for event in (ledger.get("events") or [])
            if event.get("entity_id") == f"field:{field}"
            and event.get("transition_to") == lifecycle
        ]
        current["evidence"] = public_evidence[-20:]


def _event_is_task_critical(
    raw: dict[str, Any], state: dict[str, Any], existing_item: dict[str, Any]
) -> tuple[bool, str]:
    """Validate an evaluator's criticality claim against public task evidence.

    Ordinary offers remain auditable work items, but only obligations that
    demonstrably block configured state or closure enter the coordinator queue.
    """
    if str((state.get("closure_lock") or {}).get("status") or "") == "locked":
        return False, "configured_completion_closure_locked"
    if existing_item.get("required") is True:
        return True, str(existing_item.get("criticality_reason") or "existing_required_work")
    if raw.get("task_critical") is not True:
        return False, "not_marked_task_critical"
    evidence_text = " ".join(
        str(row.get("quote") or "")
        for row in (raw.get("evidence") or [])
        if isinstance(row, dict)
    )
    # Only the stable subject and verified public quote can prove criticality;
    # evaluator-authored summaries/reasons are explanatory, not evidence.
    claim_text = " ".join([str(raw.get("subject") or ""), evidence_text])
    claim_tokens = _work_key_tokens(claim_text)
    open_tokens: set[str] = set()
    has_open_state = False
    for issue in state.get("open_issues") or []:
        if not str(issue).startswith("work:"):
            has_open_state = True
            open_tokens.update(_work_key_tokens(issue))
    overlaps_open_state = bool(claim_tokens & open_tokens)
    explicit_blocking_language = bool(_CRITICAL_LANGUAGE_RE.search(claim_text))
    # In schema-driven tasks, a newly mentioned side issue cannot become a
    # completion prerequisite merely because someone calls it a blocker.  It
    # must overlap a configured open field.  Open-ended tasks without state
    # conditions may still promote an explicit public blocker.
    if overlaps_open_state or (explicit_blocking_language and not has_open_state):
        reason = str(raw.get("criticality_reason") or "").strip()[:300]
        return True, reason or (
            "overlaps_open_state" if overlaps_open_state else "explicit_public_blocker"
        )
    return False, "criticality_not_supported_by_public_task_evidence"


def task_progress_signature(task_state: dict[str, Any] | None) -> str:
    """Stable, evidence-free signature used to detect real task progress."""
    state = task_state or {}
    variables = state.get("variables") or {}
    compact = {
        "phase": state.get("phase"),
        "completion_status": state.get("completion_status"),
        "variables": {
            field: {
                "value": item.get("value") if item.get("status") in {"confirmed", "rejected"} else None,
                "status": item.get("status") if item.get("status") in {"confirmed", "rejected"} else "unresolved",
                "confirmations": sorted(set(item.get("confirmations") or [])) if item.get("status") == "confirmed" else [],
            }
            for field, item in sorted(variables.items())
            if isinstance(item, dict)
        },
        # Work items represent material progress (documents delivered, actions
        # completed, blockers raised), not merely another differently worded
        # conversational turn. Repeated promises therefore do not reset the
        # stagnation counter.
        "work_items": {
            key: {"status": item.get("status")}
            for key, item in sorted((state.get("work_items") or {}).items())
            if isinstance(item, dict) and item.get("status") in MATERIAL_WORK_STATUSES
        },
        "outcome": {
            "type": (state.get("outcome") or {}).get("type"),
            "status": (state.get("outcome") or {}).get("status"),
        },
        "public_ledger": {
            entity_id: {"lifecycle": entity.get("lifecycle")}
            for entity_id, entity in sorted(
                (ensure_public_ledger(state).get("entities") or {}).items()
            )
            if isinstance(entity, dict) and entity.get("lifecycle") in MATERIAL_LIFECYCLE
        },
    }
    return json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str)


def public_task_result(task_state: dict[str, Any] | None) -> dict[str, Any]:
    """Expose auditable outcomes without private prompts, reasoning, or memories."""
    state = task_state or {}
    _project_public_ledger(state)
    variables = state.get("variables") or {}
    return {
        "phase": state.get("phase"),
        "completion_status": state.get("completion_status", "in_progress"),
        "variables": {
            field: {
                "value": item.get("value"),
                "status": item.get("status", "unknown"),
                "confirmations": list(item.get("confirmations") or []),
            }
            for field, item in variables.items()
            if isinstance(item, dict)
        },
        "open_issues": list(state.get("open_issues") or []),
        "condition_results": list(state.get("condition_results") or []),
        "work_items": deepcopy(state.get("work_items") or {}),
        "capability_boundaries": deepcopy(state.get("capability_boundaries") or {}),
        "closure_lock": deepcopy(state.get("closure_lock") or {}),
        "recent_events": deepcopy((state.get("event_ledger") or [])[-30:]),
        "outcome": deepcopy(state.get("outcome") or {}),
        "progress": deepcopy(state.get("progress") or {}),
        "coordination_history": deepcopy((state.get("coordination_history") or [])[-30:]),
        "public_ledger": public_ledger_view(state),
    }


def _evaluator_state_view(state: dict[str, Any]) -> dict[str, Any]:
    """Keep the evaluator prompt bounded as proposals/evidence accumulate."""
    public = public_task_result(state)
    ledger = public.get("public_ledger") or {}
    public["public_ledger"] = {
        "schema": ledger.get("schema"),
        "simulation_clock": ledger.get("simulation_clock") or {},
        "entities": dict(list((ledger.get("entities") or {}).items())[-40:]),
        "recent_events": list(ledger.get("recent_events") or [])[-20:],
        "recent_rejections": list(ledger.get("recent_rejections") or [])[-10:],
    }
    return public


def _evaluator_config_view(task_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": task_config.get("task_type"),
        "state_schema": task_config.get("state_schema") or {},
        "phase_ids": [
            phase.get("phase_id")
            for phase in task_config.get("phases") or []
            if isinstance(phase, dict) and phase.get("phase_id")
        ],
        "completion_conditions": task_config.get("completion_conditions") or {},
        "evaluator_instructions": task_config.get("evaluator_instructions") or [],
    }


def _coerce_value(value: Any, spec: dict[str, Any]) -> tuple[Any, bool]:
    """Validate common JSON scalar types declared by arbitrary scenario schemas."""
    kind = str(spec.get("type") or "").lower()
    if value is None:
        return None, True
    if kind == "boolean":
        if isinstance(value, bool):
            return value, True
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true", True
        return value, False
    if kind == "integer":
        if isinstance(value, bool):
            return value, False
        try:
            normalized = str(value).strip().replace(",", "")
            if isinstance(value, str):
                match = re.fullmatch(
                    r"\s*([-+]?\d+(?:\.\d+)?)\s*(?:[A-Za-z%$€£¥/._-]+(?:\s+[A-Za-z%$€£¥/._-]+)*)?\s*",
                    normalized,
                )
                if not match:
                    return value, False
                normalized = match.group(1)
            number = int(float(normalized))
            return number, float(normalized) == number
        except (TypeError, ValueError):
            return value, False
    if kind == "number":
        if isinstance(value, bool):
            return value, False
        try:
            normalized = str(value).strip().replace(",", "")
            if isinstance(value, str):
                match = re.fullmatch(
                    r"\s*([-+]?\d+(?:\.\d+)?)\s*(?:[A-Za-z%$€£¥/._-]+(?:\s+[A-Za-z%$€£¥/._-]+)*)?\s*",
                    normalized,
                )
                if not match:
                    return value, False
                normalized = match.group(1)
            return float(normalized), True
        except (TypeError, ValueError):
            return value, False
    if kind == "string":
        return (value, True) if isinstance(value, str) else (value, False)
    if kind == "array":
        return (value, True) if isinstance(value, list) else (value, False)
    if kind == "object":
        return (value, True) if isinstance(value, dict) else (value, False)
    return value, True


def normalize_evaluator_payload(raw: str) -> dict[str, Any]:
    """Unwrap OpenAI-compatible providers that nest structured JSON in an envelope."""
    current: Any = orch_support.parse_json(raw)
    for _ in range(4):
        if not isinstance(current, dict):
            return {}
        if isinstance(current.get("updates"), list):
            return current
        nested: Any = None
        for key in ("content", "result", "response", "output"):
            if key in current:
                nested = current[key]
                break
        if isinstance(nested, dict):
            current = nested
        elif isinstance(nested, str):
            current = orch_support.parse_json(nested)
        else:
            return current
    return current if isinstance(current, dict) else {}


def initial_task_state(task_config: dict[str, Any]) -> dict[str, Any]:
    phases = task_config.get("phases") or []
    first = phases[0].get("phase_id", "active") if phases and isinstance(phases[0], dict) else "active"
    variables = {}
    for field, spec in (task_config.get("state_schema") or {}).items():
        variables[field] = {
            "value": deepcopy(spec.get("initial_value")),
            "status": "unknown",
            "proposals": [],
            "confirmations": [],
            "evidence": [],
        }
    return {
        "schema_version": 7,
        "phase": first,
        "completion_status": "in_progress",
        "variables": variables,
        "open_issues": list(variables),
        "condition_results": [],
        "event_ledger": [],
        "work_items": {},
        "capability_boundaries": {},
        "closure_lock": {},
        "outcome": {"type": None, "status": "open", "reason": "", "evidence": []},
        "progress": {"stagnant_turns": 0, "last_progress_turn": 0},
        "public_ledger": ensure_public_ledger({}),
    }


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    try:
        if operator == "==": return actual == expected
        if operator == "!=": return actual != expected
        if operator == "<=": return actual <= expected
        if operator == ">=": return actual >= expected
        if operator == "<": return actual < expected
        if operator == ">": return actual > expected
        if operator == "in": return actual in expected
        if operator == "contains": return expected in actual
    except (TypeError, ValueError):
        return False
    return False


def _condition_result(condition: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    field = str(condition.get("field", ""))
    state = variables.get(field) or {}
    required_status = condition.get("required_status", "confirmed")
    allowed_statuses = condition.get("allowed_statuses")
    status_ok = state.get("status") in allowed_statuses if allowed_statuses else (state.get("status") == required_status if required_status else True)
    value_ok = _compare(state.get("value"), str(condition.get("operator", "==")), condition.get("value"))
    return {"condition": condition, "met": bool(status_ok and value_ok), "actual": state.get("value"), "status": state.get("status", "unknown")}


def _completion_field_results(
    task_config: dict[str, Any], variables: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Evaluate configured fields without letting derived work shadow them."""
    root = task_config.get("completion_conditions") or {"all": []}
    all_results = [_condition_result(c, variables) for c in root.get("all", [])]
    any_results = [_condition_result(c, variables) for c in root.get("any", [])]
    complete = bool(all_results or any_results) and all(
        row["met"] for row in all_results
    ) and (not any_results or any(row["met"] for row in any_results))
    return all_results, any_results, complete


def _reconcile_required_work_with_authoritative_fields(
    task_config: dict[str, Any], task_state: dict[str, Any], *, turn_id: int = 0,
) -> None:
    """Make configured field state authoritative over extractor-created work."""
    schema = task_config.get("state_schema") or {}
    variables = task_state.get("variables") or {}
    boundaries = task_state.get("capability_boundaries") or {}
    work_items = task_state.get("work_items") or {}
    field_tokens = {
        str(field): (
            _work_key_tokens(str(field)),
            _work_key_tokens(f"{field} {(spec or {}).get('description') or ''}"),
        )
        for field, spec in schema.items()
    }
    for key, item in work_items.items():
        if not isinstance(item, dict) or item.get("required") is not True:
            continue
        tokens = _work_key_tokens(" ".join([
            str(key), str(item.get("subject") or ""),
            str(item.get("criticality_reason") or ""),
        ]))
        related = []
        for field, (identity_tokens, configured_tokens) in field_tokens.items():
            overlap = tokens.intersection(configured_tokens)
            # A single generic word such as "review", "plan", or "owner"
            # must not close unrelated work. Multi-token fields need at least
            # two grounded terms; genuinely single-token fields need one.
            minimum_overlap = 1 if len(identity_tokens) <= 1 else 2
            if len(overlap) >= minimum_overlap:
                related.append(field)
        resolved = [
            field for field in related
            if (variables.get(field) or {}).get("status") == "confirmed"
            or str((boundaries.get(field) or {}).get("status") or "")
            in {"unavailable", "resolved"}
        ]
        if resolved:
            item["required"] = False
            item["closure_superseded_by_fields"] = resolved
            item["closure_reconciled_turn"] = int(turn_id)

    all_results, any_results, fields_complete = _completion_field_results(
        task_config, variables
    )
    if fields_complete:
        completed_fields = list(dict.fromkeys(
            str(row["condition"].get("field"))
            for row in [*all_results, *any_results]
            if row["met"] and row["condition"].get("field")
        ))
        task_state["closure_lock"] = {
            "status": "locked",
            "turn_id": int(turn_id),
            "resolved_fields": completed_fields,
            "reason": "configured_completion_fields_satisfied",
        }
        for item in work_items.values():
            if not isinstance(item, dict) or item.get("required") is not True:
                continue
            item["required"] = False
            item["closure_superseded_by_fields"] = completed_fields
            item["closure_reconciled_turn"] = int(turn_id)
    elif str((task_state.get("closure_lock") or {}).get("status") or "") == "locked":
        task_state["closure_lock"] = {
            **dict(task_state.get("closure_lock") or {}),
            "status": "reopened",
            "reopened_turn": int(turn_id),
            "reason": "authorized_field_challenge_or_condition_change",
        }
    task_state["work_items"] = work_items


def conditions_met(root: dict[str, Any] | None, variables: dict[str, Any]) -> bool:
    if not root:
        return False
    all_results = [_condition_result(c, variables) for c in root.get("all", [])]
    any_results = [_condition_result(c, variables) for c in root.get("any", [])]
    return bool(all_results or any_results) and all(r["met"] for r in all_results) and (not any_results or any(r["met"] for r in any_results))


def advance_phase(task_config: dict[str, Any], task_state: dict[str, Any]) -> str:
    """Advance monotonically to the furthest phase whose entry conditions are met."""
    phases = [p for p in task_config.get("phases", []) if isinstance(p, dict) and p.get("phase_id")]
    if not phases:
        return str(task_state.get("phase") or "active")
    ids = [str(p["phase_id"]) for p in phases]
    current = str(task_state.get("phase") or ids[0])
    current_index = ids.index(current) if current in ids else 0
    variables = task_state.get("variables") or {}
    furthest = current_index
    for index, phase in enumerate(phases[current_index + 1 :], start=current_index + 1):
        if conditions_met(phase.get("entry_conditions"), variables):
            furthest = index
    task_state["phase"] = ids[furthest]
    return ids[furthest]


def evaluate_conditions(task_config: dict[str, Any], task_state: dict[str, Any]) -> dict[str, Any]:
    _project_public_ledger(task_state)
    variables = task_state.get("variables") or {}
    _reconcile_required_work_with_authoritative_fields(
        task_config, task_state,
        turn_id=int(
            ((ensure_public_ledger(task_state).get("simulation_clock") or {}).get("turn"))
            or 0
        ),
    )
    all_results, any_results, fields_complete = _completion_field_results(
        task_config, variables
    )
    required_work_open = any(
        isinstance(item, dict) and item.get("required") is True
        and item.get("status") not in {"submitted", "completed", "rejected"}
        for item in (task_state.get("work_items") or {}).values()
    )
    complete = fields_complete and not required_work_open
    task_state["condition_results"] = all_results + any_results
    explicit_outcome = (task_state.get("outcome") or {}).get("type")
    has_configured_conditions = bool(all_results or any_results)
    if complete and has_configured_conditions:
        task_state["completion_status"] = "completed"
    elif explicit_outcome == "completed" and has_configured_conditions:
        # Dialogue can claim that work is complete while the evidence-backed
        # state still contains unmet required conditions.  Preserve the public
        # claim, but reconcile it to a truthful terminal result rather than
        # allowing the assertion to override the ledger.
        outcome = dict(task_state.get("outcome") or {})
        outcome["claimed_type"] = "completed"
        outcome["type"] = "conditional" if any(r["met"] for r in [*all_results, *any_results]) else "deferred"
        outcome["status"] = "reconciled_unmet_conditions"
        unmet = [r["condition"].get("field") for r in [*all_results, *any_results] if not r["met"]]
        outcome["unmet_conditions"] = list(dict.fromkeys(str(field) for field in unmet if field))
        task_state["outcome"] = outcome
        task_state["completion_status"] = str(outcome["type"])
    elif explicit_outcome in TERMINAL_OUTCOMES:
        task_state["completion_status"] = explicit_outcome
    else:
        task_state["completion_status"] = "in_progress"
    variable_issues = [name for name, value in variables.items() if value.get("status") != "confirmed"]
    work_issues = [
        f"work:{key}" for key, item in (task_state.get("work_items") or {}).items()
        if isinstance(item, dict) and item.get("required") is True
        and item.get("status") not in {"submitted", "completed", "rejected"}
    ]
    task_state["open_issues"] = list(dict.fromkeys([*variable_issues, *work_issues]))
    advance_phase(task_config, task_state)
    return task_state


def set_progress_metadata(
    task_state: dict[str, Any], *, stagnant_turns: int, turn_id: int, progress_made: bool
) -> dict[str, Any]:
    """Persist convergence signals so every agent sees the same meeting state."""
    progress = dict(task_state.get("progress") or {})
    progress["stagnant_turns"] = max(0, int(stagnant_turns))
    progress["last_checked_turn"] = max(0, int(turn_id))
    if progress_made:
        progress["last_progress_turn"] = max(0, int(turn_id))
    task_state["progress"] = progress
    return task_state


def prepare_turn_governance(
    task_state: dict[str, Any],
    *,
    characters: list[CharacterTemplate],
    turn_id: int,
    safety_max_turns: int,
    max_stagnant_turns: int,
) -> dict[str, Any]:
    """Select one deterministic focus before an autonomous RoomMind turn.

    The coordinator does not invent domain facts or complete work. It only
    exposes which already-public unresolved item should move next, who has
    authority/ownership, and whether the meeting is approaching a closeout
    boundary. This keeps independent agents coordinated without sharing their
    private memories.
    """
    state = deepcopy(task_state)
    _project_public_ledger(state)
    progress = dict(state.get("progress") or {})
    stagnant_turns = max(0, int(progress.get("stagnant_turns") or 0))
    remaining_turns = max(0, int(safety_max_turns) - int(turn_id) + 1)
    closeout_required = (
        remaining_turns <= 2
        or stagnant_turns >= max(2, int(max_stagnant_turns) - 2)
    )

    prior_history = [
        row for row in (state.get("coordination_history") or [])
        if isinstance(row, dict)
    ]
    last_issue = str((((prior_history[-1].get("focus") or {}).get("issue")) or "")) if prior_history else ""
    trailing_focus_streak = 0
    for row in reversed(prior_history):
        if str(((row.get("focus") or {}).get("issue")) or "") != last_issue:
            break
        trailing_focus_streak += 1

    focus: dict[str, Any] | None = None
    registered_ids = {character.character_id for character in characters}
    work_items = state.get("work_items") or {}
    candidates: list[dict[str, Any]] = []
    for key, raw in work_items.items():
        if not isinstance(raw, dict) or raw.get("required") is not True:
            continue
        status = str(raw.get("status") or "unknown")
        if status in {"submitted", "completed", "rejected"}:
            continue
        raw_owner = "user" if str(raw.get("owner_id") or "") == "player" else str(raw.get("owner_id") or "")
        raw_target = "user" if str(raw.get("target_id") or "") == "player" else str(raw.get("target_id") or "")
        if raw_owner not in registered_ids and raw_target not in registered_ids:
            # The comparison player deliberately has no access to RoomMind's
            # private coordinator.  Do not select player-only work that this
            # coordinator cannot route to a responsible NPC.
            continue
        promised_turn = int(raw.get("promised_turn") or 0)
        age = max(0, int(turn_id) - promised_turn) if promised_turn else 0
        issue = f"work:{key}"
        priority = (
            0 if status == "blocked" or (status == "promised" and age >= 2)
            else 2
        )
        candidates.append({
            "priority": priority,
            "order": promised_turn or int(turn_id),
            "key": issue,
            "issue": f"work:{key}",
            "kind": "work_item",
            "status": status,
            "subject": str(raw.get("subject") or key),
            "owner_ids": list(dict.fromkeys(
                cid for cid in (raw_owner, raw_target) if cid in registered_ids
            )),
            "age_turns": age,
            "due_now": bool(status == "blocked" or age >= 2),
            "blocked_cooldown": False,
        })

    variables = state.get("variables") or {}
    executable_fields = {
        str(field)
        for character in characters
        for field in ((character.authority or {}).get("can_execute") or [])
    }
    tool_result_fields = {
        str(result.get("field") or "")
        for result in ((ensure_public_ledger(state).get("tool_results") or {}).values())
        if isinstance(result, dict) and str(result.get("field") or "")
    }
    capability_boundaries = state.setdefault("capability_boundaries", {})
    for field_index, field in enumerate(state.get("open_issues") or []):
        if str(field).startswith("work:") or field not in variables:
            continue
        owners = [
            character.character_id
            for character in characters
            if field in ((character.authority or {}).get("can_confirm") or [])
        ]
        item = variables.get(field) or {}
        tool_result_required = field in executable_fields
        tool_result_available = field in tool_result_fields
        prior_boundary = capability_boundaries.get(str(field)) or {}
        if tool_result_available and prior_boundary:
            capability_boundaries[str(field)] = {
                **prior_boundary,
                "status": "resolved",
                "resolved_turn": int(turn_id),
            }
        if (
            tool_result_required
            and not tool_result_available
            and str(prior_boundary.get("status") or "") == "unavailable"
        ):
            # The environment boundary is durable public state.  Repeatedly
            # asking for the same impossible in-session result adds no facts
            # and previously trapped incident simulations in a loop.
            continue
        candidates.append({
            "priority": 0 if closeout_required or (tool_result_required and not tool_result_available) else 1,
            "order": field_index,
            "key": f"state:{field}",
            "issue": str(field),
            "kind": (
                "capability_boundary"
                if tool_result_required and not tool_result_available
                else "state_variable"
            ),
            "status": str(item.get("status") or "unknown"),
            "subject": str(field),
            "owner_ids": owners,
            "age_turns": 0,
            "due_now": closeout_required or (tool_result_required and not tool_result_available),
            "blocked_cooldown": False,
            "tool_result_required": tool_result_required,
            "tool_result_available": tool_result_available,
        })

    if candidates:
        ordered = sorted(
            candidates,
            key=lambda row: (int(row["priority"]), int(row["order"]), str(row["key"])),
        )
        chosen = ordered[0]
        # A single unresolved state variable can monopolize the conversation
        # just as easily as a blocked work item.  Give every ordinary focus at
        # most two consecutive turns.  Rotate to the best alternative when one
        # exists; otherwise require an explicit truthful outcome resolution.
        if last_issue and chosen["issue"] == last_issue and trailing_focus_streak >= 2:
            alternative = next(
                (row for row in ordered if str(row.get("issue") or "") != last_issue),
                None,
            )
            if alternative is not None:
                chosen = {**alternative, "rotated_from_issue": last_issue}
            else:
                prior_focus = (prior_history[-1].get("focus") or {}) if prior_history else {}
                chosen = {
                    "priority": -1,
                    "order": int(turn_id),
                    "key": "outcome_resolution",
                    "issue": "outcome_resolution",
                    "kind": "outcome_resolution",
                    "status": str(prior_focus.get("status") or chosen.get("status") or "unresolved"),
                    "subject": str(prior_focus.get("subject") or chosen.get("subject") or last_issue),
                    "owner_ids": list(prior_focus.get("owner_ids") or chosen.get("owner_ids") or []),
                    "age_turns": int(prior_focus.get("age_turns") or chosen.get("age_turns") or 0),
                    "due_now": True,
                    "blocked_cooldown": True,
                    "origin_focus_issue": last_issue,
                    "rotated_from_issue": last_issue,
                }
        focus = {
            key: value for key, value in chosen.items()
            if key not in {"priority", "order", "key"}
        }
        focus["focus_streak"] = (
            trailing_focus_streak + 1 if focus["issue"] == last_issue else 1
        )
        if focus.get("kind") == "capability_boundary":
            field = str(focus.get("subject") or focus.get("issue") or "")
            existing = capability_boundaries.get(field) or {}
            capability_boundaries[field] = {
                **existing,
                "field": field,
                "status": "unavailable",
                "reason": "registered_simulated_tool_result_unavailable",
                "first_observed_turn": int(existing.get("first_observed_turn") or turn_id),
                "last_checked_turn": int(turn_id),
            }

    if focus:
        if focus.get("kind") == "outcome_resolution":
            instruction = (
                "This unresolved focus has already held the floor for two turns. "
                "Do not restate or invent completion evidence. Resolve the current activity "
                "truthfully now: confirm it with existing public evidence, explicitly reject "
                "or block it, hand it off with an owner and review point, or state a "
                "conditional, deferred, or failed outcome naming what remains unresolved."
            )
        elif focus.get("kind") == "capability_boundary":
            instruction = (
                "This state requires an environment/tool result that is not available in the "
                "current text simulation. Do not claim that the action happened and do not ask "
                "again for an impossible in-session result. State the proposed action and owner, "
                "then close conditionally or defer to a named external follow-up and review point."
            )
        elif closeout_required:
            instruction = (
                "Close out this focus now: the responsible role must either complete/confirm it "
                "with public evidence, explicitly block or reject it, hand it off with an owner "
                "and review point, or state a truthful conditional/deferred/failed outcome."
            )
        elif focus.get("due_now"):
            instruction = (
                "The commitment is due in-session. The responsible role must perform or submit it "
                "now, or explicitly state the blocker and a concrete handoff; another promise is "
                "not progress."
            )
        else:
            instruction = (
                "Advance this single focus with a new fact, proposal, authorized decision, "
                "material action, or necessary objection."
            )
        focus["instruction"] = instruction
        focus["closeout_required"] = closeout_required

    progress.update({
        "turn_id": int(turn_id),
        "remaining_turns": remaining_turns,
        "closeout_required": closeout_required,
        "focus": focus,
    })
    state["progress"] = progress
    history = [
        row for row in prior_history
        if isinstance(row, dict) and int(row.get("turn_id") or -1) != int(turn_id)
    ]
    history.append({
        "turn_id": int(turn_id),
        "remaining_turns": remaining_turns,
        "stagnant_turns": stagnant_turns,
        "closeout_required": closeout_required,
        "focus": deepcopy(focus),
    })
    state["coordination_history"] = history[-100:]
    return state


def reconcile_capability_boundary_closure(
    task_config: dict[str, Any], task_state: dict[str, Any], *, turn_id: int = 0,
) -> dict[str, Any]:
    """Close truthfully when only unavailable environment actions remain.

    This reducer never marks an action complete.  It converts an otherwise
    endless text-only simulation into a conditional outcome once every unmet
    completion condition is a persisted capability boundary and all other
    required public work is resolved.
    """
    if (task_state.get("outcome") or {}).get("type") in TERMINAL_OUTCOMES:
        return task_state
    root = task_config.get("completion_conditions") or {"all": []}
    variables = task_state.get("variables") or {}
    all_results = [_condition_result(c, variables) for c in root.get("all", [])]
    any_results = [_condition_result(c, variables) for c in root.get("any", [])]
    unmet_all = [row for row in all_results if not row["met"]]
    unmet_any = [] if (not any_results or any(row["met"] for row in any_results)) else any_results
    unmet = [*unmet_all, *unmet_any]
    if not unmet:
        return task_state
    boundaries = task_state.get("capability_boundaries") or {}
    unmet_fields = {
        str(row.get("condition", {}).get("field") or "") for row in unmet
    }
    bounded_fields = {
        str(field) for field, row in boundaries.items()
        if isinstance(row, dict) and row.get("status") == "unavailable"
    }
    required_work_open = any(
        isinstance(item, dict)
        and item.get("required") is True
        and item.get("status") not in {"submitted", "completed", "rejected"}
        for item in (task_state.get("work_items") or {}).values()
    )
    if not unmet_fields or not unmet_fields.issubset(bounded_fields) or required_work_open:
        return task_state
    ordered = sorted(field for field in unmet_fields if field)
    task_state["outcome"] = {
        "type": "conditional",
        "status": "capability_boundary_reconciled",
        "reason": (
            "The text simulation resolved every available requirement; the remaining "
            "conditions require registered environment or tool results."
        ),
        "turn_id": int(turn_id),
        "unmet_conditions": ordered,
        "evidence": [],
    }
    task_state["completion_status"] = "conditional"
    return task_state


def finalize_stalled_task_state(
    task_state: dict[str, Any], *, turn_id: int, reason: str | None = None
) -> dict[str, Any]:
    """Close an autonomous simulation that cannot make material progress.

    This is deliberately domain-neutral: a negotiation may be deferred, an
    incident exercise may be blocked, and an interview may end incomplete.
    """
    state = deepcopy(task_state)
    open_issues = list(state.get("open_issues") or [])
    state["outcome"] = {
        "type": "stalled",
        "status": "system_closed",
        "reason": reason or "No material state, work-item, or outcome progress within the configured window.",
        "turn_id": int(turn_id),
        "open_issues": open_issues,
        "evidence": [],
    }
    state["completion_status"] = "stalled"
    return state


def _valid_public_evidence(
    evidence: Any, turn_text: dict[str, str]
) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for row in evidence if isinstance(evidence, list) else []:
        if not isinstance(row, dict):
            continue
        speaker_id = "user" if row.get("speaker_id") == "player" else str(row.get("speaker_id") or "")
        quote = " ".join(str(row.get("quote") or "").split()).casefold()
        public_text = " ".join(turn_text.get(speaker_id, "").split()).casefold()
        if speaker_id and quote and quote in public_text:
            valid.append({**row, "speaker_id": speaker_id})
    return valid


_GROUNDING_STOPWORDS = {
    "accepted", "agreed", "boolean", "configured", "current", "integer",
    "number", "standard", "status", "target", "true", "value",
}


def _field_update_is_grounded(
    *, field: str, spec: dict[str, Any], value: Any, status: str,
    evidence: list[dict[str, Any]],
) -> bool:
    """Reject evaluator updates not explicitly supported by their quote.

    Exact quote matching proves only that the words were public; it does not
    prove the extracted field or value occurred in those words.  This compact
    deterministic check keeps an LLM evaluator from copying goals/schema
    defaults into state when a participant never stated them.
    """
    if not evidence:
        return False
    text = " ".join(str(row.get("quote") or "") for row in evidence).casefold()
    field_phrase = field.replace("_", " ").casefold()
    tokens = {
        token for token in re.findall(
            r"[\w]+", f"{field_phrase} {spec.get('description') or ''}".casefold()
        )
        if len(token) >= 4 and token not in _GROUNDING_STOPWORDS
    }
    if field_phrase not in text and not any(
        re.search(rf"\b{re.escape(token)}\b", text) for token in tokens
    ):
        return False

    value_type = str(spec.get("type") or "string").lower()
    if value_type in {"number", "integer"}:
        candidates = {str(value)}
        try:
            numeric = float(value)
            candidates.add(f"{numeric:g}")
        except (TypeError, ValueError):
            return False
        if not any(re.search(rf"(?<![\w.]){re.escape(item)}(?![\w.])", text) for item in candidates):
            return False
    elif value_type == "boolean":
        positive = r"\b(?:accept|accepted|agree|agreed|approve|approved|confirm|confirmed|adopt|adopted|enable|enabled|active|activated|complete|completed|identified|ready|cover|covers|covered|satisfy|satisfies|satisfied|meet|meets|met|yes|true)\b"
        negative = r"\b(?:reject|rejected|decline|declined|not|no|false|inactive|disable|disabled)\b"
        if bool(value) and not re.search(positive, text):
            return False
        if not bool(value) and not re.search(negative, text):
            return False
    elif value is not None:
        normalized_value = str(value).strip().casefold()
        value_tokens = {
            token for token in re.findall(r"[\w]+", normalized_value)
            if len(token) >= 3
        }
        if normalized_value not in text and not (
            value_tokens
            and any(re.search(rf"\b{re.escape(token)}\b", text) for token in value_tokens)
            and _quote_references_field(field, spec, text)
        ):
            return False

    return True


def _commit_explicit_field_confirmations(
    *, field: str, spec: dict[str, Any], value: Any,
    confirmations: list[str], evidence: list[dict[str, Any]],
    state: dict[str, Any], characters: list[CharacterTemplate], turn_id: int,
) -> None:
    """Atomically project explicit authorized speech into the public ledger.

    The semantic evaluator may describe a partially confirmed field as merely
    ``proposed`` until the full confirmation policy is satisfied.  Waiting for
    the aggregate status loses each participant's real acceptance and caused
    G3.4 to repeat already-settled issues.  Each explicit, grounded acceptance
    is committed independently; the normal ledger projection decides when the
    configured multi-party policy is complete.
    """
    by_id = {character.character_id: character for character in characters}
    configured = set(spec.get("confirm_permissions") or [])
    if "player" in configured:
        configured.add("user")
    for speaker_id in dict.fromkeys(confirmations):
        if configured and speaker_id not in configured:
            continue
        row = next(
            (candidate for candidate in evidence
             if str(candidate.get("speaker_id") or "") == speaker_id),
            None,
        )
        if not row or not _field_update_is_grounded(
            field=field, spec=spec, value=value, status="confirmed", evidence=[row],
        ):
            continue
        if speaker_id == "user":
            character: Any = {
                "character_id": "user",
                "authority": {"can_confirm": [field], "can_propose": [field]},
            }
        else:
            character = by_id.get(speaker_id)
            if character is None:
                continue
        quote = " ".join(str(row.get("quote") or "").split())
        intent = validate_public_intent(
            character=character,
            intent={
                "kind": "decision",
                "subject": str(spec.get("description") or field.replace("_", " ")),
                "transition": "accepted",
                "field": field,
                "value": value,
                "simulation_scope": "discussion",
                "evidence_source": "public_statement",
            },
            turn_id=turn_id,
            state=state,
        )
        intent = ground_public_intent_in_quote(intent, quote)
        if intent.get("commit_allowed", True):
            commit_public_intent(
                state, intent=intent, public_quote=quote,
                tick=len((ensure_public_ledger(state).get("events") or [])) + 1,
            )


_EXPLICIT_ACCEPTANCE_RE = re.compile(
    r"\b(?:(?:i|we)\s+(?:(?:can|hereby|now|fully|explicitly|formally)\s+)*"
    r"(?:confirm|accept|approve|agree(?:\s+to)?|support)|"
    r"(?:i|we)(?:(?:\s+will|['’]ll))?\s+consider\b[^.!?;]{0,100}\bcomplete|"
    r"(?:i|we)(?:(?:\s+am|['’]m|\s+are|['’]re))\s+(?:officially\s+)?(?:setting|assigning|designating|appointing)|"
    r"(?:i|we)\s+(?:officially\s+)?(?:set|assign|designate|appoint)|"
    r"confirmed\s*[-—:]|"
    r"(?:cover|covers|covered|satisfy|satisfies|satisfied|meet|meets|met)\b[^.!?;]{0,100}\b(?:evidence|requirement|criteria|need)|"
    r"(?:is|are|has\s+been|have\s+been)\s+(?:now\s+|fully\s+|formally\s+)?"
    r"(?:confirmed|accepted|approved|agreed|identified|ready)|"
    r"(?:is|are)\s+acceptable)\b",
    flags=re.IGNORECASE,
)
_CONDITIONAL_OR_NEGATED_ACCEPTANCE_RE = re.compile(
    r"\b(?:do\s+not|don't|cannot|can't|not\s+(?:yet\s+)?(?:confirm|accept|approve|"
    r"agree|ready)|conditionally|conditional\s+on|subject\s+to|provided\s+that|"
    r"pending|awaiting|before\s+(?:i|we)\s+(?:can|will)|until)\b",
    flags=re.IGNORECASE,
)
_FIELD_REFERENCE_STOPWORDS = {
    "agreed", "and", "are", "can", "concrete", "decision", "explicitly",
    "final", "obtained", "support", "supported", "the", "with",
}


def _quote_references_field(field: str, spec: dict[str, Any], quote: str) -> bool:
    text = " ".join(str(quote or "").casefold().replace("_", " ").split())
    phrase = field.casefold().replace("_", " ")
    if phrase in text:
        return True
    tokens = {
        token for token in re.findall(
            r"[a-z0-9]+", f"{phrase} {spec.get('description') or ''}".casefold()
        )
        if len(token) >= 4 and token not in _FIELD_REFERENCE_STOPWORDS
    }
    hits = {token for token in tokens if re.search(rf"\b{re.escape(token)}\b", text)}
    return len(hits) >= min(2, max(1, len(tokens)))


def _explicit_value_from_quote(
    *, field: str, spec: dict[str, Any], quote: str, current_value: Any,
) -> tuple[Any, bool]:
    text = " ".join(str(quote or "").split())
    kind = str(spec.get("type") or "string").lower()
    if kind in {"number", "integer"}:
        unit = str(spec.get("unit") or "").strip()
        patterns = []
        if unit:
            patterns.append(
                rf"(?<![\w.])([-+]?\d[\d,]*(?:\.\d+)?)\s*(?:[- ]?{re.escape(unit)})\b"
            )
        patterns.append(
            rf"\b{re.escape(field.replace('_', ' '))}\b[^\d]{{0,30}}([-+]?\d[\d,]*(?:\.\d+)?)"
        )
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return _coerce_value(f"{match.group(1)} {unit}".strip(), spec)
        if current_value is not None and _quote_references_field(field, spec, text):
            return _coerce_value(current_value, spec)
        return None, False
    if kind == "boolean":
        if not _quote_references_field(field, spec, text):
            return None, False
        negative = bool(re.search(
            r"\b(?:false|inactive|rejected|declined|not\s+(?:active|accepted|approved|"
            r"confirmed|ready|obtained|identified))\b", text, flags=re.IGNORECASE,
        ))
        return (not negative), True
    if kind == "string":
        if current_value is not None:
            normalized = str(current_value).strip()
            variants = {normalized.casefold(), normalized.casefold().replace("_", " ")}
            if any(value and value in text.casefold() for value in variants):
                return normalized, True
            if _quote_references_field(field, spec, text):
                return normalized, True
        description = str(spec.get("description") or "")
        for candidate in re.findall(r"[a-z][a-z0-9_]+", description.casefold()):
            if "_" in candidate and candidate.replace("_", " ") in text.casefold():
                return candidate, True
        return None, False
    return None, False


def _commit_quote_level_confirmations(
    *, task_config: dict[str, Any], state: dict[str, Any],
    characters: list[CharacterTemplate], turn_text: dict[str, str], turn_id: int,
) -> None:
    """Recover explicit confirmations independently of evaluator intent labels.

    This is deliberately narrow: the quote must contain an unambiguous
    acceptance cue, identify the configured field, state (or resolve to) a
    typed value, and come from a configured confirmer.  It cannot infer
    agreement from politeness, silence, questions, or conditional language.
    """
    schema = task_config.get("state_schema") or {}
    variables = state.get("variables") or {}
    by_id = {character.character_id: character for character in characters}
    for speaker_id, raw_quote in turn_text.items():
        full_quote = " ".join(str(raw_quote or "").split())
        if not full_quote:
            continue
        clauses = [
            clause.strip()
            for clause in re.split(r"(?<=[.!?])\s+|;\s*", full_quote)
            if clause.strip()
        ]
        for field, spec in schema.items():
            # Confirmation is atomic at field/clause level.  A conditional
            # delivery sentence must not erase an unconditional price
            # acceptance elsewhere in the same public turn.
            quote = next((
                clause for clause in clauses
                if not clause.rstrip().endswith("?")
                and _EXPLICIT_ACCEPTANCE_RE.search(clause)
                and not _CONDITIONAL_OR_NEGATED_ACCEPTANCE_RE.search(clause)
                and _quote_references_field(str(field), spec, clause)
            ), "")
            if not quote:
                continue
            configured = set(spec.get("confirm_permissions") or [])
            if "player" in configured:
                configured.add("user")
            authority = (
                {"user"}
                if speaker_id == "user"
                else set((by_id.get(speaker_id).authority or {}).get("can_confirm") or [])
                if by_id.get(speaker_id)
                else set()
            )
            if configured and speaker_id not in configured:
                continue
            if speaker_id != "user" and field not in authority:
                continue
            executable = any(
                field in ((character.authority or {}).get("can_execute") or [])
                for character in characters
            )
            if executable and not ledger_has_support(
                state, kind="action", subject=str(field), field=str(field),
                minimum={"verified", "accepted"},
            ):
                emit(
                    "task_state.quote_confirmation.rejected",
                    field=str(field), speaker_id=speaker_id,
                    reason="executable_field_requires_simulated_tool_result",
                    turn_id=int(turn_id),
                )
                continue
            value, valid = _explicit_value_from_quote(
                field=str(field), spec=spec, quote=quote,
                current_value=(variables.get(field) or {}).get("value"),
            )
            if not valid or value is None:
                continue
            before = len((ensure_public_ledger(state).get("events") or []))
            _commit_explicit_field_confirmations(
                field=str(field), spec=spec, value=value,
                confirmations=[speaker_id],
                evidence=[{"speaker_id": speaker_id, "quote": quote}],
                state=state, characters=characters, turn_id=turn_id,
            )
            after = len((ensure_public_ledger(state).get("events") or []))
            if after > before:
                emit(
                    "task_state.quote_confirmation.committed",
                    field=str(field), speaker_id=speaker_id,
                    normalized_value=value, turn_id=int(turn_id),
                )


def _event_claim_is_grounded(
    event_type: str, actor_id: str, subject: str,
    evidence: list[dict[str, Any]],
) -> bool:
    if actor_id not in {str(row.get("speaker_id") or "") for row in evidence}:
        return False
    actor_text = " ".join(
        str(row.get("quote") or "") for row in evidence
        if str(row.get("speaker_id") or "") == actor_id
    ).casefold()
    if event_type == "information_provided":
        if actor_text.rstrip().endswith("?") or re.search(
            r"\b(?:please|could you|can you|would you|clarify|what|which|who|when|where|how)\b",
            actor_text,
        ):
            return False
        return True
    subject_tokens = _work_key_tokens(subject)
    public_tokens = _work_key_tokens(actor_text)
    if subject_tokens and not subject_tokens.intersection(public_tokens):
        return False
    if event_type == "artifact_offered":
        return bool(re.search(
            r"\b(?:i|we)\s+(?:will|shall|can\s+\w+|plan\s+to|offer\s+to|"
            r"send\b|provide\b|deliver\b|share\b|draft\b|prepare\b)",
            actor_text,
        ))
    if event_type == "action_committed":
        return bool(re.search(
            r"\b(?:i|we)\s+(?:will|shall|commit\s+to|agree\s+to|undertake\s+to|"
            r"can\s+(?:provide|deliver|send|share)|plan\s+to|send\b|provide\b|deliver\b|share\b)",
            actor_text,
        ))
    return True


def _terminal_outcome_is_grounded(
    outcome_type: str, evidence: list[dict[str, Any]]
) -> bool:
    text = " ".join(str(row.get("quote") or "") for row in evidence).casefold()
    if outcome_type == "completed":
        if re.search(r"\b(?:before|until|unless|cannot|can't|not|yet|if)\b", text):
            return False
        return bool(re.search(
            r"\b(?:we (?:have )?(?:agree|agreed)|agreement (?:is|has been) (?:final|finalized|reached)|"
            r"decision (?:is|has been) final|task (?:is|has been) complete|"
            r"meeting (?:is|has been) (?:closed|concluded|adjourned))\b",
            text,
        ))
    patterns = {
        "conditional": r"\b(?:conditional|subject to|provided that)\b",
        "deferred": r"\b(?:defer|deferred|postpone|postponed|hold|pending|cannot finalize|can't finalize)\b",
        "failed": r"\b(?:failed|cannot reach (?:an )?agreement|can't reach (?:an )?agreement|abandon|abandoned)\b",
        "stalled": r"\b(?:stalled|stuck|no (?:further )?progress)\b",
    }
    return bool(re.search(patterns.get(outcome_type, r"(?!)"), text))


def apply_generic_events(
    *,
    state: dict[str, Any],
    parsed: dict[str, Any],
    turn_text: dict[str, str],
    turn_id: int = 0,
) -> None:
    """Apply evidence-grounded events without assuming a negotiation domain."""
    ledger = state.setdefault("event_ledger", [])
    work_items = state.setdefault("work_items", {})
    existing = {
        (row.get("event_type"), row.get("subject_key"), row.get("status"), row.get("actor_id"))
        for row in ledger if isinstance(row, dict) and row.get("transition_valid", True)
    }
    next_event_index = max(
        [int(row.get("event_index") or 0) for row in ledger if isinstance(row, dict)] or [0]
    ) + 1
    for raw in parsed.get("events", []) if isinstance(parsed.get("events"), list) else []:
        if not isinstance(raw, dict):
            continue
        event_type = str(raw.get("event_type") or "")
        status = str(raw.get("status") or "")
        if event_type not in ALLOWED_EVENT_TYPES or status not in ALLOWED_EVENT_STATUSES:
            continue
        evidence = _valid_public_evidence(raw.get("evidence"), turn_text)
        if not evidence:
            continue
        actor_id = "user" if raw.get("actor_id") == "player" else str(raw.get("actor_id") or evidence[0]["speaker_id"])
        key, subject = _resolve_work_item_key(raw, work_items)
        if not _event_claim_is_grounded(event_type, actor_id, subject, evidence):
            continue
        signature = (event_type, key, status, actor_id)
        if signature in existing:
            continue
        item = dict(work_items.get(key) or {})
        task_critical, criticality_reason = _event_is_task_critical(
            {**raw, "evidence": evidence}, state, item
        )
        milestones = set(item.get("milestones") or [])
        transition_error = ""
        if event_type == "artifact_submitted" and not ledger_has_support(
            state, kind="artifact", subject=subject,
            minimum={"submitted", "verified", "accepted"},
        ):
            transition_error = "artifact_submission_not_supported_by_public_ledger"
        elif event_type == "artifact_reviewed" and not ledger_has_support(
            state, kind="artifact", subject=subject,
            minimum={"verified", "accepted"},
        ):
            transition_error = "artifact_review_not_supported_by_public_ledger"
        elif event_type == "action_completed" and not ledger_has_support(
            state, kind="action", subject=subject,
            minimum={"verified", "accepted"},
        ):
            transition_error = "action_completion_not_supported_by_public_ledger"
        transition_valid = not transition_error
        event = {
            "event_index": next_event_index,
            "turn_id": int(turn_id),
            "event_type": event_type, "subject": subject, "subject_key": key,
            "status": status, "actor_id": actor_id,
            "target_id": str(raw.get("target_id") or ""),
            "summary": str(raw.get("summary") or subject).strip()[:500],
            "evidence": evidence,
            "task_critical": task_critical,
            "criticality_reason": criticality_reason,
            "transition_valid": transition_valid,
        }
        next_event_index += 1
        if not transition_valid:
            event["transition_error"] = transition_error
        ledger.append(event)
        if not transition_valid:
            continue
        existing.add(signature)
        aliases = list(dict.fromkeys([*(item.get("aliases") or []), subject]))[-12:]
        item.update({
            "subject": item.get("subject") or subject,
            "kind": item.get("kind") or event_type,
            "last_event_type": event_type,
            "owner_id": actor_id,
            "aliases": aliases,
            "target_id": str(raw.get("target_id") or item.get("target_id") or ""),
            "last_transition_turn": int(turn_id),
        })
        milestones.add(event_type)
        item["milestones"] = sorted(milestones)
        if task_critical:
            item["required"] = True
            item["criticality_reason"] = criticality_reason
        if event_type == "artifact_offered":
            item.setdefault("promised_turn", int(turn_id))
            if item.get("status") not in {"blocked", "submitted", "completed"}:
                item["status"] = "promised"
        elif event_type == "artifact_submitted":
            item["status"] = "submitted"
            item["resolved_turn"] = int(turn_id)
        elif event_type in {"artifact_reviewed", "action_completed"}:
            item["status"] = "completed"
            item["resolved_turn"] = int(turn_id)
        elif event_type == "information_provided":
            # Describing a requirement or blocker is useful information, but
            # does not itself satisfy an already required artifact/action.
            if not item.get("required") or item.get("status") not in {"blocked", "promised"}:
                item["status"] = "completed"
        elif event_type == "outcome":
            item["status"] = "completed" if status == "completed" else status
        elif event_type in {"decision", "handoff", "schedule"}:
            item["status"] = "completed" if status == "completed" else "proposed"
            if status != "completed" and task_critical:
                item["required"] = True
        elif event_type == "action_committed":
            item.setdefault("promised_turn", int(turn_id))
            if item.get("status") not in {"blocked", "completed"}:
                item["status"] = "promised"
        elif event_type == "blocker":
            item["status"] = "blocked"
        work_items[key] = item
    state["event_ledger"] = ledger[-100:]

    raw_outcome = parsed.get("outcome")
    if isinstance(raw_outcome, dict) and str(raw_outcome.get("type") or "") in TERMINAL_OUTCOMES:
        evidence = _valid_public_evidence(raw_outcome.get("evidence"), turn_text)
        outcome_type = str(raw_outcome["type"])
        if evidence and _terminal_outcome_is_grounded(outcome_type, evidence):
            state["outcome"] = {
                "type": outcome_type, "status": "explicit",
                "reason": str(raw_outcome.get("reason") or "").strip()[:800],
                "evidence": evidence,
            }


_CLOSURE_PATTERNS = (
    r"\bmeeting (?:(?:is (?:now )?)|has been )?(?:concluded|adjourned|closed)\b",
    r"\bthis (?:meeting|interview|session) (?:is |has been )?(?:concluded|complete|closed)\b",
    r"\bthis concludes (?:the|our) (?:meeting|interview|session)\b",
    r"\bmeeting is now officially closed\b",
)


def apply_explicit_closure(
    task_config: dict[str, Any], state: dict[str, Any], turn_text: dict[str, str]
) -> None:
    """Turn unambiguous public closure language into a terminal outcome."""
    if (state.get("outcome") or {}).get("type") in TERMINAL_OUTCOMES:
        return
    closure_evidence: list[dict[str, str]] = []
    for speaker_id, content in turn_text.items():
        normalized = " ".join(str(content or "").split())
        if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in _CLOSURE_PATTERNS):
            closure_evidence.append({"speaker_id": speaker_id, "quote": normalized[:500]})
    if not closure_evidence:
        return
    root = task_config.get("completion_conditions") or {"all": []}
    variables = state.get("variables") or {}
    results = [
        *[_condition_result(condition, variables) for condition in root.get("all", [])],
        *[_condition_result(condition, variables) for condition in root.get("any", [])],
    ]
    outcome_type = "completed" if conditions_met(root, variables) else (
        "conditional" if any(row["met"] for row in results) else "deferred"
    )
    state["outcome"] = {
        "type": outcome_type,
        "status": "explicit_closure",
        "reason": "Participants explicitly closed the current activity.",
        "evidence": closure_evidence,
    }


def apply_evaluator_updates(
    *,
    task_config: dict[str, Any],
    state: dict[str, Any],
    parsed: dict[str, Any],
    characters: list[CharacterTemplate],
    player_text: str,
    npc_turns: list[dict[str, str]],
    turn_id: int = 0,
) -> dict[str, Any]:
    """Apply untrusted model extraction through schema and authority checks."""
    schema = task_config.get("state_schema") or {}
    authorized: dict[str, set[str]] = {field: set() for field in schema}
    executable_fields: set[str] = set()
    for character in characters:
        for field in (character.authority or {}).get("can_confirm", []):
            if field in authorized:
                authorized[field].add(character.character_id)
        executable_fields.update((character.authority or {}).get("can_execute") or [])
    turn_text = {"user": player_text}
    turn_text.update({str(row.get("speaker_id")): str(row.get("content") or "") for row in npc_turns})
    variables = state.setdefault("variables", {})
    for update in parsed.get("updates", []) if isinstance(parsed.get("updates"), list) else []:
        field = update.get("field")
        if field not in schema or update.get("status") not in ALLOWED_STATUSES:
            continue
        value, value_valid = _coerce_value(update.get("value"), schema[field])
        if not value_valid:
            logger.warning("Ignoring invalid typed value for task field %s", field)
            continue
        current = variables.setdefault(field, {"value": None, "status": "unknown", "proposals": [], "confirmations": [], "evidence": []})
        evidence = [row for row in (update.get("evidence") or []) if isinstance(row, dict)]
        valid_evidence: list[dict[str, Any]] = []
        for row in evidence:
            speaker_id = "user" if row.get("speaker_id") == "player" else str(row.get("speaker_id") or "")
            quote = " ".join(str(row.get("quote") or "").split()).casefold()
            public_text = " ".join(turn_text.get(speaker_id, "").split()).casefold()
            if speaker_id and quote and quote in public_text:
                valid_evidence.append({**row, "speaker_id": speaker_id})
        if not _field_update_is_grounded(
            field=str(field), spec=schema[field], value=value,
            status=str(update.get("status") or ""), evidence=valid_evidence,
        ):
            logger.warning("Ignoring ungrounded evaluator update for task field %s", field)
            continue
        proposed_by = str(update.get("proposed_by") or "")
        if proposed_by == "player":
            proposed_by = "user"
        if not proposed_by and valid_evidence:
            proposed_by = str(valid_evidence[0]["speaker_id"])
        proposal = {"value": value, "proposed_by": proposed_by, "evidence": valid_evidence}
        configured_proposers = set(schema[field].get("propose_permissions") or [])
        if "player" in configured_proposers:
            configured_proposers.add("user")
        proposer_valid = not configured_proposers or proposed_by in configured_proposers
        if update["status"] in {"proposed", "disputed", "rejected"}:
            current.setdefault("proposals", []).append(proposal)
        claimed_confirmations = ["user" if speaker == "player" else str(speaker) for speaker in (update.get("confirmed_by") or [])]
        evidence_speakers = {str(row["speaker_id"]) for row in valid_evidence}
        confirmations = [speaker for speaker in dict.fromkeys(claimed_confirmations) if speaker in evidence_speakers]
        same_value = current.get("value") == value
        accumulated_confirmations = list(current.get("confirmations") or []) if same_value else []
        confirmations = list(dict.fromkeys([*accumulated_confirmations, *confirmations]))
        status = update["status"]
        policy = schema[field].get("confirmation_policy", "responsible_participant")
        has_player = "user" in confirmations
        has_authorized = bool(authorized[field].intersection(confirmations))
        configured_confirmers = set(schema[field].get("confirm_permissions") or [])
        if "player" in configured_confirmers:
            configured_confirmers.add("user")
        if configured_confirmers:
            confirmations = [speaker for speaker in confirmations if speaker in configured_confirmers]
            has_player = "user" in confirmations
            has_authorized = bool((authorized[field] | configured_confirmers).intersection(confirmations) - {"user", "player"})
        _commit_explicit_field_confirmations(
            field=str(field), spec=schema[field], value=value,
            confirmations=confirmations, evidence=valid_evidence,
            state=state, characters=characters, turn_id=turn_id,
        )
        confirmation_valid = {
            "player": has_player,
            "responsible_participant": has_authorized,
            "player_and_authorized_counterpart": has_player and has_authorized,
            "player_and_responsible_participant": has_player and has_authorized,
            "player_and_assignee": has_player and has_authorized,
        }.get(policy, False)
        if (
            status == "confirmed"
            and field in executable_fields
            and not ledger_has_support(
                state,
                kind="action",
                subject=str(field),
                field=str(field),
                minimum={"verified", "accepted"},
            )
        ):
            confirmation_valid = False
            current.setdefault("permission_violations", []).append({
                "action": "confirm_without_verified_public_action",
                "field": field,
                "claimed_by": confirmations,
                "turn_id": int(turn_id),
            })
        was_confirmed = current.get("status") == "confirmed"
        if was_confirmed and not same_value:
            challenge_speakers = {str(row["speaker_id"]) for row in valid_evidence}
            permitted_challenge = bool(
                challenge_speakers.intersection(authorized[field] | configured_confirmers | {"user"})
            )
            if status == "confirmed" and confirmation_valid:
                pass
            elif status in {"disputed", "rejected"} and permitted_challenge:
                current.setdefault("challenges", []).append({
                    "candidate_value": value,
                    "status": status,
                    "proposed_by": proposed_by,
                    "evidence": valid_evidence,
                    "turn_id": int(turn_id),
                })
                current["status"] = "disputed"
                current.setdefault("evidence", []).extend(valid_evidence)
                continue
            else:
                # A question or new proposal cannot silently reopen a settled
                # item. Keep it as audit evidence while preserving the public
                # confirmed value and status.
                current.setdefault("superseded_proposals", []).append({
                    **proposal,
                    "status": status,
                    "turn_id": int(turn_id),
                })
                continue
        if status == "confirmed" and not confirmation_valid:
            status = "proposed"
        if status == "confirmed" and confirmation_valid:
            current["value"] = value
        elif not proposer_valid and status in {"proposed", "disputed"}:
            status = "disputed"
            current.setdefault("permission_violations", []).append({"action": "propose", "speaker_id": proposed_by, "value": value})
        else:
            current["value"] = value
        if current.get("status") == "confirmed" and same_value and status == "proposed":
            status = "confirmed"
        current["status"] = status
        current["confirmations"] = confirmations
        current.setdefault("evidence", []).extend(valid_evidence)
    _commit_quote_level_confirmations(
        task_config=task_config, state=state, characters=characters,
        turn_text=turn_text, turn_id=turn_id,
    )
    apply_generic_events(state=state, parsed=parsed, turn_text=turn_text, turn_id=turn_id)
    _project_public_ledger(state)
    _project_field_ledger(task_config, state, characters)
    evaluate_conditions(task_config, state)
    reconcile_capability_boundary_closure(
        task_config, state, turn_id=turn_id,
    )
    apply_explicit_closure(task_config, state, turn_text)
    return evaluate_conditions(task_config, state)


async def update_task_state(
    db: AsyncSession,
    *,
    task_config: dict[str, Any],
    previous: dict[str, Any] | None,
    player_text: str,
    npc_turns: list[dict[str, str]],
    orchestration_config: dict[str, Any] | None,
    characters: list[CharacterTemplate],
    turn_id: int = 0,
) -> dict[str, Any]:
    state = deepcopy(previous) if previous else initial_task_state(task_config)
    llm_cfg = await orch_support.get_llm_config(db)
    evaluator = resolve_llm(llm_cfg, orchestration_config, "state_evaluator")
    config_view = _evaluator_config_view(task_config)
    state_view = _evaluator_state_view(state)
    prompt = f"""You are a neutral state evaluator for a multi-role task simulation.
Use only explicit evidence in the current turn. Never infer agreement from politeness, a question, a conditional offer, or silence.
Only emit fields present in state_schema. An empty updates array is valid when this turn contains no state change.
Scenario task schema:
{json.dumps(config_view, ensure_ascii=False)}
Previous public task state:
{json.dumps(state_view, ensure_ascii=False)}
Current player turn: {player_text}
Current participant replies:
{json.dumps(npc_turns, ensure_ascii=False)}

Also extract domain-neutral operational events. Distinguish a promise to provide
something (artifact_offered/action_committed) from actually providing or doing
it (artifact_submitted/action_completed). A statement such as "I will send it"
is never artifact_submitted. Use an explicit terminal outcome only when the
participants clearly close, defer, conditionally settle, fail, or abandon the
current activity. Emit at most four events and only for material changes in the
current turn. If an event concerns an existing work item, reuse that work item's
exact key and subject so that it is updated instead of duplicated. Never report
artifact_reviewed unless that same work item was actually submitted in a prior
or current public turn. Do not treat statements such as "attached", "sent", or
"uploaded" as artifact_submitted unless the public message also contains the
material artifact contents or previously established verifiable evidence. Do
not record invented links, hashes, measurements, approvals, or live-system
results as completed work.

For every operational event, set task_critical=true only when the public turn
shows that this exact item is indispensable to an unmet configured condition or
explicitly blocks truthful closure. A useful offer, optional follow-up, ordinary
attachment, or future improvement is not task-critical. State the short public
reason; unsupported criticality claims are ignored deterministically.

Return strict JSON only:
{{
  "phase": "one phase_id from task_config.phases",
  "updates": [{{
    "field": "a field in state_schema",
    "value": "typed value or null",
    "status": "unknown|proposed|disputed|confirmed|rejected",
    "proposed_by": "user or character_id",
    "confirmed_by": ["speaker ids that explicitly confirmed it"],
    "evidence": [{{"speaker_id":"...","quote":"short exact excerpt"}}]
  }}],
  "events": [{{
    "event_type": "information_provided|artifact_offered|artifact_submitted|artifact_reviewed|action_committed|action_completed|decision|blocker|handoff|schedule|outcome",
    "subject": "stable concise name for the information, artifact, action, decision, blocker, handoff, or schedule",
    "work_item_key": "exact existing work_items key for the same item, otherwise a new concise stable key",
    "status": "proposed|completed|blocked|rejected",
    "actor_id": "user or character_id",
    "target_id": "optional recipient character_id",
    "summary": "brief public summary",
    "task_critical": false,
    "criticality_reason": "why this item directly blocks an unmet condition or closure, otherwise empty",
    "evidence": [{{"speaker_id":"...","quote":"short exact excerpt"}}]
  }}],
  "outcome": null or {{
    "type": "completed|conditional|deferred|failed|stalled",
    "reason": "why the activity explicitly ended",
    "evidence": [{{"speaker_id":"...","quote":"short exact excerpt"}}]
  }}
}}
Follow each field's type and confirmation_policy. Preserve prior confirmed values unless explicit new evidence changes them.
{chr(10).join(task_config.get('evaluator_instructions') or [])}"""
    parsed: dict[str, Any] = {}
    for semantic_attempt in range(2):
        try:
            repair = (
                "\nYour previous response was unusable. Return one complete JSON object; "
                "use {\"updates\":[]} if there is no explicit update.\n"
                if semantic_attempt
                else ""
            )
            raw = await llm_client.chat_completion(
                [{"role": "user", "content": prompt + repair}],
                db_provider=evaluator.provider,
                db_model=evaluator.model,
                temperature=0.0,
                max_tokens=min(max(evaluator.max_tokens, 1800), 3200),
                response_format={"type": "json_object"},
            )
            candidate = normalize_evaluator_payload(raw)
            if isinstance(candidate.get("updates"), list):
                parsed = candidate
                break
            logger.warning("Task evaluator returned no usable updates: %s", raw[:2000])
        except Exception:
            logger.exception("Task evaluator attempt failed")
    if not parsed:
        logger.warning("Task evaluator failed; preserving the previous task state")

    return apply_evaluator_updates(
        task_config=task_config,
        state=state,
        parsed=parsed,
        characters=characters,
        player_text=player_text,
        npc_turns=npc_turns,
        turn_id=turn_id,
    )
