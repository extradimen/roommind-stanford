"""Audit frozen v3 program-localized evidence attempts; no model calls."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.factorial_study import digest
from app.g5.calibration_evidence_localized import localize_output
from g5_run_development_calibration import read, save

INPUT = Path("research/experiments/2026-09-12-g5-localized-evidence-calibration-inputs/inputs.json")
OUTPUT = Path("research/experiments/2026-09-12-g5-localized-evidence-calibration-predictions")


def diagnose(task, raw):
    if raw["transport_error"]:
        return raw["transport_error"]
    if raw["status"] != 200:
        return "http_status"
    try:
        envelope = json.loads(raw["body"])
    except ValueError:
        return "invalid_http_json"
    if envelope.get("model") != "gpt-oss:120b":
        return "model_mismatch"
    if envelope.get("done") is not True or envelope.get("done_reason") != "stop":
        return "incomplete_response"
    try:
        parsed = json.loads(envelope.get("message", {}).get("content", ""))
    except (ValueError, TypeError):
        return "invalid_content_json"
    if not isinstance(parsed, dict) or set(parsed) != {"prediction", "rationale", "citations"}:
        return "output_shape"
    if (parsed["prediction"] not in {"clear", "violation", "abstain"}
            or not isinstance(parsed["rationale"], str) or not parsed["rationale"].strip()):
        return "invalid_decision"
    citations = parsed["citations"]
    if (not isinstance(citations, list) or len(citations) > 5
            or (parsed["prediction"] != "abstain" and not citations)):
        return "evidence_count"
    messages = {message["message_id"]: message for message in task["messages"]}
    seen = set()
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"message_id", "quote", "relevance"}:
            return "citation_shape"
        message = messages.get(citation["message_id"])
        if message is None:
            return "unknown_message"
        if (not isinstance(citation["quote"], str) or not citation["quote"]
                or len(citation["quote"]) > 600 or not isinstance(citation["relevance"], str)
                or not citation["relevance"].strip()):
            return "citation_text"
        count = message["content"].count(citation["quote"])
        if count == 0:
            return "quote_missing"
        if count != 1:
            return "quote_nonunique"
        start = message["content"].find(citation["quote"])
        key = (citation["message_id"], start, start + len(citation["quote"]))
        if key in seen:
            return "duplicate_citation"
        seen.add(key)
    localize_output(task, parsed)
    return "valid"


def main():
    bundle = read(INPUT)
    assert bundle["sha256"] == digest({key: value for key, value in bundle.items() if key != "sha256"})
    attempts, final, files = [], [], {}
    reasons = Counter()
    for case in bundle["cases"]:
        latest = None
        for number in (1, 2):
            prefix = OUTPUT / (case["task"]["case_id"] + f".{number}")
            paths = [Path(str(prefix) + suffix) for suffix in (".started.json", ".http.json", ".result.json")]
            if not paths[0].exists():
                assert not paths[1].exists() and not paths[2].exists()
                continue
            assert all(path.exists() for path in paths)
            marker, raw, result = map(read, paths)
            assert marker["input_sha256"] == bundle["sha256"]
            assert marker["request_sha256"] == digest(case["request"])
            assert raw["request_sha256"] == digest(case["request"])
            if raw["body"] is not None:
                assert hashlib.sha256(raw["body"].encode()).hexdigest() == raw["body_sha256"]
            reason = diagnose(case["task"], raw)
            assert (reason == "valid") == (result["status"] == "completed")
            if reason == "valid":
                output = result["protocol"]["output"]
                assert output == localize_output(case["task"], {"prediction": output["prediction"],
                    "rationale": output["rationale"], "citations": output["model_citations"]})
            reasons[reason] += 1
            attempts.append({"case_id": case["task"]["case_id"], "attempt": number,
                "status": result["status"], "reason": reason})
            latest = result
            for path in paths:
                files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert latest is not None
        final.append({"case_id": case["task"]["case_id"], "status": latest["status"],
            "prediction": latest["protocol"]["output"]["prediction"] if latest["protocol"] else None})
    report = {"schema": "g5-localized-evidence-calibration-audit-v1",
        "input_sha256": bundle["sha256"], "attempts": attempts, "final_cases": final,
        "file_sha256": files, "attempt_count": len(attempts),
        "attempt_reason_counts": dict(sorted(reasons.items())),
        "final_status_counts": dict(Counter(item["status"] for item in final)),
        "final_prediction_counts": dict(Counter(item["prediction"] for item in final
            if item["status"] == "completed")), "human_reference_labels": 0,
        "accuracy_estimable": False, "g5_effect_estimable": False}
    report["sha256"] = digest(report)
    audit_path = OUTPUT / "audit.json"
    if audit_path.exists():
        assert read(audit_path) == report
    else:
        save(audit_path, report)
    print(json.dumps({key: report[key] for key in ("attempt_count", "attempt_reason_counts",
        "final_status_counts", "final_prediction_counts", "sha256")}))


if __name__ == "__main__":
    main()
