#!/usr/bin/env python3
"""Run the frozen v11 48-cell scorer batch after exact external authorization."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import request_for
import g5_run_catalog_evidence_calibration as runner


INPUT = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-preflight/inputs.json")
OUTPUT = Path("research/experiments/2026-09-13-g5-fresh-family-v11-scorer-predictions")
EXPECTED_INPUT_SHA = "ac09d92494c00ad9994b547017b113b344eafbed7a645e331d756db8b7f89ae0"
AUTHORIZATION_SCHEMA = "g5-fresh-v11-scorer-external-authorization-v1"
AUTHORIZATION_SCOPE = (
    "Send the 48 frozen dimension-scoped development-scoring requests derived from the eight "
    "sealed v11 dialogues to https://ollama.com/api/chat using gpt-oss:120b; preserve every raw "
    "response and technical failure; do not start the 32-dialogue screening batch."
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_authorization(path):
    value = read(path)
    unsigned = {key: item for key, item in value.items() if key != "sha256"}
    if value.get("sha256") != digest(unsigned):
        raise ValueError("Authorization record checksum mismatch")
    expected = {"schema", "input_sha256", "scope", "provider", "model", "endpoint",
        "maximum_requests", "preserve_raw_responses", "authorized", "user_authorization_record",
        "sha256"}
    if (set(value) != expected or value["schema"] != AUTHORIZATION_SCHEMA
            or value["input_sha256"] != EXPECTED_INPUT_SHA
            or value["scope"] != AUTHORIZATION_SCOPE or value["provider"] != "ollama"
            or value["model"] != "gpt-oss:120b"
            or value["endpoint"] != "https://ollama.com/api/chat"
            or value["maximum_requests"] != 96
            or value["preserve_raw_responses"] is not True
            or value["authorized"] is not True
            or not isinstance(value["user_authorization_record"], str)
            or not value["user_authorization_record"].strip()):
        raise ValueError("Authorization does not cover the frozen scorer batch")
    return value


def validate_inputs():
    bundle = read(INPUT)
    if (bundle.get("sha256") != EXPECTED_INPUT_SHA
            or digest({key: value for key, value in bundle.items() if key != "sha256"})
            != EXPECTED_INPUT_SHA):
        raise ValueError("Frozen v11 scorer inputs changed")
    if bundle.get("real_model_calls") != 0 or bundle.get("external_execution_authorized") is not False:
        raise ValueError("Preparation record no longer represents the untouched local preflight")
    for path_text, checksum in bundle["source_file_sha256"].items():
        if hashlib.sha256(Path(path_text).read_bytes()).hexdigest() != checksum:
            raise ValueError("Sealed source file changed")
    for case in bundle["cases"]:
        if request_for(case["task"], bundle["prediction_plan"]["model_spec"]) != case["request"]:
            raise ValueError("Frozen scoring request changed")
    if len(bundle["cases"]) != 48:
        raise ValueError("Scorer coverage changed")
    return bundle


async def run(authorization_path):
    bundle = validate_inputs()
    authorization = validate_authorization(authorization_path)
    runner.INPUT, runner.OUTPUT = INPUT, OUTPUT
    OUTPUT.mkdir(exist_ok=True, mode=0o700)
    auth_copy = OUTPUT / "authorization.json"
    if auth_copy.exists():
        if read(auth_copy) != authorization:
            raise ValueError("Output belongs to another authorization")
    else:
        runner.save(auth_copy, authorization)
    lock = os.open(OUTPUT / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        for path in OUTPUT.glob("*.started.json"):
            if not Path(str(path).replace(".started.json", ".http.json")).exists():
                raise RuntimeError("Indeterminate attempt requires quiescent review")
        key = None
        for case in bundle["cases"]:
            for number in (1, 2):
                path = OUTPUT / (case["task"]["case_id"] + f".{number}.result.json")
                result = read(path) if path.exists() else None
                if result is None:
                    if key is None:
                        key = runner.credential()
                    result = await runner.attempt(case, bundle["prediction_plan"], number, key)
                print(json.dumps({"case": result["case_id"], "attempt": number,
                    "status": result["status"],
                    "prediction": result["protocol"]["output"]["prediction"]
                    if result["protocol"] else None,
                    "citations": len(result["protocol"]["output"]["evidence"])
                    if result["protocol"] else 0,
                    "error_code": result["error_code"]}), flush=True)
                if result["status"] == "completed":
                    break
        print("FROZEN_FRESH_V11_SCORER_PREDICTIONS_FINISHED", flush=True)
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-file", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.authorization_file))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Stopped safely: " + type(error).__name__, flush=True)
        raise SystemExit(1)
