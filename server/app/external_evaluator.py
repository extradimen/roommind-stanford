"""Post-hoc blinded semantic evaluation that never participates in dialogue."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.db import ScenarioTemplate
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm


def _gold_specification(scenario: ScenarioTemplate) -> dict[str, Any]:
    return {
        "title": scenario.title,
        "description": scenario.description,
        "task_config": scenario.task_config or {},
        "characters": [
            {
                "character_id": row.character_id,
                "job_title": row.job_title,
                "responsibility": row.responsibility,
                "persona": row.persona,
                "authority": row.authority or {},
                # Private facts are supplied only to the observer so it can detect
                # leakage. The requested output may cite message IDs but not repeat
                # undisclosed private facts.
                "private_state": row.private_state or {},
            }
            for row in sorted(scenario.characters, key=lambda item: item.sort_order)
        ],
    }


EVALUATOR_ATTEMPTS = 3


def _public_transcript(messages: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    rows = [
        {
            "sequence_no": row.get("sequence_no"),
            "turn_id": row.get("turn_id"),
            "speaker_id": row.get("speaker_id"),
            "content": str(row.get("content") or "")[:900],
        }
        for row in messages
        if row.get("speaker_type") in {"user", "npc"}
    ]
    return rows[-max(1, min(limit, 100)):]


def _normalize_evaluation(raw: str) -> dict[str, Any] | None:
    """Accept harmless wrappers while rejecting prose or incomplete output."""
    parsed = orch_support.parse_json(raw)
    if not isinstance(parsed, dict):
        return None
    for wrapper in ("evaluation", "result", "metrics"):
        nested = parsed.get(wrapper)
        if isinstance(nested, dict):
            parsed = nested
            break
    if "externally_validated_completion" not in parsed:
        return None
    return parsed


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "yes", "1"}
    return bool(value)


async def evaluate_public_transcript(
    db: AsyncSession,
    *,
    scenario: ScenarioTemplate,
    messages: list[dict[str, Any]],
    system_claim: dict[str, Any],
) -> dict[str, Any]:
    """Return evidence-backed metrics while hiding the evaluated condition."""
    llm_cfg = await orch_support.get_llm_config(db)
    resolved = resolve_llm(llm_cfg, scenario.orchestration_config, "external_evaluator")
    prompt = f"""You are a blinded external observer evaluating a multi-role dialogue.
You did not participate in the dialogue. Do not assume the system's completion
claim is correct. Use only the gold specification and public transcript as
evidence. Conditional agreement is not final agreement. Silence, praise, and
politeness are not confirmation. Cite sequence numbers for every detected issue.
Do not reveal or quote a private fact unless it already appears in the transcript.

Gold specification:
{json.dumps(_gold_specification(scenario), ensure_ascii=False)}

Public transcript:
{json.dumps(_public_transcript(messages), ensure_ascii=False)}

System's own claim (not ground truth):
{json.dumps(system_claim, ensure_ascii=False)}

Return strict JSON only using this schema:
{{
  "externally_validated_completion": false,
  "first_valid_completion_turn": null,
  "premature_completion": false,
  "total_confirmation_count": 0,
  "authority_violations": [{{"sequence_no":1,"speaker_id":"...","field":"..."}}],
  "private_information_leaks": [{{"sequence_no":1,"speaker_id":"...","private_owner":"..."}}],
  "contradictions": [{{"sequence_nos":[1,2],"reason":"..."}}],
  "semantic_repetitions": [{{"sequence_nos":[1,2],"reason":"..."}}],
  "responsibility_match_rate": 0.0,
  "distinct_contribution_rate": 0.0,
  "role_consistency": {{"speaker_id": 1}},
  "closure_coherence": 1,
  "completion_evidence_sequence_nos": [],
  "notes": "brief evidence-based summary"
}}
Rates must be between 0 and 1. Role consistency and closure coherence use 1-5.
Use empty arrays when there are no violations."""
    parsed: dict[str, Any] | None = None
    last_shape = "empty"
    for attempt in range(EVALUATOR_ATTEMPTS):
        retry_instruction = ""
        if attempt:
            retry_instruction = (
                "\nYour previous response could not be parsed. Return exactly one complete JSON "
                "object. Do not use Markdown, prose, comments, or an outer wrapper."
            )
        raw = await llm_client.chat_completion(
            [{"role": "user", "content": prompt + retry_instruction}],
            db_provider=resolved.provider,
            db_model=resolved.model,
            temperature=0.0,
            max_tokens=min(max(resolved.max_tokens, 2600 + attempt * 500), 4096),
            response_format={"type": "json_object"},
        )
        parsed = _normalize_evaluation(raw)
        if parsed is not None:
            break
        last_shape = f"nonempty={bool(raw.strip())}, chars={len(raw)}"
        if attempt < EVALUATOR_ATTEMPTS - 1:
            await asyncio.sleep(0.5 * (attempt + 1))
    if parsed is None:
        raise RuntimeError(
            "External evaluator returned unusable JSON after "
            f"{EVALUATOR_ATTEMPTS} attempts ({last_shape})"
        )
    transcript = _public_transcript(messages)
    npc_message_count = sum(1 for row in messages if row.get("speaker_type") == "npc")
    public_message_count = len(transcript)
    parsed["externally_validated_completion"] = _as_bool(
        parsed.get("externally_validated_completion")
    )
    parsed["premature_completion"] = _as_bool(parsed.get("premature_completion"))
    for key in (
        "authority_violations",
        "private_information_leaks",
        "contradictions",
        "semantic_repetitions",
        "completion_evidence_sequence_nos",
    ):
        if not isinstance(parsed.get(key), list):
            parsed[key] = []
    try:
        confirmation_count = max(0, int(parsed.get("total_confirmation_count") or 0))
    except (TypeError, ValueError):
        confirmation_count = 0
    parsed["total_confirmation_count"] = confirmation_count
    parsed["authority_violation_count"] = len(parsed["authority_violations"])
    parsed["authority_violation_rate"] = (
        len(parsed["authority_violations"]) / confirmation_count if confirmation_count else 0.0
    )
    parsed["private_information_leakage_count"] = len(parsed["private_information_leaks"])
    parsed["private_information_leakage_rate"] = (
        len(parsed["private_information_leaks"]) / npc_message_count if npc_message_count else 0.0
    )
    parsed["contradiction_count"] = len(parsed["contradictions"])
    parsed["contradiction_rate"] = (
        len(parsed["contradictions"]) / public_message_count if public_message_count else 0.0
    )
    repeated_sequence_nos = {
        int(sequence_no)
        for group in parsed["semantic_repetitions"]
        if isinstance(group, dict)
        for sequence_no in (group.get("sequence_nos") or [])
        if str(sequence_no).isdigit()
    }
    parsed["semantic_repetition_count"] = len(repeated_sequence_nos)
    parsed["semantic_repetition_rate"] = (
        len(repeated_sequence_nos) / public_message_count if public_message_count else 0.0
    )
    parsed["protocol"] = "blinded-semantic-observer-v1"
    parsed["observer_model"] = resolved.label()
    parsed["condition_hidden"] = True
    parsed["evaluation_attempts"] = attempt + 1
    parsed["evaluated_public_message_count"] = public_message_count
    return parsed
