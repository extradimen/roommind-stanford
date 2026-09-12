import copy
import unittest
from dataclasses import replace

from app.factorial_study import digest
from app.g5.semantic import EmbeddingBinding, EmbeddingCompletion, EmbeddingScorer
from app.g5.memory import MemoryCognition
from test_g5_memory import view


class SemanticTests(unittest.IsolatedAsyncioTestCase):
    binding = EmbeddingBinding("offline", "synthetic-vectors", "test", 2)

    def scorer(self, vectors, transform=lambda r: r):
        async def transport(request):
            return transform(EmbeddingCompletion(self.binding, digest(request), vectors))
        return EmbeddingScorer(self.binding, transport)

    async def test_cosine_and_extreme_values(self):
        result = await self.scorer([[1e308, 1e308], [1, 1], [-1, -1], [1, -1]]).score_many("q", ["a", "b", "c"])
        for actual, expected in zip(result.scores, [1, -1, 0]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(result.evidence["vectors_sha256"], digest([[1e308, 1e308], [1, 1], [-1, -1], [1, -1]]))

    async def test_invalid_vectors_and_receipts(self):
        for vectors in ([[1, 0]], [[1, 0], [0, 0]], [[1, 0], [True, 1]],
                        [[1, 0], [float("nan"), 1]], [[1, 0], [1]]):
            with self.assertRaises(ValueError):
                await self.scorer(vectors).score_many("q", ["a"])
        with self.assertRaises(ValueError):
            await self.scorer([[1, 0], [1, 0]], lambda r: replace(r, request_sha256="wrong")).score_many("q", ["a"])

    async def test_batch_memory_integration_private_evidence(self):
        calls = []
        async def transport(request):
            calls.append(copy.deepcopy(request))
            return EmbeddingCompletion(self.binding, digest(request), [[1, 0] for _ in request["input"]])
        memory = MemoryCognition(semantic_scorer=EmbeddingScorer(self.binding, transport), semantic_id="v1")
        source = view()
        source["world_audit"] = "not-for-embedding"
        state = await memory(source)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]["input"]), len(state["nodes"]) + 1)
        self.assertNotIn("not-for-embedding", str(calls))
        self.assertTrue(state["retrieval_evidence"])
        self.assertNotIn("retrieval_evidence", memory.policy_context(state))
        self.assertEqual(state["context"]["retrieval"], "hybrid")

    async def test_failure_preserves_input_and_binding_drift(self):
        async def failed(request):
            raise TimeoutError("offline failure")
        scorer = EmbeddingScorer(self.binding, failed)
        memory = MemoryCognition(semantic_scorer=scorer, semantic_id="v1")
        source = view()
        before = copy.deepcopy(source)
        with self.assertRaises(TimeoutError):
            await memory(source)
        self.assertEqual(source, before)
        scorer.binding = replace(self.binding, model="other")
        with self.assertRaises(ValueError):
            await memory(source)

    async def test_empty_memory_does_not_call_embedding(self):
        async def unexpected(request):
            self.fail("No evidence to rank")
        memory = MemoryCognition(semantic_scorer=EmbeddingScorer(self.binding, unexpected), semantic_id="v1")
        source = view()
        source["facts"], source["observations"] = {}, []
        state = await memory(source)
        self.assertEqual(state["context"]["retrieved"], [])
        self.assertIsNone(state["retrieval_evidence"])
