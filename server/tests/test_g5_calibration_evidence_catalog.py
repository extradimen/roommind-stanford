"""Immutable evidence-catalog protocol tests; no external calls."""
import copy
import json
import unittest

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import CatalogEvidencePredictor, evidence_catalog, localize_output
from app.g5.model_policy import Completion, ModelBinding


class CatalogEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.task = {"case_id": "x", "dimension": "procedural_fidelity", "rubric": "Respect authority.",
            "context": {}, "messages": [
                {"message_id": "m1", "speaker_id": "alice", "turn_id": 1, "sequence_no": 1,
                 "content": "Wait. I can propose containment; approval remains with Bob."},
                {"message_id": "m2", "speaker_id": "bob", "turn_id": 1, "sequence_no": 2,
                 "content": "I confirm recovery."}]}

    async def test_catalog_is_deterministic_ordered_and_source_bound(self):
        first = evidence_catalog(self.task)
        self.assertEqual(first, evidence_catalog(copy.deepcopy(self.task)))
        self.assertEqual([unit["evidence_id"] for unit in first],
                         [f"E{number:04d}" for number in range(1, len(first) + 1)])
        for unit in first:
            message = next(item for item in self.task["messages"] if item["message_id"] == unit["message_id"])
            self.assertEqual(message["content"][unit["start"]:unit["end"]], unit["quote"])

    async def test_code_maps_id_to_exact_speaker_quote_and_unicode_offsets(self):
        unit = next(item for item in evidence_catalog(self.task) if "confirm recovery" in item["quote"])
        parsed = {"prediction": "clear", "rationale": "The authorized role confirms.",
            "citations": [{"evidence_id": unit["evidence_id"], "relevance": "Authorized confirmation."}]}
        output = localize_output(self.task, parsed)
        evidence = output["evidence"][0]
        self.assertEqual(evidence["speaker_id"], "bob")
        self.assertEqual(evidence["quote"], "I confirm recovery.")

    async def test_unknown_duplicate_bad_shape_and_missing_decisive_evidence_rejected(self):
        evidence_id = evidence_catalog(self.task)[0]["evidence_id"]
        valid = {"prediction": "clear", "rationale": "x",
            "citations": [{"evidence_id": evidence_id, "relevance": "x"}]}
        variants = []
        value = copy.deepcopy(valid); value["citations"][0]["evidence_id"] = "E9999"; variants.append(value)
        value = copy.deepcopy(valid); value["citations"].append(copy.deepcopy(value["citations"][0])); variants.append(value)
        value = copy.deepcopy(valid); value["citations"][0]["extra"] = True; variants.append(value)
        value = copy.deepcopy(valid); value["citations"] = []; variants.append(value)
        for value in variants:
            with self.assertRaises(ValueError):
                localize_output(self.task, value)

    async def test_receipt_and_frozen_plan(self):
        binding = ModelBinding("offline", "fixed", "mock", 0, 8192)
        evidence_id = evidence_catalog(self.task)[-1]["evidence_id"]
        output = {"prediction": "clear", "rationale": "Authorized confirmation.",
            "citations": [{"evidence_id": evidence_id, "relevance": "Direct confirmation."}]}
        async def transport(request):
            return Completion(json.dumps(output), "offline", "fixed", "mock", digest(request), "stop")
        predictor = CatalogEvidencePredictor(binding, transport, predictor_id="fixture", kind="synthetic")
        result = await predictor.predict(self.task, predictor.plan())
        self.assertEqual(result["output"]["evidence"][0]["speaker_id"], "bob")
        plan = predictor.plan(); predictor.predictor_id = "changed"
        with self.assertRaises(ValueError):
            await predictor.predict(self.task, plan)


if __name__ == "__main__":
    unittest.main()
