"""Persistent, restart-resumable batch experiments for autonomous comparisons."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import random
import time
import traceback
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database import async_session_factory
from app.external_evaluator import evaluate_public_transcript
from app.external_observer import build_blinded_evaluation_packet
from app.memory.service import memory_service
from app.models.db import BatchExperiment, BatchExperimentRun, BatchHumanReview, ScenarioTemplate
from app.orchestrator.common import orch_support
from app.research_protocol import (
    CURRENT_ARCHITECTURE_VERSION,
    CURRENT_GENERATION_ID,
    HUMAN_REVIEW_PROTOCOL_VERSION,
    REALISM_RUBRIC,
    STUDY_PHASES,
    experiment_manifest,
    transcript_provenance,
)
from app.research_probes import run_integrity_probes
from app.session_export import build_public_session_export_bundle, build_session_export_bundle
from app.telemetry import emit, monotonic_ms, telemetry_context

router = APIRouter(prefix="/api/game/batch-experiments", tags=["batch-experiments"])

DEFAULT_CONCURRENCY = 2
MAX_CONCURRENCY = 4
MAX_RUNS_PER_BATCH = 500
_tasks: dict[str, asyncio.Task] = {}
_evaluation_tasks: dict[str, asyncio.Task] = {}
_retry_tasks: dict[int, asyncio.Task] = {}
_global_run_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
logger = logging.getLogger(__name__)
AUTONOMOUS_STEP_TIMEOUT_SECONDS = 900
EXTERNAL_EVALUATION_TIMEOUT_SECONDS = 1800


class BatchCreateIn(BaseModel):
    name: str = Field(default="Batch experiment", min_length=1, max_length=256)
    scenario_ids: list[int] = Field(min_length=1)
    conditions: list[str] = Field(min_length=1)
    repetitions: int = Field(default=10, ge=1, le=100)
    concurrency: int = Field(default=DEFAULT_CONCURRENCY, ge=1, le=MAX_CONCURRENCY)
    safety_max_turns: int = Field(default=50, ge=10, le=100)
    max_stagnant_turns: int = Field(default=8, ge=4, le=25)
    locale: str | None = None
    random_seed: int = Field(default=20260728, ge=0, le=2_147_483_647)
    human_validation_enabled: bool = True
    study_phase: str = "exploration"


REALISM_DIMENSIONS = [
    "role_strategic_fidelity", "epistemic_fidelity", "temporal_coherence",
    "interaction_structure_fidelity", "multi_party_dynamics_fidelity", "procedural_fidelity",
]


class HumanReviewIn(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=128)
    ratings: dict[str, float]
    evidence: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=8000)
    transcript_sha256: str = Field(min_length=64, max_length=64)
    indicator_ratings: dict[str, float] = Field(default_factory=dict)
    reviewer_profile: dict[str, Any] = Field(default_factory=dict)
    interface_locale: str = Field(default="zh-CN", max_length=16)
    finalize: bool = True


class EvaluationStartIn(BaseModel):
    run_ids: list[int] | None = None
    retry_all: bool = False
    concurrency: int = Field(default=1, ge=1, le=4)


def _dialogue_retry_result(run: BatchExperimentRun) -> dict[str, Any]:
    """Build a fresh run result while retaining a compact audit trail."""
    previous = dict(run.result or {})
    history = list(previous.get("dialogue_retry_history") or [])
    attempt_count = max(1, int(previous.get("dialogue_attempt_count") or 1))
    history.append({
        "attempt_number": attempt_count,
        "status": previous.get("dialogue_status") or run.status,
        "session_uuid": run.session_uuid,
        "error": run.error or previous.get("error"),
        "failure_stage": previous.get("failure_stage"),
        "exception_type": previous.get("exception_type"),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    })
    return {
        "dialogue_status": "queued",
        "evaluation_status": "not_started",
        "dialogue_attempt_count": attempt_count + 1,
        "dialogue_retry_history": history,
        "dialogue_retry_queued_at": _now().isoformat(),
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _performance_summary(trace: list[dict[str, Any]]) -> dict[str, Any]:
    events = [event for row in trace for event in (row.get("llm_events") or [])]
    successes = [event for event in events if event.get("event") == "llm.request.succeeded"]
    return {
        "recorded_stage_count": len(trace),
        "total_stage_duration_ms": sum(int(row.get("duration_ms") or 0) for row in trace),
        "llm_request_attempt_count": sum(
            event.get("event") == "llm.request.started" for event in events
        ),
        "llm_success_count": len(successes),
        "llm_retry_event_count": sum(
            event.get("event") in {
                "llm.request.length_retry",
                "llm.request.empty_retry",
                "llm.request.http_retry",
                "llm.request.transport_error",
            }
            and bool(event.get("retrying", True))
            for event in events
        ),
        "llm_degraded_fallback_count": sum(
            event.get("event") == "llm.degraded_fallback" for event in events
        ),
        "dialogue_safe_fallback_count": sum(
            event.get("event") == "dialogue.safe_fallback.used" for event in events
        ),
        "dialogue_silent_recovery_count": sum(
            event.get("event") == "dialogue.silent_recovery.used" for event in events
        ),
        "dialogue_validated_draft_count": sum(
            event.get("event") == "dialogue.validated_draft.used" for event in events
        ),
        "dialogue_public_clause_repair_count": sum(
            event.get("event") == "dialogue.public_clause_repair.used" for event in events
        ),
        "dialogue_near_duplicate_suppression_count": sum(
            event.get("event") == "dialogue.near_duplicate.suppressed" for event in events
        ),
        "dialogue_floor_handoff_count": sum(
            event.get("event") == "dialogue.floor_handoff.to_player" for event in events
        ),
        "dialogue_speech_act_mismatch_rejection_count": sum(
            event.get("event") == "llm.public_output.rejected"
            and event.get("rejection_reason") == "speech_act_mismatch"
            for event in events
        ),
        "quote_confirmation_commit_count": sum(
            event.get("event") == "task_state.quote_confirmation.committed" for event in events
        ),
        "public_grounding_rejection_count": sum(
            event.get("event") == "llm.public_output.rejected"
            and (
                str(event.get("rejection_reason") or "").startswith("unsupported_")
                or str(event.get("rejection_reason") or "")
                == "current_world_completion_requires_simulated_tool_result"
            )
            for event in events
        ),
        "llm_total_duration_ms": sum(int(event.get("duration_ms") or 0) for event in successes),
        "prompt_tokens": sum(int(event.get("prompt_tokens") or 0) for event in successes),
        "completion_tokens": sum(int(event.get("completion_tokens") or 0) for event in successes),
        "total_tokens": sum(int(event.get("total_tokens") or 0) for event in successes),
    }


def _coordination_summary(
    task_result: dict[str, Any] | None,
    shared_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic G2 process measures; never infer dialogue realism."""
    task = task_result or {}
    history = [
        row for row in (task.get("coordination_history") or [])
        if isinstance(row, dict)
    ]
    focuses = [row.get("focus") for row in history if isinstance(row.get("focus"), dict)]
    test_state = (shared_state or {}).get("_test_state") or {}
    boundaries = task.get("capability_boundaries") or {}
    closure_lock = task.get("closure_lock") or {}
    outcome = task.get("outcome") or {}
    return {
        "coordinator_focus_turn_count": len(focuses),
        "coordinator_due_focus_turn_count": sum(bool(row.get("due_now")) for row in focuses),
        "coordinator_closeout_turn_count": sum(
            bool(row.get("closeout_required")) for row in history
        ),
        "coordinator_distinct_focus_count": len({
            str(row.get("issue")) for row in focuses if row.get("issue")
        }),
        "coordinator_focus_rotation_count": sum(
            bool(row.get("rotated_from_issue")) for row in focuses
        ),
        "coordinator_outcome_resolution_count": sum(
            row.get("kind") in {"outcome", "outcome_resolution"} for row in focuses
        ),
        "coordinator_task_critical_work_focus_count": sum(
            row.get("kind") == "work_item" for row in focuses
        ),
        "coordinator_task_critical_focus_count": sum(
            row.get("kind") in {"state_variable", "work_item", "capability_boundary"}
            for row in focuses
        ),
        "coordinator_capability_boundary_count": sum(
            row.get("kind") == "capability_boundary" for row in focuses
        ),
        "persistent_capability_boundary_count": sum(
            isinstance(row, dict) and row.get("status") == "unavailable"
            for row in boundaries.values()
        ),
        "capability_boundary_closure": (
            outcome.get("status") == "capability_boundary_reconciled"
        ),
        "governor_bounded_close": (
            outcome.get("status") == "governor_bounded_close"
        ),
        "authoritative_closure_lock": closure_lock.get("status") == "locked",
        "closure_reconciled_work_item_count": sum(
            isinstance(item, dict) and bool(item.get("closure_superseded_by_fields"))
            for item in (task.get("work_items") or {}).values()
        ),
        "task_critical_work_item_count": sum(
            isinstance(item, dict) and item.get("required") is True
            for item in (task.get("work_items") or {}).values()
        ),
        "incidental_work_item_count": sum(
            isinstance(item, dict) and item.get("required") is not True
            for item in (task.get("work_items") or {}).values()
        ),
        "final_completion_status": task.get("completion_status"),
        "final_open_issue_count": len(task.get("open_issues") or []),
        "governor_stop_reason": test_state.get("stop_reason"),
    }


def _flatten_result(
    *,
    scenario: ScenarioTemplate,
    condition: str,
    repetition: int,
    session_uuid: str,
    session_status: str,
    message_count: int,
    turn_count: int,
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "scenario_id": scenario.id,
        "scenario_slug": scenario.slug,
        "scenario_title": scenario.title,
        "condition": "roommind" if condition == "test" else "baseline",
        "session_mode": condition,
        "repetition": repetition,
        "matched_pair_id": f"{scenario.slug}:r{repetition}",
        "session_uuid": session_uuid,
        "session_status": session_status,
        "message_count": message_count,
        "turn_count": turn_count,
        "externally_validated_completion": bool(evaluation.get("externally_validated_completion")),
        "premature_completion": bool(evaluation.get("premature_completion")),
        "first_valid_completion_turn_id": evaluation.get("first_valid_completion_turn_id"),
        "valid_confirmation_count": int(evaluation.get("valid_confirmation_count") or 0),
        "responsible_confirmation_count": int(
            evaluation.get("responsible_confirmation_count") or 0
        ),
        "responsible_confirmer_rate": _optional_float(
            evaluation.get("responsible_confirmer_rate")
        ),
        "authority_violation_count": int(evaluation.get("authority_violation_count") or 0),
        "authority_violation_rate": _optional_float(evaluation.get("authority_violation_rate")),
        "protected_secret_leakage_count": int(
            evaluation.get("protected_secret_leakage_count") or 0
        ),
        "protected_secret_leakage_rate": _optional_float(
            evaluation.get("protected_secret_leakage_rate")
        ),
        "cross_role_knowledge_contamination_count": int(
            evaluation.get("cross_role_knowledge_contamination_count") or 0
        ),
        "cross_role_knowledge_contamination_rate": _optional_float(
            evaluation.get("cross_role_knowledge_contamination_rate")
        ),
        "agreement_reversal_count": int(evaluation.get("agreement_reversal_count") or 0),
        "agreement_retention_rate": _optional_float(evaluation.get("agreement_retention_rate")),
        "semantic_repetition_count": int(evaluation.get("semantic_repetition_count") or 0),
        "semantic_repetition_rate": float(evaluation.get("semantic_repetition_rate") or 0),
        "responsibility_match_rate": _optional_float(evaluation.get("responsibility_match_rate")),
        "distinct_contribution_rate": _optional_float(evaluation.get("distinct_contribution_rate")),
        "observer_model": evaluation.get("observer_model"),
        "evaluation_protocol": evaluation.get("protocol"),
        "notes": evaluation.get("notes") or "",
    }
    dimension_scores = evaluation.get("dimension_scores") or {}
    for dimension in REALISM_DIMENSIONS:
        row[f"ai_{dimension}"] = _optional_float(dimension_scores.get(dimension))
    row["realism_dimensions"] = evaluation.get("dimensions") or {}
    dispatch = ((evaluation.get("deterministic_metrics") or {}).get("dispatch") or {})
    row["dispatch_precision"] = _optional_float(dispatch.get("dispatch_precision"))
    row["dispatch_recall"] = _optional_float(dispatch.get("dispatch_recall"))
    return row


async def _batch_cancelled(batch_id: int) -> bool:
    async with async_session_factory() as db:
        batch = await db.get(BatchExperiment, batch_id)
        return not batch or batch.status in {"cancelling", "cancelled"}


async def _record_run_heartbeat(
    run_id: int,
    *,
    turn_index: int,
    step_attempt: int,
    stage: str,
) -> None:
    """Persist worker liveness independently from the long dialogue transaction."""
    async with async_session_factory() as db:
        run = await db.get(BatchExperimentRun, run_id)
        if not run or run.status != "running":
            return
        result = dict(run.result or {})
        result.update({
            "worker_heartbeat_at": _now().isoformat(),
            "current_turn_index": turn_index,
            "current_step_attempt": step_attempt,
            "current_stage": stage,
        })
        run.result = result
        await db.commit()


async def _execute_run(
    run_id: int, safety_max_turns: int, max_stagnant_turns: int, locale: str | None
) -> None:
    session_uuid: str | None = None
    stage = "initialization"
    performance_trace: list[dict[str, Any]] = []
    try:
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if not run or run.status != "queued":
                return
            run.status = "running"
            current_result = dict(run.result or {})
            current_result["dialogue_status"] = "running"
            current_result["dialogue_started_at"] = _now().isoformat()
            run.result = current_result
            run.started_at = _now()
            scenario_id, condition = run.scenario_id, run.condition
            repetition = run.repetition
            batch_id = run.batch_id
            batch = await db.get(BatchExperiment, batch_id)
            batch_config = dict((batch.config if batch else None) or {})
            emit(
                "batch.run.started",
                batch_run_id=run_id,
                batch_id=batch_id,
                scenario_id=scenario_id,
                condition=condition,
                repetition=repetition,
            )
            stage = "session_creation"
            session = await memory_service.create_session(
                db,
                scenario_id,
                user_id=f"batch:{run.batch_id}:{run.id}",
                session_mode=condition,
                run_config={
                    "safety_max_turns": safety_max_turns,
                    "max_stagnant_turns": max_stagnant_turns,
                    "player_strategy": "balanced",
                    "player_temperature": 0.2,
                    "player_max_tokens": 512,
                    "working_message_limit": 30,
                    "comparison_protocol": "roommind-vs-independent-memory-agents-v3",
                    "baseline_architecture": "traditional_independent_agents",
                    "baseline_memory": "per_agent_rolling_public_history",
                    "baseline_governance": "none_except_safety_stop",
                    "metrics_protocol": "six-dimension-simulation-realism-v3",
                    "comparison_lock_model": True,
                    "batch_experiment_run_id": run.id,
                    # Freeze generation metadata into every session.  Forensic
                    # probes operate on archived sessions and must not depend on
                    # a mutable parent batch row being available later.
                    "research_manifest": batch_config.get("research_manifest") or {},
                    "generation_id": batch_config.get("generation_id"),
                    "architecture_version": batch_config.get("architecture_version"),
                },
            )
            session_uuid = session.session_uuid
            run.session_uuid = session_uuid
            await db.commit()

        # Commit each autonomous turn so progress survives a process restart.
        for turn_index in range(1, safety_max_turns + 1):
            if await _batch_cancelled(batch_id):
                raise asyncio.CancelledError
            stage = f"autonomous_turn_{turn_index}"
            step: dict[str, Any] | None = None
            for step_attempt in range(1, 3):
                await _record_run_heartbeat(
                    run_id,
                    turn_index=turn_index,
                    step_attempt=step_attempt,
                    stage=stage,
                )
                async with async_session_factory() as db:
                    from app.api.game import _run_autonomous_step

                    started = time.monotonic()
                    turn_events: list[dict[str, Any]] = []
                    with telemetry_context(
                        batch_run_id=run_id,
                        batch_id=batch_id,
                        session_uuid=session_uuid,
                        scenario_id=scenario_id,
                        condition=condition,
                        turn_index=turn_index,
                        step_attempt=step_attempt,
                        stage=stage,
                        _collector=turn_events,
                    ):
                        emit("batch.turn.started")
                        try:
                            step = await asyncio.wait_for(
                                _run_autonomous_step(db, session_uuid, locale),
                                timeout=AUTONOMOUS_STEP_TIMEOUT_SECONDS,
                            )
                        except TimeoutError as exc:
                            await db.rollback()
                            emit(
                                "batch.turn.timeout",
                                duration_ms=monotonic_ms(started),
                                timeout_seconds=AUTONOMOUS_STEP_TIMEOUT_SECONDS,
                                retrying=step_attempt == 1,
                            )
                            performance_trace.append({
                                "turn_index": turn_index,
                                "step_attempt": step_attempt,
                                "stage": stage,
                                "duration_ms": monotonic_ms(started),
                                "status": "timeout",
                                "recorded_at": _now().isoformat(),
                                "llm_events": [
                                    row for row in turn_events
                                    if str(row.get("event") or "").startswith(
                                        ("llm.", "dialogue.", "task_state.", "public_ledger.")
                                    )
                                ],
                            })
                            if step_attempt == 1:
                                await asyncio.sleep(2)
                                continue
                            raise RuntimeError(
                                f"Autonomous turn {turn_index} timed out twice after "
                                f"{AUTONOMOUS_STEP_TIMEOUT_SECONDS}s"
                            ) from exc
                        duration_ms = monotonic_ms(started)
                        trace_row = {
                            "turn_index": turn_index,
                            "step_attempt": step_attempt,
                            "stage": stage,
                            "duration_ms": duration_ms,
                            "status": step.get("status"),
                            "stop_reason": (step.get("test_state") or {}).get("stop_reason"),
                            "recorded_at": _now().isoformat(),
                            "llm_events": [
                                row for row in turn_events
                                if str(row.get("event") or "").startswith(
                                    ("llm.", "dialogue.", "task_state.", "public_ledger.")
                                )
                            ],
                        }
                        performance_trace.append(trace_row)
                        session_row = await memory_service.get_session(db, session_uuid)
                        if session_row:
                            shared = dict(session_row.shared_state or {})
                            shared["_performance_trace"] = performance_trace[-200:]
                            session_row.shared_state = shared
                        run_row = await db.get(BatchExperimentRun, run_id)
                        if run_row and run_row.status == "running":
                            run_progress = dict(run_row.result or {})
                            run_progress.update({
                                "worker_heartbeat_at": _now().isoformat(),
                                "last_completed_turn_index": turn_index,
                                "last_step_status": step.get("status"),
                                **_performance_summary(performance_trace),
                            })
                            run_row.result = run_progress
                        emit("batch.turn.finished", **trace_row)
                    await db.commit()
                    break
            if step is None:
                raise RuntimeError(f"Autonomous turn {turn_index} produced no result")
            if step.get("status") != "active":
                break

        async with async_session_factory() as db:
            stage = "dialogue_persistence"
            session = await memory_service.get_session(db, session_uuid)
            if not session:
                raise RuntimeError("Generated session disappeared")
            scenario = await orch_support.load_scenario(db, session.scenario_id)
            public = build_public_session_export_bundle(await build_session_export_bundle(db, session))
            shared = dict(session.shared_state or {})
            shared["_performance_trace"] = performance_trace[-200:]
            session.shared_state = shared
            messages = public.get("messages") or []
            turn_ids = {
                row.get("turn_id")
                for row in messages
                if row.get("speaker_type") in {"user", "npc"} and row.get("turn_id") is not None
            }
            result = {
                "scenario_id": scenario.id, "scenario_slug": scenario.slug,
                "scenario_title": scenario.title,
                "condition": "roommind" if condition == "test" else "baseline",
                "session_mode": condition, "repetition": repetition,
                "matched_pair_id": f"{scenario.slug}:r{repetition}",
                "session_uuid": session_uuid, "session_status": session.status,
                "message_count": len(messages), "turn_count": len(turn_ids),
                "dialogue_status": "completed", "evaluation_status": "not_started",
                "dialogue_completed_at": _now().isoformat(),
            }
            result.update(transcript_provenance(public))
            result.update(_performance_summary(performance_trace))
            result.update(_coordination_summary(public.get("task_result"), shared))
            run = await db.get(BatchExperimentRun, run_id)
            if run:
                retry_metadata = {
                    key: value for key, value in dict(run.result or {}).items()
                    if key in {
                        "dialogue_attempt_count", "dialogue_retry_history",
                        "dialogue_retry_queued_at",
                    }
                }
                run.status = "dialogue_completed"
                run.result = {**retry_metadata, **result}
                run.finished_at = _now()
            await db.commit()
            emit(
                "batch.dialogue.completed",
                batch_run_id=run_id,
                batch_id=batch_id,
                session_uuid=session_uuid,
                scenario_id=scenario_id,
                condition=condition,
                turn_count=len(turn_ids),
            )
    except asyncio.CancelledError:
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if run and run.status not in {"dialogue_completed", "dialogue_failed"}:
                run.status = "cancelled"
                run.error = "Batch cancelled"
                run.finished_at = _now()
            await db.commit()
    except Exception as exc:  # one failed cell must not abort the experiment
        exception_type = type(exc).__name__
        error_detail = f"{exception_type}: {exc!r}"
        logger.exception(
            "Batch run failed run_id=%s session_uuid=%s stage=%s",
            run_id,
            session_uuid,
            stage,
        )
        emit(
            "batch.run.failed",
            batch_run_id=run_id,
            session_uuid=session_uuid,
            stage=stage,
            exception_type=exception_type,
            error=error_detail[:2000],
        )
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if run:
                run.status = "dialogue_failed"
                run.error = error_detail[:4000]
                run.result = {
                    **dict(run.result or {}),
                    "dialogue_attempt_count": int(
                        (run.result or {}).get("dialogue_attempt_count") or 1
                    ),
                    "technical_failure": True,
                    "dialogue_status": "failed",
                    "evaluation_status": "not_started",
                    "failure_stage": stage,
                    "exception_type": exception_type,
                    "error": error_detail[:4000],
                    "traceback": traceback.format_exc()[-12000:],
                    "performance_trace": performance_trace[-200:],
                    **_performance_summary(performance_trace),
                }
                run.finished_at = _now()
                if session_uuid and not run.session_uuid:
                    run.session_uuid = session_uuid
            await db.commit()


async def _refresh_batch_counts(batch_id: int) -> None:
    async with async_session_factory() as db:
        batch = await db.get(BatchExperiment, batch_id)
        if not batch:
            return
        rows = list(
            (
                await db.execute(
                    select(BatchExperimentRun).where(BatchExperimentRun.batch_id == batch_id)
                )
            ).scalars()
        )
        dialogue_complete_statuses = {
            "dialogue_completed", "evaluation_queued", "evaluation_running",
            "evaluation_completed", "evaluation_partial", "evaluation_failed", "completed",
        }
        batch.completed_runs = sum(row.status in dialogue_complete_statuses for row in rows)
        batch.failed_runs = sum(row.status in {"failed", "dialogue_failed"} for row in rows)
        batch.cancelled_runs = sum(row.status == "cancelled" for row in rows)
        terminal = dialogue_complete_statuses | {"failed", "dialogue_failed", "cancelled"}
        if rows and all(row.status in terminal for row in rows):
            if any(row.status in {"evaluation_queued", "evaluation_running"} for row in rows):
                batch.status = "evaluation_running"
            elif any(row.status in {"evaluation_partial", "evaluation_failed"} for row in rows):
                batch.status = "evaluation_partial"
            elif all(row.status == "evaluation_completed" for row in rows):
                batch.status = "evaluation_completed"
            else:
                batch.status = "cancelled" if any(row.status == "cancelled" for row in rows) else "dialogue_completed"
            batch.finished_at = _now()
        await db.commit()


async def _execute_batch(batch_uuid: str) -> None:
    try:
        async with async_session_factory() as db:
            batch = (
                await db.execute(
                    select(BatchExperiment).where(BatchExperiment.batch_uuid == batch_uuid)
                )
            ).scalar_one_or_none()
            if not batch or batch.status in {
                "dialogue_completed", "evaluation_running", "evaluation_completed",
                "evaluation_partial", "completed", "cancelled",
            }:
                return
            batch.status = "running"
            batch.started_at = batch.started_at or _now()
            config = dict(batch.config or {})
            # Interrupted in-flight cells are safe to rerun as new sessions.
            runs = list(
                (
                    await db.execute(
                        select(BatchExperimentRun).where(BatchExperimentRun.batch_id == batch.id)
                    )
                ).scalars()
            )
            for row in runs:
                if row.status == "running":
                    row.status = "queued"
                    row.error = "Recovered after server restart"
            await db.commit()
            batch_id = batch.id

        pending = [row.id for row in runs if row.status in {"queued", "running"}]
        random.Random(int(config.get("random_seed", 20260728))).shuffle(pending)
        concurrency = max(1, min(int(config.get("concurrency", DEFAULT_CONCURRENCY)), MAX_CONCURRENCY))
        semaphore = asyncio.Semaphore(concurrency)

        async def guarded(run_id: int) -> None:
            async with semaphore:
                # Multiple batches may coexist, but the API process never runs
                # more than MAX_CONCURRENCY LLM-heavy sessions at once.
                async with _global_run_semaphore:
                    if not await _batch_cancelled(batch_id):
                        await _execute_run(
                            run_id,
                            int(config.get("safety_max_turns", 50)),
                            int(config.get("max_stagnant_turns", 8)),
                            config.get("locale"),
                        )
                await _refresh_batch_counts(batch_id)

        await asyncio.gather(*(guarded(run_id) for run_id in pending))
        await _refresh_batch_counts(batch_id)
    finally:
        _tasks.pop(batch_uuid, None)


def _schedule(batch_uuid: str) -> None:
    existing = _tasks.get(batch_uuid)
    if existing and not existing.done():
        return
    _tasks[batch_uuid] = asyncio.create_task(_execute_batch(batch_uuid))


def _schedule_single_dialogue_retry(
    *, batch_id: int, run_id: int, config: dict[str, Any]
) -> None:
    """Run one retried cell without waiting for unrelated evaluation work."""
    existing = _retry_tasks.get(run_id)
    if existing and not existing.done():
        return

    async def execute() -> None:
        try:
            async with _global_run_semaphore:
                await _execute_run(
                    run_id,
                    int(config.get("safety_max_turns", 50)),
                    int(config.get("max_stagnant_turns", 8)),
                    config.get("locale"),
                )
            await _refresh_batch_counts(batch_id)
        finally:
            _retry_tasks.pop(run_id, None)

    _retry_tasks[run_id] = asyncio.create_task(execute())


async def _evaluate_run(run_id: int) -> None:
    """Evaluate one frozen dialogue without changing its dialogue outcome."""
    started = time.monotonic()
    evaluation_events: list[dict[str, Any]] = []
    try:
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if not run or run.status != "evaluation_queued" or not run.session_uuid:
                return
            run.status = "evaluation_running"
            existing = dict(run.result or {})
            existing["dialogue_status"] = existing.get("dialogue_status") or "completed"
            existing["evaluation_status"] = "running"
            run.result = existing
            run.error = None
            await db.commit()

            session = await memory_service.get_session(db, run.session_uuid)
            if not session:
                raise RuntimeError("Frozen dialogue session no longer exists")
            scenario = await orch_support.load_scenario(db, session.scenario_id)
            public = build_public_session_export_bundle(await build_session_export_bundle(db, session))
            existing_external_evaluation = (session.shared_state or {}).get("_external_evaluation")
            if not isinstance(existing_external_evaluation, dict) and isinstance(
                existing.get("realism_dimensions"), dict
            ):
                # A restart or legacy archive may retain flattened run scores
                # even when the session-side evaluation envelope is absent.
                # Reconstruct enough state to keep completed dimensions frozen.
                existing_external_evaluation = {
                    "dimensions": deepcopy(existing.get("realism_dimensions") or {}),
                    "evaluation_errors": dict(existing.get("evaluation_errors") or {}),
                }
            with telemetry_context(
                batch_run_id=run.id, batch_id=run.batch_id, session_uuid=run.session_uuid,
                scenario_id=run.scenario_id, condition=run.condition,
                stage="independent_external_evaluation", _collector=evaluation_events,
            ):
                emit("batch.evaluation.started")
                evaluation = await asyncio.wait_for(
                    evaluate_public_transcript(
                        db, scenario=scenario, messages=public.get("messages") or [],
                        system_claim=(public.get("external_observation") or {}).get("system_claim") or {},
                        existing_evaluation=existing_external_evaluation,
                    ),
                    timeout=EXTERNAL_EVALUATION_TIMEOUT_SECONDS,
                )
                emit("batch.evaluation.finished", duration_ms=monotonic_ms(started))

            messages = public.get("messages") or []
            turn_ids = {row.get("turn_id") for row in messages
                        if row.get("speaker_type") in {"user", "npc"} and row.get("turn_id") is not None}
            evaluated = _flatten_result(
                scenario=scenario, condition=run.condition, repetition=run.repetition,
                session_uuid=run.session_uuid, session_status=session.status,
                message_count=len(messages), turn_count=len(turn_ids), evaluation=evaluation,
            )
            scores = evaluation.get("dimension_scores") or {}
            completed_dimensions = sum(scores.get(name) is not None for name in REALISM_DIMENSIONS)
            evaluation_status = (
                "completed" if completed_dimensions == len(REALISM_DIMENSIONS)
                else "partial" if completed_dimensions else "failed"
            )
            evaluation_trace = [{
                "stage": "independent_external_evaluation", "duration_ms": monotonic_ms(started),
                "recorded_at": _now().isoformat(),
                "llm_events": [row for row in evaluation_events
                               if str(row.get("event") or "").startswith(
                                   ("llm.", "dialogue.", "task_state.", "public_ledger.")
                               )],
            }]
            prior_evaluation_trace = list(existing.get("evaluation_performance_trace") or [])
            merged = {**existing, **evaluated,
                      "dialogue_status": "completed", "evaluation_status": evaluation_status,
                      "evaluated_dimension_count": completed_dimensions,
                      "evaluation_errors": evaluation.get("evaluation_errors") or {},
                      "evaluation_performance_trace": [*prior_evaluation_trace, *evaluation_trace][-12:],
                      "evaluation_completed_at": _now().isoformat()}
            run = await db.get(BatchExperimentRun, run_id)
            if run:
                run.status = f"evaluation_{evaluation_status}"
                run.result = merged
                run.error = None if evaluation_status != "failed" else "All six realism dimensions failed evaluation"
            shared = dict(session.shared_state or {})
            shared["_external_evaluation"] = evaluation
            session.shared_state = shared
            await db.commit()
    except Exception as exc:
        logger.exception("Independent evaluation failed run_id=%s", run_id)
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if run:
                existing = dict(run.result or {})
                existing.update({
                    "dialogue_status": existing.get("dialogue_status") or "completed",
                    "evaluation_status": "failed", "evaluation_failure_stage": "external_evaluation",
                    "evaluation_exception_type": type(exc).__name__,
                    "evaluation_error": f"{type(exc).__name__}: {exc}"[:4000],
                    "evaluation_traceback": traceback.format_exc()[-12000:],
                })
                run.status = "evaluation_failed"
                run.result = existing
                run.error = existing["evaluation_error"]
            await db.commit()


async def _execute_evaluation_batch(batch_uuid: str, concurrency: int) -> None:
    try:
        async with async_session_factory() as db:
            batch = (await db.execute(select(BatchExperiment).where(
                BatchExperiment.batch_uuid == batch_uuid
            ))).scalar_one_or_none()
            if not batch:
                return
            batch.status = "evaluation_running"
            rows = list((await db.execute(select(BatchExperimentRun).where(
                BatchExperimentRun.batch_id == batch.id,
                BatchExperimentRun.status == "evaluation_queued",
            ))).scalars())
            batch_id = batch.id
            await db.commit()
        semaphore = asyncio.Semaphore(max(1, min(concurrency, MAX_CONCURRENCY)))
        async def guarded(run_id: int) -> None:
            async with semaphore:
                async with _global_run_semaphore:
                    await _evaluate_run(run_id)
                await _refresh_batch_counts(batch_id)
        await asyncio.gather(*(guarded(row.id) for row in rows))
        await _refresh_batch_counts(batch_id)
    finally:
        _evaluation_tasks.pop(batch_uuid, None)


def _schedule_evaluation(batch_uuid: str, concurrency: int) -> None:
    existing = _evaluation_tasks.get(batch_uuid)
    if existing and not existing.done():
        return
    _evaluation_tasks[batch_uuid] = asyncio.create_task(
        _execute_evaluation_batch(batch_uuid, concurrency)
    )


async def resume_batch_experiments() -> None:
    """Resume queued/running work when the API process starts."""
    async with async_session_factory() as db:
        batches = list(
            (
                await db.execute(
                    select(BatchExperiment).where(BatchExperiment.status.in_(["queued", "running"]))
                )
            ).scalars()
        )
    for batch in batches:
        _schedule(batch.batch_uuid)
    async with async_session_factory() as db:
        evaluation_batches = list((await db.execute(select(BatchExperiment).where(
            BatchExperiment.status == "evaluation_running"
        ))).scalars())
        for batch in evaluation_batches:
            rows = list((await db.execute(select(BatchExperimentRun).where(
                BatchExperimentRun.batch_id == batch.id,
                BatchExperimentRun.status == "evaluation_running",
            ))).scalars())
            for row in rows:
                row.status = "evaluation_queued"
        await db.commit()
    for batch in evaluation_batches:
        _schedule_evaluation(batch.batch_uuid, int((batch.config or {}).get("evaluation_concurrency", 1)))


def _serialize_batch(batch: BatchExperiment, runs: list[BatchExperimentRun] | None = None) -> dict:
    payload = {
        "batch_uuid": batch.batch_uuid,
        "name": batch.name,
        "status": batch.status,
        "config": batch.config or {},
        "total_runs": batch.total_runs,
        "completed_runs": batch.completed_runs,
        "failed_runs": batch.failed_runs,
        "cancelled_runs": batch.cancelled_runs,
        "created_at": batch.created_at,
        "started_at": batch.started_at,
        "finished_at": batch.finished_at,
    }
    if runs is not None:
        payload["runs"] = [
            {
                "id": row.id,
                "scenario_id": row.scenario_id,
                "condition": "roommind" if row.condition == "test" else "baseline",
                "session_mode": row.condition,
                "repetition": row.repetition,
                "status": row.status,
                "session_uuid": row.session_uuid,
                "result": row.result or {},
                "error": row.error,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
            }
            for row in runs
        ]
    return payload


@router.post("")
async def create_batch(body: BatchCreateIn) -> dict:
    conditions = list(dict.fromkeys(body.conditions))
    if any(value not in {"test", "baseline"} for value in conditions):
        raise HTTPException(422, "Conditions must be 'test' and/or 'baseline'")
    if body.study_phase not in STUDY_PHASES:
        raise HTTPException(422, "study_phase must be exploration, screening, or confirmation")
    scenario_ids = list(dict.fromkeys(body.scenario_ids))
    total = len(scenario_ids) * len(conditions) * body.repetitions
    if total > MAX_RUNS_PER_BATCH:
        raise HTTPException(422, f"A batch may contain at most {MAX_RUNS_PER_BATCH} runs")
    async with async_session_factory() as db:
        found = set(
            (
                await db.execute(
                    select(ScenarioTemplate.id).where(
                        ScenarioTemplate.id.in_(scenario_ids), ScenarioTemplate.is_published.is_(True)
                    )
                )
            ).scalars()
        )
        if found != set(scenario_ids):
            raise HTTPException(422, "One or more scenarios do not exist or are unpublished")
        config = body.model_dump()
        config.update({
            "research_manifest": experiment_manifest(
                study_phase=body.study_phase, random_seed=body.random_seed
            ),
            "generation_id": CURRENT_GENERATION_ID,
            "architecture_version": CURRENT_ARCHITECTURE_VERSION,
            "comparison_protocol": "roommind-vs-independent-memory-agents-v3",
            "baseline_architecture": "traditional_independent_agents",
            "baseline_memory": "per_agent_rolling_public_history",
            "baseline_governance": "none_except_safety_stop",
            "metrics_protocol": "six-dimension-simulation-realism-v3",
            "shared_player_policy": "public-only-comparison-player-v1",
            "player_temperature": 0.2,
            "working_message_limit": 30,
            "comparison_lock_model": True,
        })
        batch = BatchExperiment(
            batch_uuid=str(uuid.uuid4()),
            name=body.name.strip(),
            config=config,
            status="queued",
            total_runs=total,
        )
        db.add(batch)
        await db.flush()
        for scenario_id in scenario_ids:
            for condition in conditions:
                for repetition in range(1, body.repetitions + 1):
                    db.add(
                        BatchExperimentRun(
                            batch_id=batch.id,
                            scenario_id=scenario_id,
                            condition=condition,
                            repetition=repetition,
                        )
                    )
        await db.commit()
        payload = _serialize_batch(batch)
    _schedule(batch.batch_uuid)
    return payload


@router.get("")
async def list_batches() -> list[dict]:
    async with async_session_factory() as db:
        rows = list(
            (await db.execute(select(BatchExperiment).order_by(BatchExperiment.id.desc()).limit(50))).scalars()
        )
        return [_serialize_batch(row) for row in rows]


@router.get("/{batch_uuid}")
async def get_batch(batch_uuid: str) -> dict:
    async with async_session_factory() as db:
        batch = (
            await db.execute(select(BatchExperiment).where(BatchExperiment.batch_uuid == batch_uuid))
        ).scalar_one_or_none()
        if not batch:
            raise HTTPException(404, "Batch experiment not found")
        runs = list(
            (
                await db.execute(
                    select(BatchExperimentRun)
                    .where(BatchExperimentRun.batch_id == batch.id)
                    .order_by(BatchExperimentRun.scenario_id, BatchExperimentRun.condition, BatchExperimentRun.repetition)
                )
            ).scalars()
        )
        return _serialize_batch(batch, runs)


@router.post("/{batch_uuid}/cancel")
async def cancel_batch(batch_uuid: str) -> dict:
    async with async_session_factory() as db:
        batch = (
            await db.execute(select(BatchExperiment).where(BatchExperiment.batch_uuid == batch_uuid))
        ).scalar_one_or_none()
        if not batch:
            raise HTTPException(404, "Batch experiment not found")
        if batch.status not in {"completed", "cancelled"}:
            batch.status = "cancelling"
            rows = list(
                (
                    await db.execute(
                        select(BatchExperimentRun).where(
                            BatchExperimentRun.batch_id == batch.id,
                            BatchExperimentRun.status == "queued",
                        )
                    )
                ).scalars()
            )
            for row in rows:
                row.status = "cancelled"
                row.error = "Batch cancelled before run started"
                row.finished_at = _now()
        await db.commit()
        return _serialize_batch(batch)


@router.post("/{batch_uuid}/runs/{run_id}/retry-dialogue")
async def retry_failed_dialogue(batch_uuid: str, run_id: int) -> dict[str, Any]:
    """Retry exactly one failed dialogue without rerunning successful cells."""
    async with async_session_factory() as db:
        batch = (await db.execute(select(BatchExperiment).where(
            BatchExperiment.batch_uuid == batch_uuid
        ))).scalar_one_or_none()
        if not batch:
            raise HTTPException(404, "Batch experiment not found")
        run = await db.get(BatchExperimentRun, run_id)
        if not run or run.batch_id != batch.id:
            raise HTTPException(404, "Batch experiment run not found")
        if run.status not in {"failed", "dialogue_failed"}:
            raise HTTPException(409, "Only failed dialogue runs can be retried")
        if batch.status == "cancelling":
            raise HTTPException(409, "A cancelling batch cannot accept a dialogue retry")

        previous_session_uuid = run.session_uuid
        run.result = _dialogue_retry_result(run)
        run.status = "queued"
        run.session_uuid = None
        run.error = None
        run.started_at = None
        run.finished_at = None
        # Evaluation and a targeted dialogue retry are independent processes.
        # Keep evaluation_running visible when applicable; otherwise expose the
        # dialogue work as running immediately instead of leaving it "queued".
        if batch.status != "evaluation_running":
            batch.status = "running"
        batch.finished_at = None
        batch_id = batch.id
        batch_config = dict(batch.config or {})
        attempt_number = run.result["dialogue_attempt_count"]
        await db.commit()
    await _refresh_batch_counts(batch_id)
    emit(
        "batch.dialogue.retry_queued",
        batch_uuid=batch_uuid,
        batch_run_id=run_id,
        previous_session_uuid=previous_session_uuid,
        attempt_number=attempt_number,
    )
    payload = await get_batch(batch_uuid)
    _schedule_single_dialogue_retry(
        batch_id=batch_id,
        run_id=run_id,
        config=batch_config,
    )
    return {**payload, "retried_run_id": run_id}


@router.post("/{batch_uuid}/evaluate")
async def start_batch_evaluation(batch_uuid: str, body: EvaluationStartIn) -> dict[str, Any]:
    """Queue independent AI evaluation for frozen dialogue sessions."""
    async with async_session_factory() as db:
        batch = (await db.execute(select(BatchExperiment).where(
            BatchExperiment.batch_uuid == batch_uuid
        ))).scalar_one_or_none()
        if not batch:
            raise HTTPException(404, "Batch experiment not found")
        rows = list((await db.execute(select(BatchExperimentRun).where(
            BatchExperimentRun.batch_id == batch.id
        ))).scalars())
        requested = set(body.run_ids or [])
        eligible_statuses = {
            "dialogue_completed", "evaluation_failed", "evaluation_partial", "completed",
        }
        queued = 0
        for row in rows:
            if requested and row.id not in requested:
                continue
            if row.status in eligible_statuses or (body.retry_all and row.status == "evaluation_completed"):
                if not row.session_uuid:
                    continue
                row.status = "evaluation_queued"
                result = dict(row.result or {})
                result["dialogue_status"] = result.get("dialogue_status") or "completed"
                result["evaluation_status"] = "queued"
                row.result = result
                row.error = None
                queued += 1
        if not queued:
            raise HTTPException(409, "No completed dialogues are eligible for evaluation")
        config = dict(batch.config or {})
        config["evaluation_concurrency"] = body.concurrency
        batch.config = config
        batch.status = "evaluation_running"
        batch.finished_at = None
        await db.commit()
        payload = _serialize_batch(batch, rows)
    emit("batch.evaluation.queued", batch_uuid=batch_uuid, run_count=queued)
    _schedule_evaluation(batch_uuid, body.concurrency)
    return {**payload, "queued_evaluation_runs": queued}


@router.get("/{batch_uuid}/results.csv", response_class=PlainTextResponse)
async def batch_results_csv(batch_uuid: str) -> PlainTextResponse:
    payload = await get_batch(batch_uuid)
    rows = []
    for run in payload["runs"]:
        rows.append(
            {
                "batch_uuid": batch_uuid,
                "batch_name": payload["name"],
                "run_id": run["id"],
                "run_status": run["status"],
                "technical_failure": run["status"] in {"failed", "dialogue_failed"},
                "evaluation_failure": run["status"] == "evaluation_failed",
                "error": run.get("error") or "",
                "started_at": run.get("started_at") or "",
                "finished_at": run.get("finished_at") or "",
                "scenario_id": run["scenario_id"],
                "condition": run["condition"],
                "session_mode": run["session_mode"],
                "repetition": run["repetition"],
                "session_uuid": run.get("session_uuid") or "",
                "blind_review_code": str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"{batch_uuid}:{run['id']}")
                )[:12],
                "comparison_protocol": (payload.get("config") or {}).get("comparison_protocol"),
                "baseline_architecture": (payload.get("config") or {}).get(
                    "baseline_architecture"
                ),
                "baseline_memory": (payload.get("config") or {}).get("baseline_memory"),
                "baseline_governance": (payload.get("config") or {}).get(
                    "baseline_governance"
                ),
                "metrics_protocol": (payload.get("config") or {}).get("metrics_protocol"),
                "shared_player_policy": (payload.get("config") or {}).get("shared_player_policy"),
                "configured_max_turns": (payload.get("config") or {}).get("safety_max_turns"),
                "configured_concurrency": (payload.get("config") or {}).get("concurrency"),
                "random_seed": (payload.get("config") or {}).get("random_seed"),
                "human_validation_enabled": (payload.get("config") or {}).get(
                    "human_validation_enabled", False
                ),
                **(run.get("result") or {}),
            }
        )
    columns = list(dict.fromkeys(key for row in rows for key in row.keys()))
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return PlainTextResponse(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch_uuid}.csv"'},
    )


@router.get("/{batch_uuid}/human-review.json")
async def batch_human_review(batch_uuid: str) -> dict[str, Any]:
    """Optional condition-hidden packets; never required for automated metrics."""
    payload = await get_batch(batch_uuid)
    if not bool((payload.get("config") or {}).get("human_validation_enabled")):
        raise HTTPException(409, "Human validation was not enabled for this batch")
    packets: list[dict[str, Any]] = []
    async with async_session_factory() as db:
        for run in payload.get("runs") or []:
            if run.get("status") not in {
                "dialogue_completed", "evaluation_queued", "evaluation_running",
                "evaluation_completed", "evaluation_partial", "evaluation_failed", "completed",
            } or not run.get("session_uuid"):
                continue
            session = await memory_service.get_session(db, run["session_uuid"])
            if not session:
                continue
            public = build_public_session_export_bundle(
                await build_session_export_bundle(db, session)
            )
            packet = build_blinded_evaluation_packet(public)
            scenario = await orch_support.load_scenario(db, session.scenario_id)
            packet["gold_specification"]["scenario_description"] = scenario.description
            packet["gold_specification"]["phases"] = scenario.phases or []
            packet["gold_specification"]["role_cards"] = [{
                "character_id": character.character_id,
                "speaker_label": (packet.get("speaker_aliases") or {}).get(
                    character.character_id, "Participant"
                ),
                "job_title": character.job_title,
                "responsibility": character.responsibility,
                "persona": character.persona,
                "tendency": character.tendency or {},
                "authority": character.authority or {},
                "information_policy": {
                    "protected_secrets": (character.private_state or {}).get("protected_secrets", []),
                    "discoverable_information": (character.private_state or {}).get("discoverable_information", []),
                    "role_disclosable_information": (character.private_state or {}).get("role_disclosable_information", []),
                },
            } for character in sorted(scenario.characters, key=lambda row: row.sort_order)]
            packet["run_label"] = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{batch_uuid}:{run['id']}")
            )[:12]
            packets.append(packet)
    packets.sort(key=lambda row: row["run_label"])
    return {
        "protocol": HUMAN_REVIEW_PROTOCOL_VERSION,
        "condition_hidden": True,
        "required_for_final_analysis": True,
        "rating_scale": "1-7",
        "rubric": REALISM_RUBRIC,
        "review_access": {
            "current": "reviewer_code_v1",
            "production_target": "email_magic_link_or_institution_sso",
            "condition_assignment": "server_side_blinded",
        },
        "packets": packets,
    }


@router.get("/{batch_uuid}/review-queue")
async def batch_review_queue(batch_uuid: str) -> dict[str, Any]:
    """Return anonymous transcripts and saved reviews without revealing condition."""
    packet_bundle = await batch_human_review(batch_uuid)
    payload = await get_batch(batch_uuid)
    code_to_run = {
        str(uuid.uuid5(uuid.NAMESPACE_URL, f"{batch_uuid}:{run['id']}"))[:12]: run["id"]
        for run in payload.get("runs") or []
    }
    async with async_session_factory() as db:
        reviews = list((await db.execute(
            select(BatchHumanReview).where(
                BatchHumanReview.batch_id == (
                    select(BatchExperiment.id).where(BatchExperiment.batch_uuid == batch_uuid).scalar_subquery()
                )
            )
        )).scalars())
    saved_counts: dict[str, int] = {}
    run_to_code = {run_id: code for code, run_id in code_to_run.items()}
    for review in reviews:
        code = run_to_code.get(review.run_id)
        if code:
            saved_counts[code] = saved_counts.get(code, 0) + 1
    # Do not expose reviewer identities or ratings through a condition-blinded
    # web queue.  Aggregate results remain available in the final report.
    packet_bundle["saved_reviews"] = {}
    packet_bundle["saved_review_counts"] = saved_counts
    return packet_bundle


@router.post("/{batch_uuid}/reviews/{run_label}")
async def submit_human_review(batch_uuid: str, run_label: str, body: HumanReviewIn) -> dict[str, Any]:
    """Persist one independent blinded review with optional sequence evidence."""
    missing = [name for name in REALISM_DIMENSIONS if name not in body.ratings]
    if missing:
        raise HTTPException(422, f"Missing realism ratings: {', '.join(missing)}")
    ratings = dict(body.ratings)
    for key, score in ratings.items():
        if key not in REALISM_DIMENSIONS + ["overall_believability"] or not 1 <= score <= 7:
            raise HTTPException(422, f"Invalid 1-7 rating: {key}")
    valid_indicators = {
        indicator[0]
        for rubric in REALISM_RUBRIC.values()
        for indicator in rubric["indicators"]
    }
    missing_indicators = sorted(valid_indicators - set(body.indicator_ratings))
    if missing_indicators:
        raise HTTPException(422, f"Missing indicator ratings: {', '.join(missing_indicators)}")
    if any(key not in valid_indicators or not 1 <= score <= 7
           for key, score in body.indicator_ratings.items()):
        raise HTTPException(422, "Every indicator rating must be on the 1-7 scale")
    async with async_session_factory() as db:
        batch = (await db.execute(
            select(BatchExperiment).where(BatchExperiment.batch_uuid == batch_uuid)
        )).scalar_one_or_none()
        if not batch or not bool((batch.config or {}).get("human_validation_enabled")):
            raise HTTPException(404, "Human review batch not found")
        runs = list((await db.execute(
            select(BatchExperimentRun).where(BatchExperimentRun.batch_id == batch.id)
        )).scalars())
        run = next((row for row in runs if str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"{batch_uuid}:{row.id}")
        )[:12] == run_label), None)
        if not run or run.status not in {
            "dialogue_completed", "evaluation_queued", "evaluation_running",
            "evaluation_completed", "evaluation_partial", "evaluation_failed", "completed",
        }:
            raise HTTPException(404, "Anonymous review item not found")
        session = await memory_service.get_session(db, run.session_uuid) if run.session_uuid else None
        if not session:
            raise HTTPException(409, "The frozen source session is unavailable")
        public = build_public_session_export_bundle(await build_session_export_bundle(db, session))
        provenance = transcript_provenance(public)
        if provenance["transcript_sha256"] != body.transcript_sha256:
            raise HTTPException(409, "Transcript changed since this review item was opened; reload before rating")
        existing = (await db.execute(select(BatchHumanReview).where(
            BatchHumanReview.run_id == run.id,
            BatchHumanReview.reviewer_id == body.reviewer_id.strip(),
        ))).scalar_one_or_none()
        review_evidence = {
            **body.evidence,
            "indicator_ratings": body.indicator_ratings,
            "reviewer_profile": body.reviewer_profile,
            "interface_locale": body.interface_locale,
            "source_provenance": provenance,
            "evaluation_protocol": HUMAN_REVIEW_PROTOCOL_VERSION,
            "finalized": body.finalize,
        }
        if existing:
            if bool((existing.evidence or {}).get("finalized")):
                raise HTTPException(409, "This review was already finalized and is immutable")
            existing.ratings, existing.evidence, existing.notes = ratings, review_evidence, body.notes
        else:
            db.add(BatchHumanReview(
                batch_id=batch.id, run_id=run.id, reviewer_id=body.reviewer_id.strip(),
                ratings=ratings, evidence=review_evidence, notes=body.notes,
            ))
        await db.commit()
    emit("batch.human_review.saved", batch_uuid=batch_uuid, run_label=run_label)
    return {
        "saved": True, "finalized": body.finalize, "run_label": run_label,
        "transcript_sha256": body.transcript_sha256,
    }


@router.get("/{batch_uuid}/final-evaluation")
async def batch_final_evaluation(batch_uuid: str) -> dict[str, Any]:
    """Merge AI and human evidence by dimension without inventing a total score."""
    payload = await get_batch(batch_uuid)
    run_ids = [run["id"] for run in payload.get("runs") or []]
    async with async_session_factory() as db:
        reviews = list((await db.execute(select(BatchHumanReview).where(
            BatchHumanReview.run_id.in_(run_ids)
        ))).scalars()) if run_ids else []
    by_run: dict[int, list[BatchHumanReview]] = {}
    for review in reviews:
        by_run.setdefault(review.run_id, []).append(review)
    rows = []
    for run in payload.get("runs") or []:
        human = by_run.get(run["id"], [])
        human_means = {
            dimension: (sum(float(r.ratings[dimension]) for r in human if dimension in r.ratings)
                        / sum(dimension in r.ratings for r in human))
            if any(dimension in r.ratings for r in human) else None
            for dimension in REALISM_DIMENSIONS
        }
        rows.append({
            "run_id": run["id"], "scenario_id": run["scenario_id"],
            "condition": run["condition"], "repetition": run["repetition"],
            "ai_scores": {d: (run.get("result") or {}).get(f"ai_{d}") for d in REALISM_DIMENSIONS},
            "human_mean_scores": human_means, "human_review_count": len(human),
            "status": "final" if human else "awaiting_human_review",
        })
    summaries: dict[str, Any] = {}
    for condition in ("roommind", "baseline"):
        selected_rows = [row for row in rows if row["condition"] == condition]
        summaries[condition] = {}
        for dimension in REALISM_DIMENSIONS:
            ai_values = [float(row["ai_scores"][dimension]) for row in selected_rows
                         if row["ai_scores"].get(dimension) is not None]
            human_values = [float(row["human_mean_scores"][dimension]) for row in selected_rows
                            if row["human_mean_scores"].get(dimension) is not None]
            summaries[condition][dimension] = {
                "ai_mean": sum(ai_values) / len(ai_values) if ai_values else None,
                "ai_n": len(ai_values),
                "human_mean": sum(human_values) / len(human_values) if human_values else None,
                "human_rated_run_n": len(human_values),
            }
    return {
        "protocol": "six-dimension-simulation-realism-final-v3",
        "aggregation_rule": "AI and human scores remain separate; no composite total is computed.",
        "dimensions": REALISM_DIMENSIONS, "rubric": REALISM_RUBRIC,
        "research_manifest": (payload.get("config") or {}).get("research_manifest"),
        "condition_summaries": summaries, "runs": rows,
    }


async def _batch_transcript_rows(batch_uuid: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = await get_batch(batch_uuid)
    exports: list[dict[str, Any]] = []
    async with async_session_factory() as db:
        for run in payload.get("runs") or []:
            session_uuid = run.get("session_uuid")
            if not session_uuid:
                continue
            session = await memory_service.get_session(db, session_uuid)
            if not session:
                continue
            public = build_public_session_export_bundle(
                await build_session_export_bundle(db, session)
            )
            exports.append({
                "run_id": run["id"],
                "condition": run["condition"],
                "scenario_id": run["scenario_id"],
                "repetition": run["repetition"],
                "run_status": run["status"],
                "run_error": run.get("error"),
                "run_result": run.get("result") or {},
                "session": public,
            })
    return payload, exports


@router.get("/{batch_uuid}/transcripts.json")
async def batch_transcripts_json(batch_uuid: str) -> dict[str, Any]:
    """Export every available public utterance, including failed/running runs."""
    payload, exports = await _batch_transcript_rows(batch_uuid)
    return {
        "batch_uuid": batch_uuid,
        "batch_name": payload.get("name"),
        "batch_status": payload.get("status"),
        "config": payload.get("config") or {},
        "research_manifest": (payload.get("config") or {}).get("research_manifest"),
        "artifact_policy": "Persisted real session transcripts; no regenerated or synthetic review dialogue.",
        "exported_at": _now().isoformat(),
        "runs": exports,
    }


@router.get("/{batch_uuid}/debug-bundle.json")
async def batch_debug_bundle(batch_uuid: str) -> dict[str, Any]:
    """Full forensic export: dialogue, internal memories, decisions, state and traces."""
    payload = await get_batch(batch_uuid)
    exports: list[dict[str, Any]] = []
    async with async_session_factory() as db:
        for run in payload.get("runs") or []:
            session_uuid = run.get("session_uuid")
            session = await memory_service.get_session(db, session_uuid) if session_uuid else None
            prior_attempts: list[dict[str, Any]] = []
            history = (run.get("result") or {}).get("dialogue_retry_history") or []
            for attempt in history:
                prior_uuid = attempt.get("session_uuid")
                if not prior_uuid:
                    continue
                prior_session = await memory_service.get_session(db, prior_uuid)
                if prior_session:
                    prior_attempts.append({
                        "attempt": attempt,
                        "full_session": await build_session_export_bundle(db, prior_session),
                    })
            full_session = await build_session_export_bundle(db, session) if session else None
            exports.append({
                "run": run,
                "full_session": full_session,
                "research_integrity_probes": run_integrity_probes(full_session) if full_session else None,
                "prior_attempt_sessions": prior_attempts,
            })
    emit("batch.debug_bundle.exported", batch_uuid=batch_uuid, run_count=len(exports))
    return {
        "format": "roommind-batch-forensic-debug-bundle-v1",
        "warning": "Contains internal agent memories and state; do not provide to blinded reviewers.",
        "batch": payload, "exported_at": _now().isoformat(), "runs": exports,
    }


@router.get("/{batch_uuid}/transcripts.csv", response_class=PlainTextResponse)
async def batch_transcripts_csv(batch_uuid: str) -> PlainTextResponse:
    """One row per utterance for statistical and qualitative analysis."""
    payload, exports = await _batch_transcript_rows(batch_uuid)
    rows: list[dict[str, Any]] = []
    for export in exports:
        session = export.get("session") or {}
        for message in session.get("messages") or []:
            speaker = message.get("speaker") or {}
            rows.append({
                "batch_uuid": batch_uuid,
                "batch_name": payload.get("name"),
                "run_id": export.get("run_id"),
                "run_status": export.get("run_status"),
                "condition": export.get("condition"),
                "scenario_id": export.get("scenario_id"),
                "repetition": export.get("repetition"),
                "session_uuid": (session.get("session") or {}).get("session_uuid"),
                "session_status": (session.get("session") or {}).get("status"),
                "turn_id": message.get("turn_id"),
                "sequence_no": message.get("sequence_no"),
                "message_id": message.get("id"),
                "speaker_id": message.get("speaker_id"),
                "speaker_name": speaker.get("display_name"),
                "speaker_role": speaker.get("role"),
                "speaker_type": message.get("speaker_type"),
                "speaker_source": message.get("speaker_source"),
                "content": message.get("content"),
                "emotion": message.get("emotion"),
                "gesture": message.get("gesture"),
                "created_at": message.get("created_at"),
                "run_error": export.get("run_error"),
            })
    columns = list(dict.fromkeys(key for row in rows for key in row.keys()))
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return PlainTextResponse(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch_uuid}-transcripts.csv"'},
    )
