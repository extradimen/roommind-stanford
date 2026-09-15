"""Common whole-observation suffix, applied before every factorial mechanism.

This bounds raw observations, not the entire prompt or model tokenizer budget.
It never grants cognition a separate backfill path. Durable world history stays
unchanged. Public queue/session projections are separate shared mechanisms.
"""
from copy import deepcopy
from dataclasses import dataclass

from app.factorial_study import digest
from app.g5.world import canonical


@dataclass(frozen=True)
class ObservationWindow:
    max_observations: int
    max_chars: int

    def runtime_specification(self):
        if (type(self.max_observations) is not int or self.max_observations < 1
                or type(self.max_chars) is not int or self.max_chars < 2):
            raise ValueError("Positive observation count and JSON character capacity required")
        return {"schema": "g5-common-observation-window-v1", "max_observations": self.max_observations,
                "max_chars": self.max_chars, "selection": "newest-contiguous-whole-observations",
                "scope": "all-arms-before-cognition-policy-governance-annotation",
                "oversized_latest": "fail-without-publication", "cognition_backfill": False}

    def apply(self, view):
        spec = self.runtime_specification()
        observations = view["observations"]
        if not isinstance(observations, list):
            raise ValueError("Observation list required")
        selected = []
        for observation in reversed(observations[-self.max_observations:]):
            candidate = [observation, *selected]
            if len(canonical(candidate)) > self.max_chars:
                if not selected:
                    raise ValueError("Latest whole observation exceeds frozen capacity")
                break
            selected = candidate
        result = deepcopy(view)
        result["observations"] = deepcopy(selected)
        metadata = {"available_count": len(observations), "delivered_count": len(selected),
                    "omitted_count": len(observations) - len(selected),
                    "meaning": "Only this recent suffix was delivered now. Omitted observations are not new knowledge; absence here is not disproof of an earlier event."}
        result["observation_delivery"] = metadata
        receipt = {**metadata, "specification_sha256": digest(spec),
            "visible_history_sha256": digest(observations), "delivered_sha256": digest(selected),
            "delivered_ids": [o["event_id"] for o in selected], "json_chars": len(canonical(selected))}
        return result, receipt
