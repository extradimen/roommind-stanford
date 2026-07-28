"""Structured operational telemetry without secrets or private prompt content."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator
from pathlib import Path

logger = logging.getLogger("roommind.telemetry")
_context: ContextVar[dict[str, Any]] = ContextVar("roommind_telemetry_context", default={})


def configure_telemetry() -> Path:
    """Write structured events to a bounded, independently rotatable file."""
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "telemetry.log"
    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        handler = RotatingFileHandler(
            path,
            maxBytes=50 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return path


@contextmanager
def telemetry_context(**values: Any) -> Iterator[None]:
    merged = {**_context.get(), **{key: value for key, value in values.items() if value is not None}}
    token = _context.set(merged)
    try:
        yield
    finally:
        _context.reset(token)


def emit(event: str, **fields: Any) -> None:
    context = _context.get()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{key: value for key, value in context.items() if not key.startswith("_")},
        **{key: value for key, value in fields.items() if value is not None},
    }
    collector = context.get("_collector")
    if isinstance(collector, list):
        collector.append(payload)
    logger.info("ROOMMIND_EVENT %s", json.dumps(payload, ensure_ascii=False, default=str))


def monotonic_ms(start: float) -> int:
    return max(0, round((time.monotonic() - start) * 1000))
