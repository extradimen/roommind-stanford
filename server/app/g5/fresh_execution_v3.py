"""Versioned recovery binding for the failed fresh-family v2 execution."""
from app.factorial_study import digest
from app.g5.fresh_execution_v2 import execution_binding as _v2_binding, run_execution


def execution_binding(source_revision, *, authorization_id, predecessor_execution_sha256):
    if (not isinstance(predecessor_execution_sha256, str)
            or len(predecessor_execution_sha256) != 64
            or any(c not in "0123456789abcdef" for c in predecessor_execution_sha256)):
        raise ValueError("Exact failed predecessor execution checksum required")
    value = _v2_binding(source_revision, authorization_id=authorization_id,
                        reasoning_effort="low")
    raw = {key: item for key, item in value.items() if key != "sha256"}
    raw.update(schema="g5-fresh-family-v3-execution-binding-v1",
               predecessor_execution_sha256=predecessor_execution_sha256,
               recovery_reason="reasoning_length_and_shared_world_identity")
    return {**raw, "sha256": digest(raw)}


__all__ = ["execution_binding", "run_execution"]
