"""Role-scoped, source-preserving memory ingestion and retrieval.

Default retrieval is lexical, not an embedding implementation. A declared local
semantic scorer can be injected. This module does not generate reflections or
claim memory retrieval alone constitutes the completed G5 cognition system.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re

from app.factorial_study import digest
from app.g5.world import canonical
from app.g5.semantic import Similarities

SCHEMA = "g5-source-memory-v1"


def tokens(text):
    # Latin words plus individual CJK characters; no claim of semantic matching.
    return set(re.findall(r"[a-z0-9_]+|[\u3400-\u9fff]", text.lower()))


class MemoryCognition:
    def __init__(self, *, top_k=8, semantic_scorer=None, semantic_id=None):
        if type(top_k) is not int or top_k < 1:
            raise ValueError("Positive retrieval count required")
        if (semantic_scorer is None) != (semantic_id is None):
            raise ValueError("Semantic scorer and its frozen ID must be supplied together")
        if semantic_id is not None and (not isinstance(semantic_id, str) or not semantic_id):
            raise ValueError("Semantic scorer ID is required")
        self.top_k, self.semantic_scorer = top_k, semantic_scorer
        self.specification = {"schema": SCHEMA, "top_k": top_k,
                              "retrieval": "lexical" if semantic_scorer is None else "hybrid",
                              "semantic_id": semantic_id}
        self.specification = self.runtime_specification()

    @staticmethod
    def policy_context(state):
        """Only selected memory reaches policy; the full store remains private."""
        return deepcopy(state["context"])

    def runtime_specification(self):
        spec = {**deepcopy(self.specification), "top_k": self.top_k,
                "retrieval": "lexical" if self.semantic_scorer is None else "hybrid"}
        spec.pop("semantic_specification", None)
        getter = getattr(self.semantic_scorer, "runtime_specification", None)
        if getter is not None:
            spec["semantic_specification"] = deepcopy(getter())
        return spec

    async def __call__(self, view):
        if self.runtime_specification() != self.specification:
            raise ValueError("Retrieval configuration drift")
        actor, scope = view["actor"], view.get("memory_scope")
        if not isinstance(scope, str) or not scope:
            raise ValueError("Explicit per-world memory scope required")
        previous = view.get("cognition_state") or {}
        if previous:
            if (previous.get("schema"), previous.get("owner"), previous.get("scope"),
                previous.get("configuration")) != (SCHEMA, actor, scope, self.specification):
                raise ValueError("Memory owner, world or retrieval configuration changed")
        nodes = deepcopy(previous.get("nodes", []))
        known = {}
        for node in nodes:
            raw = {k: v for k, v in node.items() if k != "id"}
            if node.get("id") != digest(raw) or node["id"] in known:
                raise ValueError("Memory node corruption or duplicate")
            known[node["id"]] = node

        def ingest(kind, source, text, key=None, disclosable=True):
            payload = {"kind": kind, "source": source, "text": text,
                       "fact_key": key, "disclosable": disclosable}
            node_id = digest(payload)
            if node_id not in known:
                node = {"id": node_id, **payload}
                nodes.append(node)
                known[node_id] = node
            return node_id

        current = {}
        for key, fact in sorted(view["facts"].items()):
            # This is the role-filtered view, never the whole world's truth map.
            current[key] = ingest("fact", fact["source"], canonical({key: fact["value"]}),
                                  key, fact["disclosable"])
        for observation in view["observations"]:
            kind = observation["kind"]
            if kind not in ("claim", "simulation_receipt"):
                raise ValueError("Unsupported observation kind")
            ingest(kind, observation["event_id"], canonical(observation))

        goals = view.get("own_role", {}).get("private", {}).get("goals", [])
        recent = view["observations"][-1:]  # current public issue, not hidden state
        query = canonical({"goals": goals, "latest_observation": recent})
        query_tokens = tokens(query)
        batch = None
        score_many = getattr(self.semantic_scorer, "score_many", None)
        if score_many is not None and nodes:
            batch = await score_many(query, [node["text"] for node in nodes])
            if not isinstance(batch, Similarities) or len(batch.scores) != len(nodes):
                raise ValueError("Invalid batch similarities")
        ranked = []
        for index, node in enumerate(nodes):
            words = tokens(node["text"])
            lexical = len(words & query_tokens) / max(1, len(words | query_tokens))
            semantic = None
            score = lexical
            if self.semantic_scorer is not None:
                semantic = batch.scores[index] if batch is not None else self.semantic_scorer(query, node["text"])
                if type(semantic) not in (int, float) or not math.isfinite(semantic) or not -1 <= semantic <= 1:
                    raise ValueError("Semantic scorer must return a finite similarity in [-1,1]")
                score = (lexical + (semantic + 1) / 2) / 2
            outdated = node["kind"] == "fact" and current.get(node["fact_key"]) != node["id"]
            ranked.append((score, index, {**node, "historical_fact": outdated,
                                          "lexical_score": lexical, "semantic_score": semantic}))
        selected = [row[2] for row in sorted(ranked, key=lambda row: (-row[0], -row[1]))[:self.top_k]]
        if self.runtime_specification() != self.specification:
            raise ValueError("Retrieval configuration drift")
        return {"schema": SCHEMA, "owner": actor, "scope": scope,
                "configuration": deepcopy(self.specification), "nodes": nodes,
                "retrieval_evidence": deepcopy(batch.evidence) if batch is not None else None,
                "context": {"retrieved": selected, "retrieval": self.specification["retrieval"],
                            "epistemic_rule": "Claims are claims; historical facts are not current state.",
                            "query_sha256": digest(query)}}
