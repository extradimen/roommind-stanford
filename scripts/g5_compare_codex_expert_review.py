#!/usr/bin/env python3
"""Compare the single Codex expert pass with v4 outputs; never call it human accuracy."""
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
    parser.add_argument("--v4-audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    panel, packet, review, audit = map(read, (args.panel, args.packet, args.review, args.v4_audit))
    slot = next(slot for slot in panel["slots"] if slot["slot_id"] == packet["slot_id"])
    alias_to_blind = {a["task_id"]: a["blind_id"] for a in slot["assignments"]}
    master = {m["blind_id"]: m for m in panel["master"]}
    finals = {f["case_id"]: f for f in audit["final_cases"]}
    rows = []
    for row in review["rows"]:
        source = master[alias_to_blind[row["task_id"]]]
        final = finals[source["source_case_id"]]
        model_label = "uncertain" if final.get("prediction") == "abstain" else final.get("prediction")
        comparable = final["status"] == "completed"
        rows.append({"source_case_id": source["source_case_id"], "source_family": source["source_family"],
                     "source_condition": source["source_condition"], "dimension": row["dimension"],
                     "expert_label": row["label"], "v4_status": final["status"],
                     "v4_label": model_label, "agreement": comparable and row["label"] == model_label})
    comparable = [r for r in rows if r["v4_status"] == "completed"]
    per_dimension = {}
    for dimension in sorted({r["dimension"] for r in rows}):
        group = [r for r in comparable if r["dimension"] == dimension]
        per_dimension[dimension] = {"comparable": len(group), "agreements": sum(r["agreement"] for r in group),
                                    "agreement_rate": (sum(r["agreement"] for r in group) / len(group)) if group else None}
    condition_counts = defaultdict(Counter)
    for row in rows:
        condition_counts[row["source_condition"]][row["expert_label"]] += 1
    raw = {"schema": "g5-codex-expert-v4-comparison-v1",
           "classification": "internal-development-evidence",
           "human_reference": False, "accuracy_estimable": False, "g5_effect_estimable": False,
           "limitations": ["Agreement with one Codex pass is not human-grounded accuracy.",
                           "Source conditions were joined only after the blinded expert labels were frozen.",
                           "These eight legacy dialogues are development material and cannot confirm G5 effects."],
           "based_on": {"panel_sha256": panel["sha256"], "packet_sha256": packet["sha256"],
                        "expert_review_sha256": review["sha256"], "v4_audit_sha256": audit["sha256"]},
           "summary": {"cases": len(rows), "v4_completed": len(comparable),
                       "v4_technical_failures": len(rows) - len(comparable),
                       "agreements": sum(r["agreement"] for r in comparable),
                       "agreement_rate": sum(r["agreement"] for r in comparable) / len(comparable),
                       "expert_labels": dict(sorted(Counter(r["expert_label"] for r in rows).items())),
                       "v4_labels_completed": dict(sorted(Counter(r["v4_label"] for r in comparable).items())),
                       "expert_labels_by_source_condition": {k: dict(sorted(v.items())) for k, v in sorted(condition_counts.items())},
                       "per_dimension": per_dimension},
           "rows": sorted(rows, key=lambda r: r["source_case_id"])}
    result = {**raw, "sha256": digest(raw)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"output": str(output), "sha256": result["sha256"], **result["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
