"""Schema-driven task-state extraction and deterministic completion evaluation."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.models.db import CharacterTemplate


ALLOWED_STATUSES = {"unknown", "proposed", "disputed", "confirmed", "rejected"}
logger = logging.getLogger(__name__)


def task_progress_signature(task_state: dict[str, Any] | None) -> str:
    """Stable, evidence-free signature used to detect real task progress."""
    state = task_state or {}
    variables = state.get("variables") or {}
    compact = {
        "phase": state.get("phase"),
        "completion_status": state.get("completion_status"),
        "variables": {
            field: {
                "value": item.get("value"),
                "status": item.get("status"),
                "confirmations": sorted(set(item.get("confirmations") or [])),
            }
            for field, item in sorted(variables.items())
            if isinstance(item, dict)
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
        "schema_version": 2,
        "phase": first,
        "completion_status": "in_progress",
        "variables": variables,
        "open_issues": list(variables),
        "condition_results": [],
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
    task_state["completion_status"] = "completed" if complete and (all_results or any_results) else "in_progress"
    task_state["open_issues"] = [name for name, value in variables.items() if value.get("status") != "confirmed"]
    advance_phase(task_config, task_state)
    return task_state


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
  }}]
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
