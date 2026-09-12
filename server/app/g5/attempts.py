"""Metadata-only attempt journal. Never persist exception text or credentials."""
import asyncio
from datetime import datetime, timezone
import uuid


def new_record(stage, version, actor):
    return {"attempt_id": uuid.uuid4().hex, "stage": stage, "version": version,
            "actor": actor, "status": "started", "error_code": "",
            "at": datetime.now(timezone.utc).isoformat()}


def finished(record, error=None):
    from app.g5.capacity import CapacityExceeded
    code = ""
    status = "succeeded"
    if error is not None:
        status = "failed"
        if isinstance(error, asyncio.CancelledError):
            code, status = "cancelled", "cancelled"
        elif isinstance(error, TimeoutError):
            code = "timeout"
        elif isinstance(error, ConnectionError):
            code = "connection"
        elif isinstance(error, CapacityExceeded):
            code = "capacity_exceeded"
        elif isinstance(error, ValueError):
            code = "invalid_or_conflicting_state"
        else:
            code = "internal"
        # A lost acknowledgement is not proof that the database rolled back.
        # The authoritative event log, not this status, decides the next cursor.
        if record["stage"] == "commit" and code != "invalid_or_conflicting_state":
            status = "indeterminate"
    return {**record, "status": status, "error_code": code,
            "at": datetime.now(timezone.utc).isoformat()}


def validate_record(record):
    if not isinstance(record, dict) or set(record) - {"reopen_request", "model_io"} != {
            "attempt_id", "stage", "version", "actor", "status", "error_code", "at"}:
        raise ValueError("Invalid attempt record")
    if "reopen_request" in record:
        from app.g5.reopening import validate
        validate(record["reopen_request"])
    if "model_io" in record:
        from app.g5.capacity import validate_measurements
        validate_measurements(record["model_io"])
    if record["stage"] not in ("observation", "cognition", "policy", "governance", "annotation", "session_annotation", "commit"):
        raise ValueError("Unknown attempt stage")
    if record["status"] not in ("started", "succeeded", "failed", "cancelled", "indeterminate"):
        raise ValueError("Unknown attempt status")
    if record["error_code"] not in ("", "timeout", "connection", "cancelled", "invalid_or_conflicting_state", "internal", "capacity_exceeded"):
        raise ValueError("Unsafe error code")
    if type(record["version"]) is not int or record["version"] < 0:
        raise ValueError("Invalid observed version")
    if not all(isinstance(record[k], str) and record[k] for k in ("actor", "attempt_id", "at")):
        raise ValueError("Missing attempt identity or time")
