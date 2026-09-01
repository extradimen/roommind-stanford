"""Sequential raw-provider qualification for controlled RoomMind experiments.

This probe intentionally bypasses RoomMind's retry/fallback policy.  It answers a
smaller question before an end-to-end run: did the selected provider/model return
usable visible content for the kinds of prompts RoomMind sends?

No API keys or response text are written to the result.  Run from the repository
root with ``PYTHONPATH=server .venv/bin/python server/tests/model_provider_qualification.py``.
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

from app.llm.client import LLMClient
from app.ollama_catalog import fetch_ollama_cloud_catalog
from app.platform_llm import (
    available_models,
    resolve_ollama_api_key,
    resolve_ollama_base_url,
    resolve_siliconflow_api_key,
    resolve_siliconflow_base_url,
)


PROBES: tuple[dict[str, Any], ...] = (
    {
        "name": "short_visible_text",
        "messages": [
            {"role": "system", "content": "Reply with visible text only."},
            {"role": "user", "content": "Reply with exactly READY."},
        ],
        "max_tokens": 128,
        "response_format": None,
        "expect_json": False,
    },
    {
        "name": "structured_role_decision",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are one participant in a business meeting. Return one JSON "
                    "object only with keys action, rationale, and confidence. The action "
                    "must be speak or wait. Do not add markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    "The chair asks whether the launch should proceed while one quality "
                    "risk remains unresolved. Decide your next action."
                ),
            },
        ],
        "max_tokens": 768,
        "response_format": {"type": "json_object"},
        "expect_json": True,
    },
    {
        "name": "bounded_long_context_json",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a role-consistent meeting participant. Use the public history "
                    "and return JSON only with keys action, message, and open_issue.\n" +
                    ("Earlier public discussion: price, delivery, quality, authority, and "
                     "unresolved evidence were discussed without final agreement. " * 90)
                ),
            },
            {
                "role": "user",
                "content": "Choose a concise next move without inventing new numerical facts.",
            },
        ],
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
        "expect_json": True,
    },
)


def _chat_url(provider: str) -> str:
    if provider == "ollama":
        base = resolve_ollama_base_url().rstrip("/")
    else:
        base = resolve_siliconflow_base_url().rstrip("/")
    return f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"


def _api_key(provider: str) -> str:
    return resolve_ollama_api_key() if provider == "ollama" else resolve_siliconflow_api_key()


def _json_valid(content: Any) -> bool:
    if not isinstance(content, str) or not content.strip():
        return False
    try:
        return isinstance(json.loads(content), dict)
    except json.JSONDecodeError:
        return False


async def _probe_once(
    client: httpx.AsyncClient,
    provider: str,
    model: str,
    probe: dict[str, Any],
    repetition: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": probe["messages"],
        "temperature": 0.0,
        "max_tokens": probe["max_tokens"],
        "stream": False,
    }
    if probe["response_format"]:
        payload["response_format"] = probe["response_format"]
    LLMClient()._apply_provider_payload(payload, provider, model)
    started = time.monotonic()
    row: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "probe": probe["name"],
        "repetition": repetition,
        "http_status": None,
        "latency_ms": None,
        "finish_reason": None,
        "visible_characters": 0,
        "json_valid": None,
        "usable": False,
        "error_type": None,
        "error": None,
    }
    try:
        response = await client.post(
            _chat_url(provider),
            headers={
                "Authorization": f"Bearer {_api_key(provider)}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        row["latency_ms"] = round((time.monotonic() - started) * 1000)
        row["http_status"] = response.status_code
        if response.status_code >= 400:
            row["error_type"] = "http_error"
            row["error"] = response.text[:300]
            return row
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content")
        row["finish_reason"] = choice.get("finish_reason")
        row["visible_characters"] = len(content) if isinstance(content, str) else 0
        if probe["expect_json"]:
            row["json_valid"] = _json_valid(content)
            row["usable"] = bool(content and content.strip() and row["json_valid"])
        else:
            row["usable"] = bool(isinstance(content, str) and content.strip())
        if not row["usable"]:
            row["error_type"] = "unusable_success_response"
        return row
    except Exception as exc:  # qualification must retain every failed cell
        row["latency_ms"] = round((time.monotonic() - started) * 1000)
        row["error_type"] = type(exc).__name__
        row["error"] = repr(exc)[:300]
        return row


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    catalog = available_models()
    catalog_metadata: dict[str, Any] = {
        "source": "configured_fallback",
        "live": False,
    }
    if args.catalog_source == "live" and (not args.providers or "ollama" in args.providers):
        live_models, catalog_metadata = await fetch_ollama_cloud_catalog()
        if not catalog_metadata.get("live"):
            raise RuntimeError(
                "Live Ollama Cloud catalog was requested but could not be fetched: "
                f"{catalog_metadata.get('error') or 'unknown error'}"
            )
        catalog["ollama"] = [item["id"] for item in live_models]
    providers = args.providers or list(catalog)
    candidates = [
        (provider, model)
        for provider in providers
        for model in catalog.get(provider, [])
        if not args.models or model in args.models
    ]
    rows: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        for provider, model in candidates:
            if not _api_key(provider):
                rows.append({
                    "provider": provider,
                    "model": model,
                    "probe": "configuration",
                    "repetition": 0,
                    "usable": False,
                    "error_type": "missing_api_key",
                    "error": f"{provider} API key is not configured",
                })
                continue
            for repetition in range(1, args.repetitions + 1):
                for probe in PROBES:
                    row = await _probe_once(client, provider, model, probe, repetition)
                    rows.append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row['provider']}/{row['model']}"
        group = grouped.setdefault(key, {"attempts": 0, "usable": 0, "failures": {}})
        group["attempts"] += 1
        if row.get("usable"):
            group["usable"] += 1
        else:
            failure = str(row.get("error_type") or "unknown")
            group["failures"][failure] = group["failures"].get(failure, 0) + 1
    for group in grouped.values():
        group["usable_rate"] = round(group["usable"] / max(group["attempts"], 1), 4)
    return {
        "protocol": "roommind-model-provider-qualification-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "sequential": True,
        "provider_failover": False,
        "catalog_source": args.catalog_source,
        "catalog_metadata": catalog_metadata,
        "repetitions": args.repetitions,
        "candidates": [f"{provider}/{model}" for provider, model in candidates],
        "summary": grouped,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", nargs="*", choices=["ollama", "siliconflow"])
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--catalog-source",
        choices=["live", "fallback"],
        default="live",
        help="Use the live Ollama Cloud catalog by default; fallback is only for reproducing older runs.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
