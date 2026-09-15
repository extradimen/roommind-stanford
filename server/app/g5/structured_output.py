"""Shared, bounded repair evidence for internal structured model outputs."""
from copy import deepcopy

from app.factorial_study import digest

PROTOCOL = "g5-validated-structured-generation-v1"


class StructuredOutputError(ValueError):
    """Safe public error plus internal rejected-output capsules."""

    def __init__(self, message, failures):
        super().__init__(message)
        validate_failures(failures)
        self.structured_failures = deepcopy(failures)


def repair_spec(max_revisions):
    if type(max_revisions) is not int or not 0 <= max_revisions <= 4:
        raise ValueError("Bounded structured revisions required")
    return {"schema": PROTOCOL, "max_revisions": max_revisions,
            "rejected_content": "internal-attempt-journal-only"}


def classify(message):
    text = str(message)
    lower = text.lower()
    if "task transition needs observed evidence" in lower:
        return "transition_evidence", "$.updates[*].status_source_ids"
    if "task identity cannot silently change" in lower:
        return "identity", "$.updates[*]"
    if "retroactively create completed intentions" in lower:
        return "transition", "$.updates[*].status"
    if "terminal task is immutable" in lower:
        return "terminal_identity", "$.updates[*].id"
    if "updated task cites evidence outside supplied context" in lower:
        return "reference", "$.updates[*].source_ids|status_source_ids"
    if "completion requires" in lower:
        return "transition_evidence", "$.updates[*].status_source_ids"
    if "source" in lower or "evidence" in lower or "target" in lower or "question" in lower:
        return "reference", "$"
    if "span" in lower or "offset" in lower:
        return "span", "$"
    if "json" in lower:
        return "parse", "$"
    if "envelope" in lower or "fields" in lower or "object" in lower or "list" in lower:
        return "envelope", "$"
    if "status" in lower or "transition" in lower or "terminal" in lower or "prerequisite" in lower:
        return "transition", "$"
    if "actor" in lower or "operation" in lower or "permission" in lower:
        return "authority", "$"
    return "semantic_validation", "$"


def capsule(component, revision, request_sha256, response_content, error, *,
            field_path=None, allowed_values=None):
    if not isinstance(response_content, str):
        response_content = ""
    code, inferred_path = classify(error)
    result = {
        "schema": "g5-structured-rejection-capsule-v1",
        "component": component,
        "revision": revision,
        "error_code": code,
        "field_path": field_path or inferred_path,
        "invariant": str(error),
        "message": str(error),
        "request_sha256": request_sha256,
        "response_sha256": digest(response_content),
        "response_content": response_content,
    }
    if allowed_values is not None:
        result["allowed_values"] = deepcopy(allowed_values)
    validate_failure(result)
    return result


def feedback(failure, revision):
    validate_failure(failure)
    result = {
        "schema": PROTOCOL,
        "revision": revision,
        "error": {key: deepcopy(failure[key]) for key in
                  ("error_code", "field_path", "invariant", "message")},
        "instruction": "Return a new complete structure correcting only the rejected fields.",
    }
    if "allowed_values" in failure:
        result["allowed_values"] = deepcopy(failure["allowed_values"])
    return result


def validate_failure(row):
    required = {"schema", "component", "revision", "error_code", "field_path", "invariant", "message",
                "request_sha256", "response_sha256", "response_content"}
    if not isinstance(row, dict) or set(row) not in (required, required | {"allowed_values"}):
        raise ValueError("Invalid structured rejection capsule")
    if row["schema"] != "g5-structured-rejection-capsule-v1":
        raise ValueError("Unknown structured rejection capsule")
    if type(row["revision"]) is not int or row["revision"] < 0:
        raise ValueError("Invalid structured rejection revision")
    if not all(isinstance(row[key], str) and row[key] for key in
               ("component", "error_code", "field_path", "invariant", "message")):
        raise ValueError("Incomplete structured rejection classification")
    if not isinstance(row["response_content"], str):
        raise ValueError("Rejected response must remain internal text")
    for key in ("request_sha256", "response_sha256"):
        value = row[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Invalid structured rejection checksum")
    if row["response_sha256"] != digest(row["response_content"]):
        raise ValueError("Rejected response checksum mismatch")


def validate_failures(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Nonempty structured rejection history required")
    for row in rows:
        validate_failure(row)


def rebased(rows, revision):
    """Assign the outer bounded-attempt index to parser/envelope failures."""
    validate_failures(rows)
    result = deepcopy(rows)
    for row in result:
        row["revision"] = revision
        validate_failure(row)
    return result
