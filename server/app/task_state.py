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
logger = logging.getLogger(__name__)


def _subject_key(value: Any) -> str:
    words = re.findall(r"[\w\-]+", str(value or "").casefold(), flags=re.UNICODE)
    return "_".join(words[:12])[:96] or "unspecified"


def _work_key_tokens(value: Any) -> set[str]:
    return {
        word for word in _subject_key(value).split("_")
        if word and word not in _WORK_KEY_QUALIFIERS
    }


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
    }
    return json.dumps(compact, ensure_ascii=False, sort_keys=True, default=str)


def public_task_result(task_state: dict[str, Any] | None) -> dict[str, Any]:
    """Expose auditable outcomes without private prompts, reasoning, or memories."""
    state = task_state or {}
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
        "recent_events": deepcopy((state.get("event_ledger") or [])[-30:]),
        "outcome": deepcopy(state.get("outcome") or {}),
        "progress": deepcopy(state.get("progress") or {}),
    }


def _evaluator_state_view(state: dict[str, Any]) -> dict[str, Any]:
    """Keep the evaluator prompt bounded as proposals/evidence accumulate."""
    return public_task_result(state)


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
            number = int(value)
            return number, float(value) == number
        except (TypeError, ValueError):
            return value, False
    if kind == "number":
        if isinstance(value, bool):
            return value, False
        try:
            return float(value), True
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
        "schema_version": 4,
        "phase": first,
        "completion_status": "in_progress",
        "variables": variables,
        "open_issues": list(variables),
        "condition_results": [],
        "event_ledger": [],
        "work_items": {},
        "outcome": {"type": None, "status": "open", "reason": "", "evidence": []},
        "progress": {"stagnant_turns": 0, "last_progress_turn": 0},
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
    root = task_config.get("completion_conditions") or {"all": []}
    variables = task_state.get("variables") or {}
    all_results = [_condition_result(c, variables) for c in root.get("all", [])]
    any_results = [_condition_result(c, variables) for c in root.get("any", [])]
    complete = all(r["met"] for r in all_results) and (not any_results or any(r["met"] for r in any_results))
    task_state["condition_results"] = all_results + any_results
    explicit_outcome = (task_state.get("outcome") or {}).get("type")
    if complete and (all_results or any_results):
        task_state["completion_status"] = "completed"
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


def apply_generic_events(
    *, state: dict[str, Any], parsed: dict[str, Any], turn_text: dict[str, str]
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
        signature = (event_type, key, status, actor_id)
        if signature in existing:
            continue
        item = dict(work_items.get(key) or {})
        milestones = set(item.get("milestones") or [])
        transition_valid = not (
            event_type == "artifact_reviewed" and "artifact_submitted" not in milestones
        )
        event = {
            "event_index": next_event_index,
            "event_type": event_type, "subject": subject, "subject_key": key,
            "status": status, "actor_id": actor_id,
            "target_id": str(raw.get("target_id") or ""),
            "summary": str(raw.get("summary") or subject).strip()[:500],
            "evidence": evidence,
            "transition_valid": transition_valid,
        }
        next_event_index += 1
        if not transition_valid:
            event["transition_error"] = "artifact_review_requires_prior_submission"
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
        })
        milestones.add(event_type)
        item["milestones"] = sorted(milestones)
        if event_type in {"blocker", "artifact_offered", "action_committed"}:
            item["required"] = True
        if event_type == "artifact_offered":
            if item.get("status") not in {"blocked", "submitted", "completed"}:
                item["status"] = "promised"
        elif event_type == "artifact_submitted":
            item["status"] = "submitted"
        elif event_type in {"artifact_reviewed", "action_completed"}:
            item["status"] = "completed"
        elif event_type == "information_provided":
            # Describing a requirement or blocker is useful information, but
            # does not itself satisfy an already required artifact/action.
            if not item.get("required") or item.get("status") not in {"blocked", "promised"}:
                item["status"] = "completed"
        elif event_type == "outcome":
            item["status"] = "completed" if status == "completed" else status
        elif event_type in {"decision", "handoff", "schedule"}:
            item["status"] = "completed" if status == "completed" else "proposed"
            if status != "completed":
                item["required"] = True
        elif event_type == "action_committed":
            if item.get("status") not in {"blocked", "completed"}:
                item["status"] = "promised"
        elif event_type == "blocker":
            item["status"] = "blocked"
        work_items[key] = item
    state["event_ledger"] = ledger[-100:]

    raw_outcome = parsed.get("outcome")
    if isinstance(raw_outcome, dict) and str(raw_outcome.get("type") or "") in TERMINAL_OUTCOMES:
        evidence = _valid_public_evidence(raw_outcome.get("evidence"), turn_text)
        if evidence:
            state["outcome"] = {
                "type": str(raw_outcome["type"]), "status": "explicit",
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
) -> dict[str, Any]:
    """Apply untrusted model extraction through schema and authority checks."""
    schema = task_config.get("state_schema") or {}
    authorized: dict[str, set[str]] = {field: set() for field in schema}
    for character in characters:
        for field in (character.authority or {}).get("can_confirm", []):
            if field in authorized:
                authorized[field].add(character.character_id)
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
        confirmation_valid = {
            "player": has_player,
            "responsible_participant": has_authorized,
            "player_and_authorized_counterpart": has_player and has_authorized,
            "player_and_responsible_participant": has_player and has_authorized,
            "player_and_assignee": has_player and has_authorized,
        }.get(policy, False)
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
    apply_generic_events(state=state, parsed=parsed, turn_text=turn_text)
    evaluate_conditions(task_config, state)
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
or current public turn.

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
    )
