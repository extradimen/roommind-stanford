"""Versioned recovery with conservative plan preservation after repair exhaustion."""
from app.factorial_study import digest
from app.g5.fresh_execution_v2 import execution_binding as _base_binding, run_execution


def execution_binding(source_revision, *, authorization_id, predecessor_execution_sha256):
    if (not isinstance(predecessor_execution_sha256, str)
            or len(predecessor_execution_sha256) != 64
            or any(c not in "0123456789abcdef" for c in predecessor_execution_sha256)):
        raise ValueError("Exact failed predecessor execution checksum required")
    value = _base_binding(source_revision, authorization_id=authorization_id,
                          reasoning_effort="low", max_structured_revisions=3)
    raw = {key: item for key, item in value.items() if key != "sha256"}
    raw.update(schema="g5-fresh-family-v10-execution-binding-v1",
               predecessor_execution_sha256=predecessor_execution_sha256,
               recovery_reason="conservative_plan_preservation_after_repair_exhaustion")
    return {**raw, "sha256": digest(raw)}


__all__ = ["execution_binding", "run_execution"]
