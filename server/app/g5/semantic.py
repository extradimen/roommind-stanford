"""Batched embedding similarity with explicit provider receipts, no network discovery."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math

from app.factorial_study import digest


@dataclass(frozen=True)
class EmbeddingBinding:
    provider: str
    model: str
    endpoint_id: str
    dimensions: int

    def validate(self):
        if any(not isinstance(s, str) or not s or s != s.strip()
               for s in (self.provider, self.model, self.endpoint_id)):
            raise ValueError("Explicit embedding binding required")
        if "://" in self.endpoint_id or type(self.dimensions) is not int or self.dimensions < 1:
            raise ValueError("Invalid embedding binding")


@dataclass(frozen=True)
class EmbeddingCompletion:
    binding: EmbeddingBinding
    request_sha256: str
    vectors: list


@dataclass(frozen=True)
class Similarities:
    scores: list
    evidence: dict


class EmbeddingScorer:
    def __init__(self, binding: EmbeddingBinding, transport):
        binding.validate()
        self.binding, self.transport = binding, transport

    def runtime_specification(self):
        self.binding.validate()
        spec = {"adapter": "g5-batch-cosine-v1", "binding": asdict(self.binding)}
        getter = getattr(self.transport, "runtime_specification", None)
        if getter is not None:
            from copy import deepcopy
            spec["transport"] = deepcopy(getter())
        return spec

    async def score_many(self, query, texts):
        if not isinstance(query, str) or not isinstance(texts, list) or any(not isinstance(t, str) for t in texts):
            raise ValueError("Embedding input must be text")
        spec = self.runtime_specification()
        request = {"binding": asdict(self.binding), "input": [query, *texts]}
        request_hash = digest(request)
        response = await self.transport(request)
        if (not isinstance(response, EmbeddingCompletion) or response.binding != self.binding
                or response.request_sha256 != request_hash or spec != self.runtime_specification()):
            raise ValueError("Embedding receipt mismatch")
        if not isinstance(response.vectors, list) or len(response.vectors) != len(texts) + 1:
            raise ValueError("Embedding count mismatch")
        normalized = []
        for vector in response.vectors:
            if (not isinstance(vector, list) or len(vector) != self.binding.dimensions
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector)):
                raise ValueError("Invalid embedding vector")
            scale = max(abs(v) for v in vector)
            if scale == 0:
                raise ValueError("Zero embedding vector")
            scaled = [v / scale for v in vector]
            norm = math.sqrt(sum(v * v for v in scaled))
            normalized.append([v / norm for v in scaled])
        scores = [max(-1.0, min(1.0, sum(a*b for a, b in zip(normalized[0], v))))
                  for v in normalized[1:]]
        return Similarities(scores, {"specification": spec, "request_sha256": request_hash,
                                     "vectors_sha256": digest(response.vectors)})
