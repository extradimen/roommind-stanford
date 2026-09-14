"""Condition-neutral semantic scoring contract tests; no model or network calls."""
import copy
import json
import unittest

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import (CatalogEvidencePredictor,
    PROMPT as CATALOG_PROMPT, PROMPT_V2 as CATALOG_PROMPT_V2,
    PROMPT_V3 as CATALOG_PROMPT_V3, repair_request_for, request_for)
from app.g5.evaluation import PROMPT as EVALUATION_PROMPT
from app.g5.evaluation_semantics import (DIMENSIONS, semantic_contract, semantic_contract_for_dimension,
    semantic_contract_sha256, semantic_contract_v2_for_dimension,
    semantic_contract_v2_sha256, semantic_contract_v3_for_dimension,
    semantic_contract_v3_sha256, validate_semantic_contract)
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

    def test_v4_clarifies_prospective_v14_failure_modes(self):
        common = semantic_contract()["common_evidence_semantics"]
        for key in ("state_update", "completion_flag_scope", "opaque_signal_scope",
                    "claims_do_not_extend_workflow"):
            self.assertIn(key, common)
        scopes = semantic_contract()["dimension_scopes"]
        self.assertIn("imperatives", scopes["interaction_structure_fidelity"]["request_rule"])
        self.assertIn("authoritative workflow",
                      scopes["procedural_fidelity"]["authoritative_workflow_rule"])
        self.assertIn("visible_to", common["visibility_boundary"])
        self.assertIn("affirmative goals", scopes["role_strategic_fidelity"]["goal_follow_through_rule"])
        self.assertIn("mere turn-taking", scopes["multi_party_dynamics_fidelity"]["substantive_participation_rule"])
        self.assertIn("correct operation order is necessary but not sufficient",
                      scopes["procedural_fidelity"]["completion_and_closure_rule"])

    def test_frozen_v3_v14_catalog_requests_remain_reconstructable(self):
        self.assertEqual(semantic_contract_v3_sha256(),
                         "490ff3f1a9cb6c167b3c01d44672a7817ef1da6f8df0dc71c181565c987f8f57")
        self.assertEqual(digest(CATALOG_PROMPT_V3),
                         "cb5056dc8951b1f0188e98ed735409d5b53cfa7e4f1d6fefd20f5aa4d40ce00e")
        path = "research/experiments/2026-09-14-g5-fresh-family-v14-scorer-preflight/inputs.json"
        with open(path) as stream:
            bundle = json.load(stream)
        case = bundle["cases"][0]
        self.assertEqual(request_for(case["task"], bundle["prediction_plan"]["model_spec"]),
                         case["request"])
        self.assertEqual(
            json.loads(case["request"]["messages"][1]["content"])["semantic_contract"],
            semantic_contract_v3_for_dimension(case["task"]["dimension"]))

    def test_frozen_v2_v11_catalog_request_remains_reconstructable(self):
        self.assertEqual(semantic_contract_v2_sha256(),
                         "86157439752f7dba607de9af1d74acfa3ece4f997ed89f775d358bc6646f684d")
        self.assertEqual(digest(CATALOG_PROMPT_V2),
                         "49da725eda25c86c7d9c826bf46fb040d27b481ee3be05e9a414df213d0ea930")
        task = {"case_id": "frozen-v2-reconstruction-fixture",
                "dimension": "epistemic_fidelity", "rubric": "Assess evidence.",
                "context": {"fixture": "v2"}, "messages": [{"message_id": "m-v2",
                "speaker_id": "role-a", "turn_id": 1, "sequence_no": 1,
                "content": "The registered review is complete."}]}
        spec = {"binding": {"provider": "offline", "model": "fixed",
                "endpoint_id": "mock", "temperature": 0, "max_tokens": 8192},
                "semantic_contract_sha256": semantic_contract_v2_sha256()}
        request = request_for(task, spec)
        self.assertEqual(json.loads(request["messages"][1]["content"])["semantic_contract"],
                         semantic_contract_v2_for_dimension(task["dimension"]))
        self.assertEqual(digest(request),
                         "13e7939f231cce41c4969818c17561999ce594b07a9aa48e46281bb2e2b3e660")

    def test_frozen_v1_catalog_request_remains_reconstructable(self):
        path = "research/experiments/2026-09-12-g5-semantic-scoring-calibration-inputs/inputs.json"
        with open(path) as stream:
            bundle = json.load(stream)
        case = bundle["cases"][0]
        self.assertEqual(request_for(case["task"], bundle["prediction_plan"]["model_spec"]), case["request"])

    def test_v4_repair_is_bounded_to_exact_catalog_ids(self):
        task = {"case_id": "repair", "dimension": "temporal_coherence", "rubric": "Assess time.",
                "context": {}, "messages": [{"message_id": "m", "speaker_id": "a", "turn_id": 1,
                "sequence_no": 1, "content": "The state remains open."}]}
        predictor = CatalogEvidencePredictor(ModelBinding("offline", "fixed", "mock", 0, 8192),
                                             None, predictor_id="fixture", kind="synthetic")
        spec = predictor.specification()
        repaired = repair_request_for(task, spec, '{"citations":[{"evidence_id":"E9999"}]}',
                                      "unknown_evidence_id")
        payload = json.loads(repaired["messages"][-1]["content"])
        self.assertEqual(payload["valid_evidence_ids"], ["E0001"])
        self.assertEqual(repaired["messages"][-2]["role"], "assistant")
        with self.assertRaises(ValueError):
            repair_request_for(task, spec, "{}", "unbounded_error")


if __name__ == "__main__":
    unittest.main()
