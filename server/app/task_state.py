"""Schema-driven task-state extraction and deterministic completion evaluation."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm
from app.models.db import CharacterTemplate


ALLOWED_STATUSES = {"unknown", "proposed", "disputed", "confirmed", "rejected"}


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
    prompt = f"""You are a neutral state evaluator for a multi-role task simulation.
Use only explicit evidence in the current turn. Never infer agreement from politeness, a question, a conditional offer, or silence.
Scenario task configuration:
{json.dumps(task_config, ensure_ascii=False)}
Previous task state:
{json.dumps(state, ensure_ascii=False)}
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
    try:
        raw = await llm_client.chat_completion(
            [{"role": "user", "content": prompt}],
            db_provider=evaluator.provider,
            db_model=evaluator.model,
            temperature=0.0,
            max_tokens=min(evaluator.max_tokens, 900),
            response_format={"type": "json_object"},
        )
        parsed = normalize_evaluator_payload(raw)
    except Exception:
        parsed = {}

    schema = task_config.get("state_schema") or {}
    authorized: dict[str, set[str]] = {field: set() for field in schema}
    for character in characters:
        for field in (character.authority or {}).get("can_confirm", []):
            if field in authorized:
                authorized[field].add(character.character_id)
    variables = state.setdefault("variables", {})
    for update in parsed.get("updates", []) if isinstance(parsed.get("updates"), list) else []:
        field = update.get("field")
        if field not in schema or update.get("status") not in ALLOWED_STATUSES:
            continue
        current = variables.setdefault(field, {"value": None, "status": "unknown", "proposals": [], "confirmations": [], "evidence": []})
        proposal = {"value": update.get("value"), "proposed_by": update.get("proposed_by"), "evidence": update.get("evidence") or []}
        proposed_by = str(update.get("proposed_by") or "")
        configured_proposers = set(schema[field].get("propose_permissions") or [])
        if "player" in configured_proposers:
            configured_proposers.add("user")
        proposer_valid = not configured_proposers or proposed_by in configured_proposers
        if update["status"] in {"proposed", "disputed", "rejected"}:
            current.setdefault("proposals", []).append(proposal)
        confirmations = list(dict.fromkeys(update.get("confirmed_by") or []))
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
        if not proposer_valid and status in {"proposed", "disputed", "confirmed"}:
            status = "disputed"
            current.setdefault("permission_violations", []).append({"action": "propose", "speaker_id": proposed_by, "value": update.get("value")})
        else:
            current["value"] = update.get("value")
        current["status"] = status
        current["confirmations"] = confirmations
        current.setdefault("evidence", []).extend(update.get("evidence") or [])
    return evaluate_conditions(task_config, state)
