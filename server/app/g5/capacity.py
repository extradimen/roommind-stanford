"""Opt-in frozen full-request byte limits, not tokenizer/context-window estimates.

Reject, never truncate. Metadata-only measurements are scoped to a runtime
attempt; this module neither discovers transports nor writes credentials/text.
Response limits apply after receipt, not to streaming/network allocation.
"""
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass

from app.factorial_study import digest
from app.g5.world import canonical

measurements = ContextVar("g5_model_io_measurements", default=None)


class CapacityExceeded(ValueError):
    pass


@dataclass(frozen=True)
class RequestBudget:
    max_request_bytes: int
    max_response_bytes: int

    def runtime_specification(self):
        if any(type(n) is not int or n < 1 for n in (self.max_request_bytes, self.max_response_bytes)):
            raise ValueError("Positive frozen byte limits required")
        return {"schema": "g5-whole-request-byte-budget-v1", "max_request_bytes": self.max_request_bytes,
                "max_response_bytes": self.max_response_bytes, "encoding": "canonical-json-utf8",
                "overflow": "fail-without-truncation", "token_count_claim": False}


class BudgetTransport:
    def __init__(self, delegate, budget, *, delegate_id):
        if not callable(delegate) or type(budget) is not RequestBudget or not isinstance(delegate_id, str) or not delegate_id.strip():
            raise ValueError("Explicit transport, budget and identity required")
        self.delegate, self.budget, self.delegate_id = delegate, budget, delegate_id
        self._frozen = self.runtime_specification()

    def runtime_specification(self):
        getter = getattr(self.delegate, "runtime_specification", None)
        return {"adapter": "g5-budgeted-transport-v1", "budget": self.budget.runtime_specification(),
                "delegate_id": self.delegate_id, "delegate_spec": deepcopy(getter()) if getter else None}

    async def __call__(self, request):
        if self.runtime_specification() != self._frozen:
            raise ValueError("Transport budget/binding drift")
        request = deepcopy(request)
        record = {"request_sha256": digest(request), "budget_sha256": digest(self.budget.runtime_specification()),
                  "request_bytes": len(canonical(request).encode("utf-8")), "response_bytes": None,
                  "status": "transport_failure"}
        try:
            if record["request_bytes"] > self.budget.max_request_bytes:
                record["status"] = "request_capacity_exceeded"
                raise CapacityExceeded("Full request exceeds frozen byte budget")
            result = await self.delegate(deepcopy(request))
            if not is_dataclass(result) or isinstance(result, type):
                raise ValueError("Explicit model/embedding receipt required")
            record["response_bytes"] = len(canonical(asdict(result)).encode("utf-8"))
            if record["response_bytes"] > self.budget.max_response_bytes:
                record["status"] = "response_capacity_exceeded"
                raise CapacityExceeded("Full response exceeds frozen byte budget")
            if self.runtime_specification() != self._frozen:
                raise ValueError("Transport changed during request")
            record["status"] = "received"
            return result
        finally:
            sink = measurements.get()
            if sink is not None:
                sink.append(deepcopy(record))


def validate_budget_spec(spec):
    if not isinstance(spec, dict) or RequestBudget(spec.get("max_request_bytes"), spec.get("max_response_bytes")).runtime_specification() != spec:
        raise ValueError("Unknown common request budget")


def verify_declared_budget(tree, expected):
    validate_budget_spec(expected)
    if isinstance(tree, dict):
        if tree.get("adapter") == "g5-budgeted-transport-v1":
            if tree.get("budget") != expected:
                raise ValueError("Transport has a different common budget")
            # The outer wrapper bounds its delegate's whole request/receipt.
            # A native HTTP delegate is not another model caller needing a
            # second wrapper; its frozen specification remains hash-bound.
            return
        if "adapter" in tree and isinstance(tree.get("binding"), dict) and "model" in tree["binding"]:
            transport = tree.get("transport") or {}
            if transport.get("adapter") != "g5-budgeted-transport-v1" or transport.get("budget") != expected:
                raise ValueError("Every declared model/embedding adapter needs the common budget")
        for value in tree.values():
            verify_declared_budget(value, expected)
    elif isinstance(tree, list):
        for value in tree:
            verify_declared_budget(value, expected)


def verify_runtime_budget(adapters, expected):
    seen = set()
    def visit(adapter):
        if adapter is None or id(adapter) in seen:
            return
        seen.add(id(adapter))
        binding = getattr(adapter, "binding", None)
        if binding is not None and hasattr(binding, "model"):
            transport = getattr(adapter, "transport", None)
            if type(transport) is not BudgetTransport or transport.budget.runtime_specification() != expected:
                raise ValueError("Runtime model adapter lacks the frozen request budget")
        for name in ("memory", "semantic_scorer", "reflector", "planner", "auditor"):
            visit(getattr(adapter, name, None))
    for adapter in adapters:
        visit(adapter)


def validate_measurements(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Nonempty model IO measurements required")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"request_sha256", "budget_sha256", "request_bytes", "response_bytes", "status"}:
            raise ValueError("Invalid IO metadata")
        for key in ("request_sha256", "budget_sha256"):
            if not isinstance(row[key], str) or len(row[key]) != 64 or any(c not in "0123456789abcdef" for c in row[key]):
                raise ValueError("Invalid IO checksum")
        if type(row["request_bytes"]) is not int or row["request_bytes"] < 1 or (
                row["response_bytes"] is not None and (type(row["response_bytes"]) is not int or row["response_bytes"] < 1)):
            raise ValueError("Invalid IO byte count")
        if row["status"] not in {"received", "transport_failure", "request_capacity_exceeded", "response_capacity_exceeded"}:
            raise ValueError("Invalid IO status")
        if row["status"] in {"received", "response_capacity_exceeded"} and row["response_bytes"] is None:
            raise ValueError("Received response size is missing")
        if row["status"] == "request_capacity_exceeded" and row["response_bytes"] is not None:
            raise ValueError("Rejected request cannot have a response")
