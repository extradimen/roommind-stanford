#!/usr/bin/env python3
"""Compare semantic-contract predictions with the frozen Codex expert diagnosis."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.factorial_study import digest


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", required=True)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--prior-audit", required=True)
    parser.add_argument("--semantic-audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    panel, packet, review, prior, current = map(read, (args.panel, args.packet, args.review,
        args.prior_audit, args.semantic_audit))
    slot = next(item for item in panel["slots"] if item["slot_id"] == packet["slot_id"])
    alias_to_blind = {item["task_id"]: item["blind_id"] for item in slot["assignments"]}
    master = {item["blind_id"]: item for item in panel["master"]}
    expert = {}
    metadata = {}
    for row in review["rows"]:
        source = master[alias_to_blind[row["task_id"]]]
        case_id = source["source_case_id"]
        expert[case_id] = row["label"]
        metadata[case_id] = {**source, "dimension": row["dimension"]}
    old = {item["case_id"]: item for item in prior["final_cases"]}
    new = {item["case_id"]: item for item in current["final_cases"]}
    rows = []
    for case_id in sorted(expert):
        old_label = "uncertain" if old[case_id].get("prediction") == "abstain" else old[case_id].get("prediction")
        new_label = "uncertain" if new[case_id].get("prediction") == "abstain" else new[case_id].get("prediction")
        rows.append({"case_id": case_id, "source_family": metadata[case_id]["source_family"],
            "source_condition": metadata[case_id]["source_condition"],
            "dimension": metadata[case_id]["dimension"], "expert_label": expert[case_id],
            "prior_status": old[case_id]["status"], "prior_label": old_label,
            "semantic_status": new[case_id]["status"], "semantic_label": new_label,
            "prior_agreement": old[case_id]["status"] == "completed" and old_label == expert[case_id],
            "semantic_agreement": new[case_id]["status"] == "completed" and new_label == expert[case_id]})
    comparable = [row for row in rows if row["semantic_status"] == "completed"]
    shared = [row for row in rows if row["semantic_status"] == row["prior_status"] == "completed"]
    per_dimension = {}
    for dimension in sorted({row["dimension"] for row in rows}):
        group = [row for row in comparable if row["dimension"] == dimension]
        per_dimension[dimension] = {"comparable": len(group),
            "agreements": sum(row["semantic_agreement"] for row in group),
            "agreement_rate": sum(row["semantic_agreement"] for row in group) / len(group) if group else None}
    by_condition = defaultdict(Counter)
    for row in comparable:
        by_condition[row["source_condition"]][row["semantic_label"]] += 1
    summary = {"cases": len(rows), "semantic_completed": len(comparable),
        "semantic_technical_failures": len(rows) - len(comparable),
        "semantic_agreements": sum(row["semantic_agreement"] for row in comparable),
        "semantic_agreement_rate": sum(row["semantic_agreement"] for row in comparable) / len(comparable),
        "shared_completed": len(shared),
        "prior_agreements_on_shared": sum(row["prior_agreement"] for row in shared),
        "semantic_agreements_on_shared": sum(row["semantic_agreement"] for row in shared),
        "agreement_delta_on_shared": (sum(row["semantic_agreement"] for row in shared)
            - sum(row["prior_agreement"] for row in shared)) / len(shared),
        "semantic_labels": dict(sorted(Counter(row["semantic_label"] for row in comparable).items())),
        "semantic_labels_by_condition": {key: dict(sorted(value.items()))
            for key, value in sorted(by_condition.items())}, "per_dimension": per_dimension}
    raw = {"schema": "g5-semantic-scoring-codex-expert-comparison-v1",
        "classification": "internal-development-evidence", "human_reference": False,
        "accuracy_estimable": False, "g5_effect_estimable": False,
        "limitations": ["Agreement with one Codex pass is not human-grounded accuracy.",
            "The semantic contract was designed after inspecting aggregate disagreements, so this is development-set reuse.",
            "These eight legacy dialogues cannot confirm G5 effects."],
        "based_on": {"panel_sha256": panel["sha256"], "packet_sha256": packet["sha256"],
            "expert_review_sha256": review["sha256"], "prior_audit_sha256": prior["sha256"],
            "semantic_audit_sha256": current["sha256"]}, "summary": summary, "rows": rows}
    result = {**raw, "sha256": digest(raw)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"output": str(output), "sha256": result["sha256"], **summary}, sort_keys=True))


if __name__ == "__main__":
    main()
