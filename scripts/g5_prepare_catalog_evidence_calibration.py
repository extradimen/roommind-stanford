"""Freeze v4 evidence-catalog requests from unchanged v3 case coverage."""
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import CatalogEvidencePredictor, request_for
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport

PRIOR = Path("research/experiments/2026-09-12-g5-localized-evidence-calibration-inputs/inputs.json")
TARGET = Path("research/experiments/2026-09-12-g5-catalog-evidence-calibration-inputs")
PRIOR_SHA = "e57b58d366cb4d89ae1afab2e87597c4d1679fe4f4ef7d94584c109fe4c16d71"


def main():
    prior = json.loads(PRIOR.read_text())
    if prior["sha256"] != PRIOR_SHA or digest({key: value for key, value in prior.items()
                                               if key != "sha256"}) != PRIOR_SHA:
        raise ValueError("V3 input changed")
    binding = ModelBinding("ollama", "gpt-oss:120b", "ollama-cloud-catalog-evidence-calibration", 0, 8192)
    predictor = CatalogEvidencePredictor(binding, OllamaTransport(binding, "https://ollama.com", timeout=240),
        predictor_id="g5-catalog-evidence-classifier-20260912", kind="ai")
    plan = predictor.plan()
    cases = []
    for case in prior["cases"]:
        item = {key: value for key, value in case.items() if key != "request"}
        item["request"] = request_for(item["task"], plan["model_spec"])
        cases.append(item)
    if len(cases) != 48 or [case["task"]["case_id"] for case in cases] != [
            case["task"]["case_id"] for case in prior["cases"]]:
        raise ValueError("Case coverage changed")
    bundle = {"schema": "g5-legacy-catalog-evidence-calibration-inputs-v4",
        "prior_input_sha256": PRIOR_SHA, "source_path": prior["source_path"],
        "source_file_sha256": prior["source_file_sha256"], "prediction_plan": plan, "cases": cases,
        "selection": "Exact v3 cases and source messages; only evidence selection protocol changed.",
        "change_rationale": "Trusted code presegments messages and assigns immutable IDs; the model selects IDs instead of copying quotes or computing source metadata.",
        "execution_policy": {"concurrency": 1, "maximum_attempts_per_case": 2,
            "retry": "technical failures only", "maximum_requests": 96,
            "completed_results": "immutable; resume missing only",
            "indeterminate_remote_call": "stop for quiescent review"},
        "external_execution_authorized": False, "reference_labels_available": False,
        "human_annotations": 0, "real_model_calls": 0, "accuracy_estimable": False,
        "g5_architecture_effect_estimable": False, "confirmation_eligible": False}
    bundle["sha256"] = digest(bundle)
    TARGET.mkdir(exist_ok=True, mode=0o700)
    if {path.name for path in TARGET.iterdir()} - {"README.md"}:
        raise ValueError("Target already contains generated material")
    fd = os.open(TARGET / "inputs.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(bundle, stream, ensure_ascii=False, sort_keys=True)
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"cases": 48, "sha256": bundle["sha256"],
        "largest_request_bytes": max(len(json.dumps(case["request"], ensure_ascii=False).encode())
                                     for case in cases),
        "external_execution_authorized": False}))


if __name__ == "__main__":
    main()
