#!/usr/bin/env python3
"""Freeze the same 48 v4 cases under the condition-neutral scoring contract."""
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import CatalogEvidencePredictor, request_for
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport


PRIOR = Path("research/experiments/2026-09-12-g5-catalog-evidence-calibration-inputs/inputs.json")
TARGET = Path("research/experiments/2026-09-12-g5-semantic-scoring-calibration-inputs")
PRIOR_SHA = "55f0de1fb8f61691030b7055fd21b6dfe92267c6bba877279fe1a6f82f7edc9b"


def main():
    prior = json.loads(PRIOR.read_text())
    if (prior["sha256"] != PRIOR_SHA
            or digest({key: value for key, value in prior.items() if key != "sha256"}) != PRIOR_SHA):
        raise ValueError("V4 input changed")
    binding = ModelBinding("ollama", "gpt-oss:120b",
        "ollama-cloud-semantic-scoring-calibration", 0, 8192)
    predictor = CatalogEvidencePredictor(binding,
        OllamaTransport(binding, "https://ollama.com", timeout=240),
        predictor_id="g5-semantic-scoring-classifier-20260912", kind="ai")
    plan = predictor.plan()
    cases = []
    for case in prior["cases"]:
        item = {key: value for key, value in case.items() if key != "request"}
        item["request"] = request_for(item["task"], plan["model_spec"])
        cases.append(item)
    if len(cases) != 48 or [case["task"]["case_id"] for case in cases] != [
            case["task"]["case_id"] for case in prior["cases"]]:
        raise ValueError("Case coverage changed")
    bundle = {
        "schema": "g5-semantic-scoring-calibration-inputs-v1",
        "prior_input_sha256": PRIOR_SHA,
        "source_path": prior["source_path"],
        "source_file_sha256": prior["source_file_sha256"],
        "prediction_plan": plan,
        "cases": cases,
        "selection": "Exact v4 cases, evidence catalogs, dimensions, rubrics, and source messages.",
        "change_rationale": "Add the frozen condition-neutral semantic scoring contract identified by its model-specification digest.",
        "execution_policy": {"concurrency": 1, "maximum_attempts_per_case": 2,
            "retry": "technical failures only", "maximum_requests": 96,
            "completed_results": "immutable; resume missing only",
            "indeterminate_remote_call": "stop for quiescent review"},
        "external_execution_authorized": False,
        "authorization_record": "User message '开始' after the assistant stated the exact external re-evaluation scope.",
        "reference_labels_available": True,
        "reference_kind": "single_ai_expert_development_diagnosis",
        "human_annotations": 0,
        "real_model_calls": 0,
        "accuracy_estimable": False,
        "g5_architecture_effect_estimable": False,
        "confirmation_eligible": False,
    }
    bundle["sha256"] = digest(bundle)
    TARGET.mkdir(exist_ok=True, mode=0o700)
    if list(TARGET.iterdir()):
        raise ValueError("Target already contains material")
    fd = os.open(TARGET / "inputs.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(bundle, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"cases": len(cases), "sha256": bundle["sha256"],
        "semantic_contract_sha256": plan["model_spec"]["semantic_contract_sha256"],
        "largest_request_bytes": max(len(json.dumps(case["request"], ensure_ascii=False).encode())
                                     for case in cases)}))


if __name__ == "__main__":
    main()
