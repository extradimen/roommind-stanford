"""Persistent, restart-resumable batch experiments for autonomous comparisons."""

from __future__ import annotations

import asyncio
import csv
import io
import random
import uuid
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
from app.models.db import BatchExperiment, BatchExperimentRun, ScenarioTemplate
from app.orchestrator.common import orch_support
from app.session_export import build_public_session_export_bundle, build_session_export_bundle

router = APIRouter(prefix="/api/game/batch-experiments", tags=["batch-experiments"])

DEFAULT_CONCURRENCY = 2
MAX_CONCURRENCY = 4
MAX_RUNS_PER_BATCH = 500
_tasks: dict[str, asyncio.Task] = {}
_global_run_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


class BatchCreateIn(BaseModel):
    name: str = Field(default="Batch experiment", min_length=1, max_length=256)
    scenario_ids: list[int] = Field(min_length=1)
    conditions: list[str] = Field(min_length=1)
    repetitions: int = Field(default=10, ge=1, le=100)
    concurrency: int = Field(default=DEFAULT_CONCURRENCY, ge=1, le=MAX_CONCURRENCY)
    safety_max_turns: int = Field(default=50, ge=10, le=100)
    locale: str | None = None
    random_seed: int = Field(default=20260728, ge=0, le=2_147_483_647)
    human_validation_enabled: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    return {
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


async def _batch_cancelled(batch_id: int) -> bool:
    async with async_session_factory() as db:
        batch = await db.get(BatchExperiment, batch_id)
        return not batch or batch.status in {"cancelling", "cancelled"}


async def _execute_run(run_id: int, safety_max_turns: int, locale: str | None) -> None:
    session_uuid: str | None = None
    try:
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if not run or run.status != "queued":
                return
            run.status = "running"
            run.started_at = _now()
            scenario_id, condition = run.scenario_id, run.condition
            repetition = run.repetition
            session = await memory_service.create_session(
                db,
                scenario_id,
                user_id=f"batch:{run.batch_id}:{run.id}",
                session_mode=condition,
                run_config={
                    "safety_max_turns": safety_max_turns,
                    "player_strategy": "balanced",
                    "player_temperature": 0.2,
                    "player_max_tokens": 512,
                    "working_message_limit": 30,
                    "comparison_protocol": "roommind-vs-central-prompt-v2",
                    "metrics_protocol": "roommind-core-outcomes-v2",
                    "comparison_lock_model": True,
                    "batch_experiment_run_id": run.id,
                },
            )
            session_uuid = session.session_uuid
            run.session_uuid = session_uuid
            await db.commit()

        # Commit each autonomous turn so progress survives a process restart.
        for _ in range(safety_max_turns):
            if await _batch_cancelled(run.batch_id):
                raise asyncio.CancelledError
            async with async_session_factory() as db:
                from app.api.game import _run_autonomous_step

                step = await _run_autonomous_step(db, session_uuid, locale)
                await db.commit()
            if step.get("status") != "active":
                break

        async with async_session_factory() as db:
            session = await memory_service.get_session(db, session_uuid)
            if not session:
                raise RuntimeError("Generated session disappeared")
            scenario = await orch_support.load_scenario(db, session.scenario_id)
            public = build_public_session_export_bundle(await build_session_export_bundle(db, session))
            evaluation = await evaluate_public_transcript(
                db,
                scenario=scenario,
                messages=public.get("messages") or [],
                system_claim=(public.get("external_observation") or {}).get("system_claim") or {},
            )
            shared = dict(session.shared_state or {})
            shared["_external_evaluation"] = evaluation
            session.shared_state = shared
            messages = public.get("messages") or []
            turn_ids = {
                row.get("turn_id")
                for row in messages
                if row.get("speaker_type") in {"user", "npc"} and row.get("turn_id") is not None
            }
            result = _flatten_result(
                scenario=scenario,
                condition=condition,
                repetition=repetition,
                session_uuid=session_uuid,
                session_status=session.status,
                message_count=len(messages),
                turn_count=len(turn_ids),
                evaluation=evaluation,
            )
            run = await db.get(BatchExperimentRun, run_id)
            if run:
                run.status = "completed"
                run.result = result
                run.finished_at = _now()
            await db.commit()
    except asyncio.CancelledError:
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if run and run.status not in {"completed", "failed"}:
                run.status = "cancelled"
                run.error = "Batch cancelled"
                run.finished_at = _now()
            await db.commit()
    except Exception as exc:  # one failed cell must not abort the experiment
        async with async_session_factory() as db:
            run = await db.get(BatchExperimentRun, run_id)
            if run:
                run.status = (
                    "evaluation_failed"
                    if "External evaluator" in str(exc)
                    else "failed"
                )
                run.error = str(exc)[:4000]
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
        batch.completed_runs = sum(row.status == "completed" for row in rows)
        batch.failed_runs = sum(row.status in {"failed", "evaluation_failed"} for row in rows)
        batch.cancelled_runs = sum(row.status == "cancelled" for row in rows)
        terminal = {"completed", "failed", "evaluation_failed", "cancelled"}
        if rows and all(row.status in terminal for row in rows):
            batch.status = "cancelled" if any(row.status == "cancelled" for row in rows) else "completed"
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
            if not batch or batch.status in {"completed", "cancelled"}:
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
            "comparison_protocol": "roommind-vs-central-prompt-v2",
            "metrics_protocol": "roommind-core-outcomes-v2",
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
                "technical_failure": run["status"] == "failed",
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
            if run.get("status") != "completed" or not run.get("session_uuid"):
                continue
            session = await memory_service.get_session(db, run["session_uuid"])
            if not session:
                continue
            public = build_public_session_export_bundle(
                await build_session_export_bundle(db, session)
            )
            packet = build_blinded_evaluation_packet(public)
            packet["run_label"] = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{batch_uuid}:{run['id']}")
            )[:12]
            packets.append(packet)
    return {
        "protocol": "optional-blinded-human-validation-v1",
        "condition_hidden": True,
        "required_for_primary_analysis": False,
        "rating_scale": "1-5",
        "rubric": [
            "role_believability",
            "realism_of_multiparticipant_conflict",
            "perceived_coherence",
        ],
        "packets": packets,
    }
