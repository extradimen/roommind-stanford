#!/usr/bin/env python3
"""Live, non-evidentiary interface qualification for G5 v6."""
import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.factorial_study import digest
from app.g5.capacity import BudgetTransport, RequestBudget
from app.g5.fresh_execution_v2 import _components
from app.g5.model_policy import ModelBinding
from app.g5.ollama_transport import OllamaTransport
from app.g5.role_inputs import actor_view
from app.g5.world import Decision, World, canonical


SPEC = {"roles": ["security", "sre"], "facts": {
    "preserved": {"value": False, "visible_to": None, "disclosable": True},
    "contained": {"value": False, "visible_to": None, "disclosable": True},
    "staffing": {"value": "two missing shifts", "visible_to": ["sre"], "disclosable": True},
    "secret": {"value": "protected-source", "visible_to": ["security"], "disclosable": False},
}, "actions": {
    "preserve": {"actors": ["security"], "requires": {}, "effects": {"preserved": True},
                 "outcome": "success", "visible_to": None},
    "contain": {"actors": ["sre"], "requires": {"preserved": True},
                "effects": {"contained": True}, "outcome": "success", "visible_to": None},
}}
CARDS = {role: {"public": {"name": role, "job_title": role, "side": "internal", "kind": "npc"},
                "private": {"persona": "careful", "goals": [role + "-only-goal"],
                            "instructions": "Use only observed simulation evidence."}}
         for role in SPEC["roles"]}


def write_new(path, value):
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


async def qualify(args, api_key):
    binding = ModelBinding("ollama", args.model, args.endpoint_id, 0.2, 2048)
    route = OllamaTransport(binding, args.base_url, api_key=api_key, timeout=240,
                            reasoning_effort="low")
    transport = BudgetTransport(route, RequestBudget(524288, 262144),
                                delegate_id=args.endpoint_id)
    parts = _components(binding, transport,
                        max_structured_revisions=args.max_structured_revisions)
    world = World(":memory:")
    try:
        world.create("g5-v6-interface-qualification", SPEC,
                     {"classification": "synthetic-engineering-only"})
        _, observed = world.observe("g5-v6-interface-qualification", "security")
        view = actor_view(observed, CARDS)
        view["memory_scope"] = digest([args.source_revision, "g5-v6-interface-qualification"])

        policy = await parts["policy"](view, ())
        cognition = await parts["cognition"](view)
        governance = await parts["governance"](
            view, Decision("speak", "The containment status remains uncertain."))
        question_context = {"actor": "security", "participants": list(SPEC["roles"]),
                            "observations": [], "questions": {"questions": []}}
        questions = await parts["question_annotator"](
            question_context, Decision("speak", "SRE, can you confirm the containment timeline?"))
        session_context = {"actor": "security", "participants": list(SPEC["roles"]),
                           "observations": [], "session": {"status": "open"}}
        session = await parts["session_annotator"](
            session_context, Decision("speak", "I intend to continue this discussion."))

        raw = {"schema": "g5-v6-live-interface-qualification-v1",
               "classification": "synthetic-engineering-only",
               "qualification": "interface-transport-and-validation-only",
               "source_revision": args.source_revision,
               "provider": "ollama", "model": args.model,
               "endpoint_id": args.endpoint_id, "reasoning_effort": "low",
               "max_structured_revisions": args.max_structured_revisions,
               "credential_serialized": False,
               "interfaces": {
                   "policy": {"decision": asdict(policy)},
                   "cognition": cognition,
                   "governance": asdict(governance),
                   "question_annotation": {"annotations": list(questions),
                       "model_evidence": questions.model_evidence},
                   "session_annotation": asdict(session),
               },
               "request_budget": transport.runtime_specification()["budget"],
               "research_use": "must_not_enter_development_or_confirmatory_evidence"}
        return {**raw, "sha256": digest(raw)}
    finally:
        world.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--credential-source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="gpt-oss:120b")
    parser.add_argument("--endpoint-id", default="ollama-cloud-g5-fresh-v2")
    parser.add_argument("--base-url", default="https://ollama.com")
    parser.add_argument("--max-structured-revisions", type=int, default=2)
    args = parser.parse_args()
    if len(args.source_revision) != 40 or any(c not in "0123456789abcdef" for c in args.source_revision):
        raise SystemExit("Exact source revision required")
    if not 0 <= args.max_structured_revisions <= 4:
        raise SystemExit("Bounded structured revision limit required")
    key = (dotenv_values(args.credential_source).get("OLLAMA_API_KEY")
           or dotenv_values(args.credential_source).get("OLLAMA_CLOUD_API_KEY"))
    if not key:
        raise SystemExit("Explicit credential source has no Ollama key")
    result = asyncio.run(qualify(args, key))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_new(output, result)
    print(canonical({"status": "passed", "sha256": result["sha256"],
                     "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
