#!/usr/bin/env python3
"""Run four synthetic 16-event A-D worlds for G5 v6 engineering qualification."""
import argparse
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.factorial_study import ARMS, PROTOCOL, SHARED_FIELDS, digest, freeze_design
from app.g5.artifacts import verify_source
from app.g5.capacity import BudgetTransport, RequestBudget
from app.g5.components import specification
from app.g5.fresh_execution_v2 import _components
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport
from app.g5.world import WORLD_CONTRACT_SHA256, World
from app.g5.runtime import Runtime
from g5_qualify_structured_v6 import SPEC, CARDS, write_new


SCENARIO = "g5-v6-synthetic-qualification"


def manifest(source_revision, parts):
    components = {name: specification(parts[name])
                  for name in ("policy", "cognition", "governance")}
    stop = {"max_steps": 16, "max_revisions": 1}
    shared = {key: digest({"synthetic_qualification": key}) for key in SHARED_FIELDS}
    shared.update(world_sha256=WORLD_CONTRACT_SHA256,
                  role_inputs_sha256=digest(CARDS),
                  stopping_policy_sha256=digest(stop),
                  model_bindings_sha256=digest(components))
    return freeze_design({"protocol": PROTOCOL, "source_revision": source_revision,
        "stage": "exploration", "scenarios": [{"id": SCENARIO,
        "family": "synthetic-engineering", "snapshot_sha256": digest(SPEC)}],
        "used_families": [], "repetitions": 1, "order_seed": 20260912,
        "sampling_seed_policy": "unsupported_recorded",
        "analysis_plan_sha256": digest("no-analysis-synthetic-qualification"),
        "sample_size_plan_sha256": digest("four-arms-one-world-each"),
        "arms": {arm: {**flags, "shared": deepcopy(shared)} for arm, flags in ARMS.items()},
        "components": components})


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def run(args, api_key):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    binding = ModelBinding("ollama", args.model, args.endpoint_id, 0.2, 2048)
    route = OllamaTransport(binding, args.base_url, api_key=api_key, timeout=240,
                            reasoning_effort="low")
    transport = BudgetTransport(route, RequestBudget(2097152, 1048576),
                                delegate_id=args.endpoint_id)
    parts = _components(binding, transport, max_structured_revisions=2)
    frozen = manifest(args.source_revision, parts)
    header_raw = {"schema": "g5-v6-live-world-qualification-v1",
                  "classification": "synthetic-engineering-only",
                  "source_revision": args.source_revision,
                  "manifest": frozen, "max_steps": 16, "max_revisions": 1,
                  "credential_serialized": False,
                  "research_use": "must_not_enter_development_or_confirmatory_evidence"}
    header = {**header_raw, "sha256": digest(header_raw)}
    header_path = output / "binding.json"
    if header_path.exists():
        if load(header_path) != header:
            raise ValueError("Qualification binding changed")
    else:
        write_new(header_path, header)

    store = World(output / "world.sqlite")
    committed = sum(len(store.events("qual-" + arm))
                    for arm in ARMS if store.db.execute(
                        "SELECT 1 FROM g5_worlds WHERE id=?", ("qual-" + arm,)).fetchone())
    try:
        for assignment in frozen["assignments"]:
            arm = assignment["arm"]
            world_id = "qual-" + arm
            ordinal = assignment["ordinal"]
            runtime = Runtime(world=store, world_id=world_id, spec=SPEC,
                manifest=frozen, ordinal=ordinal, policy=parts["policy"],
                cognition=parts["cognition"] if ARMS[arm]["cognition"] else None,
                governance=parts["governance"] if ARMS[arm]["governance"] else None,
                role_inputs=CARDS, max_steps=16, max_revisions=1)
            while store.frozen(world_id) is None:
                result = await runtime.step()
                if result["status"] == "committed":
                    committed += 1
                    if (args.interrupt_after and committed >= args.interrupt_after
                            and not (output / "interruption.marker").exists()):
                        write_new(output / "interruption.marker", {
                            "schema": "g5-v6-deliberate-process-interruption-v1",
                            "after_committed_events": committed,
                            "binding_sha256": header["sha256"]})
                        os._exit(75)
                elif result["status"] == "cutoff":
                    store.freeze(world_id)
                elif result["status"] != "dialogue_frozen":
                    raise ValueError("Unexpected qualification status")
            source_path = output / "sources" / (arm + ".json")
            source = store.export_source(world_id)
            verify_source(source, frozen)
            if source_path.exists():
                if load(source_path) != source:
                    raise ValueError("Qualification source changed")
            else:
                source_path.parent.mkdir(parents=True, exist_ok=True)
                write_new(source_path, source)
            print(json.dumps({"milestone": "sealed", "arm": arm,
                              "events": len(source["events"]),
                              "sha256": source["sha256"]}), flush=True)
        summary_raw = {"schema": "g5-v6-live-world-qualification-summary-v1",
            "binding_sha256": header["sha256"], "source_revision": args.source_revision,
            "arms": {arm: load(output / "sources" / (arm + ".json"))["sha256"]
                     for arm in ARMS}, "events_per_arm": 16,
            "interruption_recovery_exercised": (output / "interruption.marker").exists(),
            "qualification": "engineering-pass",
            "research_use": "must_not_enter_development_or_confirmatory_evidence"}
        summary = {**summary_raw, "sha256": digest(summary_raw)}
        summary_path = output / "summary.json"
        if summary_path.exists():
            if load(summary_path) != summary:
                raise ValueError("Qualification summary changed")
        else:
            write_new(summary_path, summary)
        print(json.dumps({"status": "passed", "sha256": summary["sha256"]}), flush=True)
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--credential-source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--interrupt-after", type=int, default=0)
    parser.add_argument("--model", default="gpt-oss:120b")
    parser.add_argument("--endpoint-id", default="ollama-cloud-g5-fresh-v2")
    parser.add_argument("--base-url", default="https://ollama.com")
    args = parser.parse_args()
    if len(args.source_revision) != 40 or any(c not in "0123456789abcdef" for c in args.source_revision):
        raise SystemExit("Exact source revision required")
    values = dotenv_values(args.credential_source)
    key = values.get("OLLAMA_API_KEY") or values.get("OLLAMA_CLOUD_API_KEY")
    if not key:
        raise SystemExit("Explicit credential source has no Ollama key")
    asyncio.run(run(args, key))


if __name__ == "__main__":
    main()
