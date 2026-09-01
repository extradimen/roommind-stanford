"""Run one real autonomous RoomMind turn per model against two isolated revisions.

This is a technical screening experiment, not a realism evaluation.  It alternates
old/new architecture cells while sharing the same scenario and model identifier.
The script updates only the active LLM row in each isolated experiment database and
writes every API result incrementally so a slow or failed model cannot erase earlier
evidence.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _database_url(worktree: Path) -> str:
    # RoomMind's runtime database binding comes from config/platform.json, not
    # DATABASE_URL in .env.  The experiment harness must resolve the same source
    # as app.config.get_settings(), otherwise it can update a different database
    # while the API silently keeps using its original model.
    raw = json.loads((worktree / "config" / "platform.json").read_text(encoding="utf-8"))
    database = raw.get("database") or {}
    ports = raw.get("ports") or {}
    user = str(database.get("user") or "roommind")
    password = str(database.get("password") or "roommind_dev")
    name = str(database.get("name") or "roommind")
    port = int(ports.get("postgres") or 5434)
    return f"postgresql+asyncpg://{user}:{password}@127.0.0.1:{port}/{name}"


async def _set_model(worktree: Path, model: str) -> None:
    engine = create_async_engine(_database_url(worktree), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(
                text(
                    "UPDATE llm_configs SET provider = 'ollama', model = :model, "
                    "updated_at = CURRENT_TIMESTAMP WHERE is_active IS TRUE"
                ),
                {"model": model},
            )
            if result.rowcount < 1:
                raise RuntimeError(f"No active llm_configs row in {worktree}")
    finally:
        await engine.dispose()


async def _scenario_id(client: httpx.AsyncClient, api_url: str, slug: str) -> int:
    response = await client.get(f"{api_url}/api/game/scenarios")
    response.raise_for_status()
    for item in response.json():
        if item.get("slug") == slug:
            return int(item["id"])
    raise RuntimeError(f"Scenario {slug!r} was not found at {api_url}")


async def _cell(
    client: httpx.AsyncClient,
    *,
    architecture: dict[str, Any],
    model: str,
    scenario_id: int,
) -> dict[str, Any]:
    api_url = architecture["api_url"]
    await _set_model(Path(architecture["worktree"]), model)
    started = time.monotonic()
    row: dict[str, Any] = {
        "architecture": architecture["name"],
        "revision": architecture["revision"],
        "model": model,
        "started_at": _now(),
        "duration_ms": None,
        "status": "running",
        "http_status": None,
        "session_uuid": None,
        "error_type": None,
        "error": None,
        "step": None,
        "session_export": None,
    }
    try:
        created = await client.post(
            f"{api_url}/api/game/sessions",
            json={
                "scenario_id": scenario_id,
                "user_id": f"model-smoke-{architecture['name']}",
                "session_mode": "test",
                "run_config": {
                    "comparison_protocol": "model-architecture-smoke-v1",
                    "comparison_lock_model": True,
                    "shared_player_policy": "public-only-comparison-player-v1",
                    "safety_max_turns": 10,
                    "max_stagnant_turns": 6,
                    "random_seed": 20260901,
                },
            },
        )
        row["http_status"] = created.status_code
        created.raise_for_status()
        session_uuid = str(created.json()["session_uuid"])
        row["session_uuid"] = session_uuid
        response = await client.post(
            f"{api_url}/api/game/sessions/{session_uuid}/test/step",
            json={"max_steps": 1, "until_complete": False, "locale": "en"},
        )
        row["http_status"] = response.status_code
        if response.status_code >= 400:
            row["status"] = "failed"
            row["error_type"] = "http_error"
            row["error"] = response.text[:2000]
        else:
            row["status"] = "completed"
            row["step"] = response.json()
            observed_model = str((row["step"].get("player_move") or {}).get("model") or "")
            row["observed_player_model"] = observed_model
            expected_model = f"ollama/{model}"
            if observed_model != expected_model:
                row["status"] = "invalid_binding"
                row["error_type"] = "model_binding_mismatch"
                row["error"] = (
                    f"Expected {expected_model!r}, observed {observed_model!r}; "
                    "cell excluded from model comparison"
                )
        export_response = await client.get(
            f"{api_url}/api/game/sessions/{session_uuid}/export"
        )
        if export_response.status_code < 400:
            row["session_export"] = export_response.json()
    except Exception as exc:
        row["status"] = "failed"
        row["error_type"] = type(exc).__name__
        row["error"] = repr(exc)[:2000]
    row["finished_at"] = _now()
    row["duration_ms"] = round((time.monotonic() - started) * 1000)
    return row


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    architectures = [
        {
            "name": "old_g1",
            "revision": args.old_revision,
            "worktree": str(args.old_worktree),
            "api_url": args.old_api.rstrip("/"),
        },
        {
            "name": "new_g1_1",
            "revision": args.new_revision,
            "worktree": str(args.new_worktree),
            "api_url": args.new_api.rstrip("/"),
        },
    ]
    result: dict[str, Any] = {
        "protocol": "roommind-model-architecture-one-turn-smoke-v1",
        "generated_at": _now(),
        "scenario_slug": args.scenario_slug,
        "sequential": True,
        "provider_failover": False,
        "architectures": architectures,
        "models": args.models,
        "cells": [],
    }
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        scenario_ids = {
            architecture["name"]: await _scenario_id(
                client, architecture["api_url"], args.scenario_slug
            )
            for architecture in architectures
        }
        for model in args.models:
            for architecture in architectures:
                row = await _cell(
                    client,
                    architecture=architecture,
                    model=model,
                    scenario_id=scenario_ids[architecture["name"]],
                )
                result["cells"].append(row)
                _write(args.output, result)
                print(
                    json.dumps(
                        {key: row.get(key) for key in (
                            "architecture", "model", "status", "http_status",
                            "duration_ms", "error_type",
                        )},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    result["finished_at"] = _now()
    _write(args.output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--old-worktree", type=Path, required=True)
    parser.add_argument("--new-worktree", type=Path, required=True)
    parser.add_argument("--old-api", default="http://127.0.0.1:9010")
    parser.add_argument("--new-api", default="http://127.0.0.1:9020")
    parser.add_argument("--old-revision", default="95b6594")
    parser.add_argument("--new-revision", default="ef8c4f7")
    parser.add_argument("--scenario-slug", default="market-launch-go-no-go")
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
