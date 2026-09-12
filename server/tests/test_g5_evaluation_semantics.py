"""Condition-neutral semantic scoring contract tests; no model or network calls."""
import copy
import json
import unittest

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import CatalogEvidencePredictor, PROMPT as CATALOG_PROMPT, request_for
from app.g5.evaluation import PROMPT as EVALUATION_PROMPT
from app.g5.evaluation_semantics import (DIMENSIONS, semantic_contract, semantic_contract_for_dimension,
    semantic_contract_sha256, validate_semantic_contract)
from app.g5.model_policy import ModelBinding


class EvaluationSemanticContractTests(unittest.TestCase):
    def test_contract_is_frozen_condition_neutral_and_copy_safe(self):
        value = semantic_contract()
        self.assertEqual(semantic_contract_sha256(), digest(value))
        self.assertTrue(value["common_evidence_semantics"]["condition_inference_forbidden"])
        self.assertNotIn("roommind", json.dumps(value).lower())
        self.assertNotIn("baseline", json.dumps(value).lower())
        changed = copy.deepcopy(value)
        changed["dimension_scopes"]["procedural_fidelity"]["closure"] = "changed"
        with self.assertRaises(ValueError):
            validate_semantic_contract(changed)
        self.assertNotEqual(changed, semantic_contract())

    def test_prompts_enforce_dimension_isolation(self):
        for prompt in (CATALOG_PROMPT, EVALUATION_PROMPT):
            for phrase in ("only the supplied dimension_scope", "Do not transfer a defect",
                           "do not themselves require a violation", "Never infer the experimental condition"):
                self.assertIn(phrase, prompt)

    def test_each_dimension_receives_only_its_scope(self):
        scopes = {dimension: semantic_contract_for_dimension(dimension) for dimension in DIMENSIONS}
        self.assertEqual(len({digest(value) for value in scopes.values()}), len(DIMENSIONS))
        for dimension, value in scopes.items():
            self.assertEqual(value["dimension"], dimension)
            self.assertEqual(set(value), {"schema", "common_evidence_semantics", "dimension",
                                          "canonical_dimension", "dimension_scope"})
            self.assertNotIn("dimension_scopes", value)
        self.assertIn("unanswered question", scopes["role_strategic_fidelity"]["dimension_scope"]["exclude"])
        self.assertIn("transcript-wide", scopes["interaction_structure_fidelity"]["dimension_scope"]["evaluate"])

    def test_catalog_request_carries_exact_contract_and_spec_hash(self):
        task = {"case_id": "x", "dimension": "epistemic_fidelity", "rubric": "Assess evidence.",
                "context": {}, "messages": [{"message_id": "m", "speaker_id": "a", "turn_id": 1,
                "sequence_no": 1, "content": "I attached the file."}]}
        predictor = CatalogEvidencePredictor(ModelBinding("offline", "fixed", "mock", 0, 8192),
                                             None, predictor_id="fixture", kind="synthetic")
        spec = predictor.specification()
        data = json.loads(request_for(task, spec)["messages"][1]["content"])
        self.assertEqual(data["semantic_contract"], semantic_contract_for_dimension(task["dimension"]))
        self.assertEqual(spec["semantic_contract_sha256"], semantic_contract_sha256())

    def test_frozen_v1_catalog_request_remains_reconstructable(self):
        path = "research/experiments/2026-09-12-g5-semantic-scoring-calibration-inputs/inputs.json"
        with open(path) as stream:
            bundle = json.load(stream)
        case = bundle["cases"][0]
        self.assertEqual(request_for(case["task"], bundle["prediction_plan"]["model_spec"]), case["request"])


if __name__ == "__main__":
    unittest.main()
