"""Condition-blinded, evidence-backed evaluation of simulation realism."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_client
from app.models.db import ScenarioTemplate
from app.orchestrator.common import orch_support
from app.orchestrator.llm_binding import resolve_llm

EVALUATOR_ATTEMPTS = 3

REALISM_DIMENSIONS: dict[str, list[str]] = {
    "role_strategic_fidelity": [
        "identity_consistency", "responsibility_consistency", "goal_interest_consistency",
        "behavioral_tendency_consistency", "role_boundary_discipline",
        "position_shift_justification",
    ],
    "epistemic_fidelity": [
        "protected_information_discipline", "cross_role_knowledge_separation",
        "knowledge_claim_grounding", "information_discovery_validity",
        "public_information_use_accuracy",
    ],
    "temporal_coherence": [
        "fact_retention", "agreement_recall", "contradiction_avoidance",
        "resolved_issue_retention", "long_horizon_reference_accuracy", "phase_continuity",
    ],
    "interaction_structure_fidelity": [
        "speaker_relevance", "interruption_discipline", "response_contingency",
        "turn_taking_plausibility", "role_responsibility_routing",
    ],
    "multi_party_dynamics_fidelity": [
        "role_differentiation", "distinct_contribution", "constructive_disagreement",
        "cross_role_coordination", "interest_conflict_plausibility",
        "evidence_based_concession", "consensus_timing", "overall_multi_party_believability",
    ],
    "procedural_fidelity": [
        "authority_discipline", "responsible_confirmation", "conditionality_preservation",
        "unresolved_issue_handling", "completion_timing", "completion_evidence_validity",
    ],
}


def _gold_specification(scenario: ScenarioTemplate, dispatch_rules: list[Any] | None = None) -> dict[str, Any]:
    return {
        "title": scenario.title,
        "description": scenario.description,
        "business_goal": scenario.business_goal,
        "player_side_goal": scenario.player_side_goal,
        "opponent_side_goal": scenario.opponent_side_goal,
        "phases": scenario.phases or [],
        "task_config": scenario.task_config or {},
        "dispatch_rules": [{
            "name": row.name, "trigger_keywords": row.trigger_keywords or [],
            "priority_character_ids": row.priority_character_ids or [],
            "min_speakers": row.min_speakers, "max_speakers": row.max_speakers,
        } for row in (dispatch_rules or [])],
        "characters": [{
            "character_id": row.character_id,
            "job_title": row.job_title,
            "responsibility": row.responsibility,
            "persona": row.persona,
            "tendency": row.tendency or {},
            "authority": row.authority or {},
            "private_state": row.private_state or {},
        } for row in sorted(scenario.characters, key=lambda item: item.sort_order)],
    }


def _public_transcript(
    messages: list[dict[str, Any]], *, turn_limit: int = 100, message_limit: int = 300
) -> list[dict[str, Any]]:
    source = [row for row in messages if row.get("speaker_type") in {"user", "npc"}]
    turn_ids = list(dict.fromkeys(row.get("turn_id") for row in source if row.get("turn_id") is not None))
    kept = set(turn_ids[-max(1, min(turn_limit, 100)):])
    if kept:
        source = [row for row in source if row.get("turn_id") in kept]
    return [{
        "sequence_no": row.get("sequence_no"), "turn_id": row.get("turn_id"),
        "speaker_id": row.get("speaker_id"), "content": str(row.get("content") or "")[:900],
    } for row in source][-max(1, min(message_limit, 300)):]


def _normalize_evaluation(raw: str) -> dict[str, Any] | None:
    parsed = orch_support.parse_json(raw)
    if not isinstance(parsed, dict):
        return None
    for wrapper in ("evaluation", "result", "metrics"):
        if isinstance(parsed.get(wrapper), dict):
            parsed = parsed[wrapper]
            break
    # New six-dimensional responses and legacy completion responses are both
    # accepted so old smoke tests and stored exports remain readable.
    if "dimension_score" not in parsed and "externally_validated_completion" not in parsed:
        return None
    return parsed


def _score(value: Any) -> float:
    try:
        return min(7.0, max(1.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def _dispatch_metrics(transcript: list[dict[str, Any]], rules: list[Any]) -> dict[str, Any]:
    """Condition-neutral keyword routing check from public turns and gold rules."""
    by_turn: dict[Any, list[dict[str, Any]]] = {}
    for row in transcript:
        by_turn.setdefault(row.get("turn_id"), []).append(row)
    expected_total = spoken_total = correct_total = eligible_turns = 0
    evidence: list[dict[str, Any]] = []
    for turn_id, rows in by_turn.items():
        player_text = " ".join(str(r.get("content") or "") for r in rows if r.get("speaker_id") == "user").casefold()
        spoken = {str(r.get("speaker_id")) for r in rows if r.get("speaker_id") != "user"}
        expected: list[str] = []
        for rule in rules:
            if any(str(keyword).casefold() in player_text for keyword in (rule.trigger_keywords or [])):
                limit = max(1, int(rule.max_speakers or len(rule.priority_character_ids or []) or 1))
                expected.extend(str(cid) for cid in (rule.priority_character_ids or [])[:limit])
        expected_set = set(expected)
        if not expected_set:
            continue
        eligible_turns += 1
        correct = spoken & expected_set
        expected_total += len(expected_set)
        spoken_total += len(spoken)
        correct_total += len(correct)
        evidence.append({"turn_id": turn_id, "expected": sorted(expected_set), "spoken": sorted(spoken)})
    return {
        "eligible_turn_count": eligible_turns,
        "dispatch_precision": correct_total / spoken_total if spoken_total else None,
        "dispatch_recall": correct_total / expected_total if expected_total else None,
        "evidence": evidence,
    }


async def _evaluate_dimension(
    *, dimension: str, metrics: list[str], gold: dict[str, Any], transcript: list[dict[str, Any]],
    system_claim: dict[str, Any], provider: str, model: str, max_tokens: int,
) -> dict[str, Any]:
    prompt = f"""You are an independent, condition-blinded judge of multi-party business
simulation realism. You did not generate this dialogue. Evaluate only the dimension
{dimension}. More turns, more conflict, and task success are NOT inherently more realistic.
Judge appropriateness against the role, information, temporal, interaction, and procedural
specification. A score of 1 means clearly unrealistic, 4 mixed/adequate, and 7 highly
realistic. Every metric must cite public transcript sequence numbers. Private state is gold
reference only: do not reward merely repeating it and do not expose it in the reason.

Gold specification:
{json.dumps(gold, ensure_ascii=False)}

Public transcript:
{json.dumps(transcript, ensure_ascii=False)}

System claim (untrusted):
{json.dumps(system_claim, ensure_ascii=False)}

Return strict JSON only:
{{"dimension_score":4,"metrics":{{{','.join(json.dumps(name)+':{"score":4,"evidence_sequence_nos":[],"reason":"brief"}' for name in metrics)}}},"strengths":[],"issues":[],"notes":"brief"}}
Do not add metrics or omit metrics."""
    for attempt in range(EVALUATOR_ATTEMPTS):
        suffix = "" if not attempt else "\nReturn one complete JSON object only; no Markdown or prose."
        raw = await llm_client.chat_completion(
            [{"role": "user", "content": prompt + suffix}],
            db_provider=provider, db_model=model, temperature=0.0,
            max_tokens=min(max(max_tokens, 1800 + attempt * 300), 3200),
            response_format={"type": "json_object"},
        )
        parsed = _normalize_evaluation(raw)
        if parsed and "dimension_score" in parsed:
            normalized_metrics: dict[str, Any] = {}
            source_metrics = parsed.get("metrics") if isinstance(parsed.get("metrics"), dict) else {}
            for name in metrics:
                row = source_metrics.get(name) if isinstance(source_metrics.get(name), dict) else {}
                normalized_metrics[name] = {
                    "score": _score(row.get("score")),
                    "evidence_sequence_nos": row.get("evidence_sequence_nos")
                    if isinstance(row.get("evidence_sequence_nos"), list) else [],
                    "reason": str(row.get("reason") or "")[:800],
                }
            parsed["metrics"] = normalized_metrics
            parsed["dimension_score"] = _score(parsed.get("dimension_score"))
            return parsed
        if attempt < EVALUATOR_ATTEMPTS - 1:
            await asyncio.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"External evaluator returned unusable JSON for {dimension}")


async def evaluate_public_transcript(
    db: AsyncSession, *, scenario: ScenarioTemplate, messages: list[dict[str, Any]],
    system_claim: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate six realism dimensions in separate bounded calls for resilience."""
    llm_cfg = await orch_support.get_llm_config(db)
    resolved = resolve_llm(llm_cfg, scenario.orchestration_config, "external_evaluator")
    transcript = _public_transcript(messages)
    dispatch_rules = await orch_support.load_dispatch_rules(db, scenario.id)
    gold = _gold_specification(scenario, dispatch_rules)
    dimensions: dict[str, Any] = {}
    evaluation_errors: dict[str, str] = {}
    for dimension, metrics in REALISM_DIMENSIONS.items():
        try:
            dimensions[dimension] = await _evaluate_dimension(
                dimension=dimension, metrics=metrics, gold=gold, transcript=transcript,
                system_claim=system_claim, provider=resolved.provider, model=resolved.model,
                max_tokens=resolved.max_tokens,
            )
        except Exception as exc:
            # One malformed judge response must not discard a completed dialogue
            # or the five other independent realism dimensions.
            evaluation_errors[dimension] = f"{type(exc).__name__}: {exc}"[:1000]
            dimensions[dimension] = {
                "dimension_score": None,
                "metrics": {name: {
                    "score": None, "evidence_sequence_nos": [],
                    "reason": "Evaluation unavailable after retries",
                } for name in metrics},
                "strengths": [], "issues": [], "notes": evaluation_errors[dimension],
                "status": "evaluation_failed",
            }

    result: dict[str, Any] = {
        "protocol": "blinded-six-dimension-realism-v3",
        "condition_hidden": True,
        "observer_model": resolved.label(),
        "evaluated_public_message_count": len(transcript),
        "dimensions": dimensions,
        "dimension_scores": {name: row["dimension_score"] for name, row in dimensions.items()},
        "evaluation_errors": evaluation_errors,
        "notes": "Six dimensions are reported separately; no composite realism score is computed.",
        "deterministic_metrics": {"dispatch": _dispatch_metrics(transcript, dispatch_rules)},
    }
    # Backward-compatible procedural fields used by older exports/UI.
    procedural = dimensions["procedural_fidelity"]["metrics"]
    completion_score = procedural["completion_evidence_validity"]["score"]
    result["externally_validated_completion"] = (
        completion_score >= 5 if completion_score is not None else False
    )
    result["system_declared_complete"] = bool(system_claim.get("declared_complete"))
    result["premature_completion"] = bool(
        result["system_declared_complete"]
        and procedural["completion_timing"]["score"] is not None
        and procedural["completion_timing"]["score"] < 4
    )
    return result
