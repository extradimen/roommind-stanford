import copy
import json
import unittest
from dataclasses import replace

from app.factorial_study import digest
from app.g5.memory import MemoryCognition
from app.g5.model_cognition import ModelCognitionGenerator
from app.g5.model_policy import Completion, ModelBinding
from app.g5.reflection import ReflectiveCognition
from test_g5_reflection import view


class CognitiveModelTests(unittest.IsolatedAsyncioTestCase):
    binding = ModelBinding("ollama", "fixed", "offline", 0.2, 512)

    def build(self, mutate=lambda kind, body: body, receipt=lambda r: r):
        calls = []
        def generator(kind):
            async def transport(request):
                calls.append(copy.deepcopy(request))
                ctx = json.loads(request["messages"][1]["content"])
                ids = [n["id"] for n in ctx["memory"]["retrieved"]][:1]
                body = ({"hypotheses": [{"text": "May need clarification", "source_ids": ids}] if ids else []}
                        if kind == "reflection" else {"goal": "Clarify", "steps": [{
                            "actor": ctx["actor"], "intent": "ask", "text": "Ask for context",
                            "operation": "", "source_ids": ids}]})
                return receipt(Completion(json.dumps(mutate(kind, body)), "ollama", "fixed", "offline",
                                          digest(request), "stop"))
            return ModelCognitionGenerator(kind, self.binding, transport)
        adapter = ReflectiveCognition(memory=MemoryCognition(), reflector=generator("reflection"),
                                      planner=generator("planning"), reflector_id="model-r", planner_id="model-p")
        return adapter, calls

    async def test_roundtrip_receipts_and_no_repeat(self):
        adapter, calls = self.build()
        source = view()
        source["world_audit"] = "never-transmit"
        state = await adapter(source)
        self.assertEqual(len(state["generation_receipts"]), 2)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("never-transmit", json.dumps(calls))
        self.assertNotIn("generation_receipts", json.dumps(adapter.policy_context(state)))
        source["cognition_state"] = state
        self.assertEqual(await adapter(source), state)
        self.assertEqual(len(calls), 2)

    async def test_bad_receipt_rejected(self):
        for change in ({"model": "wrong"}, {"finish_reason": "length"}, {"request_sha256": "wrong"}):
            adapter, _ = self.build(receipt=lambda r: replace(r, **change))
            with self.assertRaises(ValueError):
                await adapter(view())

    async def test_semantic_structure_validation_remains_in_composition(self):
        def forged(kind, body):
            if kind == "reflection":
                body["hypotheses"][0]["source_ids"] = ["invisible"]
            return body
        adapter, calls = self.build(forged)
        with self.assertRaises(ValueError):
            await adapter(view())
        self.assertEqual(len(calls), 1)

    async def test_failed_plan_preserves_previous_state(self):
        good, _ = self.build()
        source = view()
        first = await good(source)
        source["cognition_state"] = copy.deepcopy(first)
        source["observations"].append({"event_id": "new", "kind": "claim", "actor": "sre", "content": "New issue"})
        def invalid(kind, body):
            if kind == "planning":
                body["steps"][0]["actor"] = "other-role"
            return body
        bad, _ = self.build(invalid)
        with self.assertRaises(ValueError):
            await bad(source)
        self.assertEqual(source["cognition_state"], first)

    async def test_model_configuration_drift_before_call(self):
        adapter, calls = self.build()
        adapter.planner.binding = replace(self.binding, model="other")
        with self.assertRaises(ValueError):
            await adapter(view())
        self.assertEqual(calls, [])

    async def test_bad_envelope_and_corrupt_receipt(self):
        adapter, _ = self.build(lambda kind, body: {"extra": body})
        with self.assertRaises(ValueError):
            await adapter(view())
        adapter, _ = self.build()
        source = view()
        state = await adapter(source)
        state["generation_receipts"][0]["evidence"]["finish_reason"] = "forged"
        source["cognition_state"] = state
        with self.assertRaises(ValueError):
            await adapter(source)
