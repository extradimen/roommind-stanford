"""Read preserved synthetic inputs and measure local ledger validation, without inference."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import time
from unittest.mock import patch

from app.factorial_study import digest
from app.g5 import prediction_archive as ledger_module
from app.g5.calibration_predictor import request_for
from app.g5.world import canonical


def audit(root):
    paths = [root / "research/experiments/2026-09-12-g5-local-prediction-ledger/panel.json",
             root / "research/experiments/2026-09-12-g5-local-calibration-bridge/panel.json"]
    inputs = [json.loads(p.read_text()) for p in paths]
    saved = inputs[0]["ledger"]
    rows = []
    for name, annotation, events in (
        ("four_cases_empty", saved["annotation"], []),
        ("four_cases_completed", saved["annotation"], saved["events"]),
        ("twenty_four_cases_empty", inputs[1]["annotation"], []),
    ):
        archive = ledger_module.PredictionArchive(":memory:", annotation, saved["plan"])
        try:
            for event in events:
                archive.append(event)
            original = archive.export()
            task = archive.tasks.task(annotation["plan"]["plan"]["cases"][0]["id"])
            candidate = deepcopy(events[0]) if events else {"phase": "started", "value": {
                "id": "scale-audit-pending", "case_id": task["case_id"],
                "previous_attempt_sha256": None,
                "request_sha256": digest(request_for(task, saved["plan"]["model_spec"]))}}
            measurements = []
            for operation, call in (("export", archive.export), ("append", lambda: archive.append(candidate)),
                                    ("export_after", archive.export), ("idempotent_append", lambda: archive.append(candidate))):
                with patch.object(ledger_module, "freeze_results", wraps=ledger_module.freeze_results) as verify:
                    started = time.perf_counter()
                    result = call()
                    elapsed = time.perf_counter() - started
                measurements.append({"operation": operation, "seconds": elapsed,
                                     "full_result_validations": verify.call_count, "result_sha256": digest(result)})
            final = archive.export()
            rows.append({"workload": name, "cases": len(annotation["plan"]["plan"]["cases"]),
                         "sources": len(annotation["sources"]), "label_records": len(annotation["rows"]),
                         "initial_events": len(events), "final_events": len(final["events"]),
                         "initial_export_sha256": original["sha256"], "final_export_sha256": final["sha256"],
                         "export_bytes": len(canonical(final).encode()), "measurements": measurements})
        finally:
            archive.close()
    raw = {"schema": "g5-local-ledger-scale-audit-v1", "python": platform.python_version(),
           "machine": platform.machine(), "real_model_calls": 0,
           "limitations": "Single process, one timing per operation, existing 4 synthetic sources; not throughput, long-dialogue or multiworker qualification.",
           "inputs": [{"path": str(p.relative_to(root)), "file_sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
           "prediction_source_sha256": hashlib.sha256(Path(ledger_module.__file__).read_bytes()).hexdigest(), "workloads": rows}
    return {**raw, "sha256": digest(raw)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"output": str(args.output), "sha256": result["sha256"]}))
