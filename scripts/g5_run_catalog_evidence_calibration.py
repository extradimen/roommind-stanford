"""Run frozen v4 evidence-catalog calibration; credential stays in memory."""
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path

import httpx
from app.factorial_study import digest
from app.g5.calibration_evidence_catalog import CatalogEvidencePredictor, request_for
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport
from g5_run_development_calibration import credential, read, save

INPUT = Path("research/experiments/2026-09-12-g5-catalog-evidence-calibration-inputs/inputs.json")
OUTPUT = Path("research/experiments/2026-09-12-g5-catalog-evidence-calibration-predictions")


async def attempt(case, plan, number, key, http_transport=None):
    prefix = OUTPUT / (case["task"]["case_id"] + f".{number}")
    paths = [Path(str(prefix) + suffix) for suffix in (".started.json", ".http.json", ".result.json")]
    marker = {"input_sha256": read(INPUT)["sha256"], "case_id": case["task"]["case_id"],
        "attempt": number, "request_sha256": digest(case["request"])}
    if paths[0].exists():
        if read(paths[0]) != marker:
            raise ValueError("Attempt drift")
    else:
        save(paths[0], marker)
    if paths[2].exists():
        return read(paths[2])
    if not paths[1].exists():
        binding = plan["model_spec"]["binding"]
        payload = {"model": binding["model"], "messages": case["request"]["messages"], "stream": False,
            "format": "json", "options": {"temperature": binding["temperature"],
                "num_predict": binding["max_tokens"]}}
        try:
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=240,
                                         transport=http_transport) as client:
                response = await client.post("https://ollama.com/api/chat", json=payload,
                    headers={"Authorization": "Bearer " + key})
            body = response.content.decode("utf-8")
            if key in body:
                raise RuntimeError("Secret echo detected")
            raw = {"status": response.status_code, "body": body,
                "body_sha256": hashlib.sha256(response.content).hexdigest(),
                "request_sha256": digest(case["request"]), "transport_error": None}
        except (httpx.TimeoutException, httpx.HTTPError) as error:
            raw = {"status": None, "body": None, "body_sha256": None,
                "request_sha256": digest(case["request"]),
                "transport_error": "timeout" if isinstance(error, httpx.TimeoutException) else "connection"}
        save(paths[1], raw)
    raw = read(paths[1])
    if raw["status"] in (401, 403):
        raise RuntimeError("Authentication rejected")
    if raw["status"] == 200:
        try:
            envelope = json.loads(raw["body"])
        except ValueError:
            envelope = {}
        if envelope.get("model") not in (None, plan["model_spec"]["binding"]["model"]):
            raise RuntimeError("Model identity mismatch")
    async def replay(request):
        if raw["transport_error"] == "timeout":
            raise httpx.ReadTimeout("recorded")
        if raw["transport_error"]:
            raise httpx.ConnectError("recorded")
        return httpx.Response(raw["status"], content=raw["body"].encode(), request=request)
    binding = ModelBinding(**plan["model_spec"]["binding"])
    predictor = CatalogEvidencePredictor(binding,
        OllamaTransport(binding, "https://ollama.com", timeout=240, http_transport=httpx.MockTransport(replay)),
        predictor_id=plan["predictor"]["id"], kind="ai")
    try:
        protocol = await predictor.predict(case["task"], plan)
        result = {"case_id": case["task"]["case_id"], "attempt": number,
            "status": "completed", "error_code": None, "protocol": protocol}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        result = {"case_id": case["task"]["case_id"], "attempt": number,
            "status": "technical_failure", "error_code": "invalid_response", "protocol": None}
    except (TimeoutError, ConnectionError, httpx.HTTPError):
        result = {"case_id": case["task"]["case_id"], "attempt": number,
            "status": "technical_failure", "error_code": "transport_failure", "protocol": None}
    save(paths[2], result)
    return result


async def run():
    bundle = read(INPUT)
    if (bundle["sha256"] != digest({key: value for key, value in bundle.items() if key != "sha256"})
            or bundle["external_execution_authorized"] is not False):
        raise ValueError("Frozen v4 input or authorization marker changed")
    if hashlib.sha256(Path(bundle["source_path"]).read_bytes()).hexdigest() != bundle["source_file_sha256"]:
        raise ValueError("Source changed")
    for case in bundle["cases"]:
        if request_for(case["task"], bundle["prediction_plan"]["model_spec"]) != case["request"]:
            raise ValueError("Request changed")
    OUTPUT.mkdir(exist_ok=True, mode=0o700)
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
                        key = credential()
                    result = await attempt(case, bundle["prediction_plan"], number, key)
                print(json.dumps({"case": result["case_id"], "attempt": number,
                    "status": result["status"],
                    "prediction": result["protocol"]["output"]["prediction"] if result["protocol"] else None,
                    "citations": len(result["protocol"]["output"]["evidence"])
                    if result["protocol"] else 0, "error_code": result["error_code"]}), flush=True)
                if result["status"] == "completed":
                    break
        print("FROZEN_CATALOG_EVIDENCE_PREDICTIONS_FINISHED", flush=True)
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as error:
        print("Stopped safely: " + type(error).__name__, flush=True)
        raise SystemExit(1)
