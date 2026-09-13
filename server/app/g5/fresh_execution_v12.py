"""Bound, resumable execution for the eight-dialogue fresh-family v12 scorer-validation pilot.

The pre-generation frame, role pack, and scorer-validation plan remain immutable
and un-authorized.  This module creates a separate execution binding only after
an operator supplies an exact source revision, model route, and authorization
record.  It runs the selected one-arm-per-world pilot; it does not run the later
32-dialogue complete-block architecture screen or any evaluator.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import re

from app.factorial_study import ARMS, PROTOCOL, SHARED_FIELDS, digest, freeze_design, verify_manifest
from app.g5.artifacts import verify_source
from app.g5.assembly import ExplicitRouteAssembler
from app.g5.capacity import BudgetTransport, RequestBudget
from app.g5.cognition_storage import PROTOCOL as COGNITION_STORAGE
from app.g5.components import specification
from app.g5.evaluation import PROMPT as EVALUATION_PROMPT
from app.g5.evaluation_semantics import semantic_contract_sha256
from app.g5.fresh_family_frame_v3 import fresh_family_frame_v3
from app.g5.fresh_family_roles_v3 import fresh_family_role_pack_v3
from app.g5.fresh_validation_plan_v3 import fresh_validation_plan_v3
from app.g5.governance import CandidateGovernance
from app.g5.memory import MemoryCognition
from app.g5.model_auditor import ModelAuditor
from app.g5.model_cognition import ModelCognitionGenerator
from app.g5.model_policy import ModelBinding, ModelPolicy
from app.g5.model_questions import ModelQuestionAnnotator
from app.g5.model_session import ModelSessionAnnotator
from app.g5.observation import ObservationWindow
from app.g5.ollama_transport import OllamaTransport
from app.g5.reflection import ReflectiveCognition
from app.g5.scheduling import QuestionScheduler
from app.g5.session_journal import SESSION_PROTOCOL
from app.g5.structured_output import StructuredOutputError
from app.g5.world import WORLD_CONTRACT_SHA256, World


REVISION = re.compile(r"[0-9a-f]{40}\Z")
DEFAULT_MODEL = "gpt-oss:120b"
DEFAULT_ENDPOINT = "ollama-cloud-g5-fresh-v12"
DEFAULT_MAX_STEPS = 16
DEFAULT_MAX_REVISIONS = 1


def _components(binding, transport, *, max_plan_revisions=0, max_question_revisions=0,
                max_structured_revisions=0):
    plan_revisions = max_plan_revisions or max_structured_revisions
    question_revisions = max_question_revisions or max_structured_revisions
    policy = ModelPolicy(binding, transport, max_revisions=max_structured_revisions)
    memory = MemoryCognition(top_k=8)
    cognition = ReflectiveCognition(
        memory=memory,
        reflector=ModelCognitionGenerator("reflection", binding, transport),
        planner=ModelCognitionGenerator("hierarchical_updates", binding, transport),
        reflector_id="ollama-g5-fresh-v12-reflection",
        planner_id="ollama-g5-fresh-v12-hierarchical-updates",
        hierarchical=True,
        plan_updates=True,
        max_active_tasks=64,
        max_plan_revisions=plan_revisions,
        max_reflection_revisions=max_structured_revisions,
    )
    governance = CandidateGovernance(
        ModelAuditor(binding, transport), auditor_id="ollama-g5-fresh-v12-auditor",
        max_structured_revisions=max_structured_revisions)
    return {
        "policy": policy,
        "cognition": cognition,
        "governance": governance,
        "question_annotator": ModelQuestionAnnotator(
            binding, transport, max_revisions=question_revisions,
            unified_repair=bool(max_structured_revisions)),
        "session_annotator": ModelSessionAnnotator(
            binding, transport, max_revisions=max_structured_revisions),
        "scheduler": QuestionScheduler(priority_enabled=True, max_priority_streak=1),
        "observation_window": ObservationWindow(max_observations=96, max_chars=262144),
    }


def execution_binding(source_revision, *, model=DEFAULT_MODEL, endpoint_id=DEFAULT_ENDPOINT,
                      max_steps=DEFAULT_MAX_STEPS, max_revisions=DEFAULT_MAX_REVISIONS,
                      authorization_id, reasoning_effort=None, max_plan_revisions=0,
                      max_question_revisions=0, max_structured_revisions=0):
    """Freeze the exact online pilot binding without contacting a provider."""
    if not isinstance(source_revision, str) or not REVISION.fullmatch(source_revision):
        raise ValueError("Exact deployed source revision required")
    if not isinstance(authorization_id, str) or not authorization_id.strip():
        raise ValueError("Explicit execution authorization record required")
    if type(max_steps) is not int or max_steps < 1 or type(max_revisions) is not int or max_revisions < 0:
        raise ValueError("Invalid frozen stopping limits")
    if type(max_structured_revisions) is not int or not 0 <= max_structured_revisions <= 4:
        raise ValueError("Invalid structured revision limit")

    binding = ModelBinding("ollama", model, endpoint_id, 0.2, 2048)
    budget = RequestBudget(524288, 262144)
    # A credential-free route is sufficient to freeze public specifications.
    route = OllamaTransport(binding, "https://ollama.com", timeout=240,
                            reasoning_effort=reasoning_effort)
    transport = BudgetTransport(route, budget, delegate_id=endpoint_id)
    parts = _components(binding, transport, max_plan_revisions=max_plan_revisions,
                        max_question_revisions=max_question_revisions,
                        max_structured_revisions=max_structured_revisions)
    component_specs = {name: specification(parts[name])
                       for name in ("policy", "cognition", "governance")}
    question = specification(parts["question_annotator"])
    session = specification(parts["session_annotator"])
    scheduling = specification(parts["scheduler"])
    observation = specification(parts["observation_window"])
    frame, roles, plan = (fresh_family_frame_v3(), fresh_family_role_pack_v3(),
                          fresh_validation_plan_v3())
    role_index = {scenario: digest(cards)
                  for scenario, cards in roles["scenario_roles"].items()}
    stop = {"max_steps": max_steps, "max_revisions": max_revisions,
            "session": deepcopy(SESSION_PROTOCOL)}
    shared = {key: digest({"field": key, "pilot": plan["sha256"]}) for key in SHARED_FIELDS}
    shared.update(
        world_sha256=WORLD_CONTRACT_SHA256,
        role_inputs_sha256=digest(role_index),
        base_scheduler_sha256=digest(scheduling),
        observation_policy_sha256=digest(observation),
        player_policy_sha256=digest({"policy": "same-fixed-model-role-simulation-v1",
                                     "player_kind_is_not_human": True}),
        model_bindings_sha256=digest(component_specs),
        tool_permissions_sha256=digest({w["scenario_id"]: w["world"]["actions"]
                                        for w in frame["worlds"]}),
        stopping_policy_sha256=digest(stop),
        evaluator_plan_sha256=digest({"prompt_sha256": digest(EVALUATION_PROMPT),
                                      "semantic_contract_sha256": semantic_contract_sha256()}),
    )
    design = {
        "protocol": PROTOCOL,
        "source_revision": source_revision,
        "stage": "exploration",
        "scenarios": [{"id": w["scenario_id"], "family": w["family_id"],
                       "snapshot_sha256": w["snapshot_sha256"]} for w in frame["worlds"]],
        "used_families": ["incident", "interview", "launch", "negotiation", "library-space-allocation", "research-data-release", "museum-loan-conservation", "community-transit-adjustment"],
        "repetitions": 1,
        "order_seed": 20260913,
        "sampling_seed_policy": "unsupported_recorded",
        "analysis_plan_sha256": digest({"plan": plan["sha256"],
                                         "scope": "scorer-development-validation"}),
        "sample_size_plan_sha256": digest({"dialogues": 8, "one_arm_per_world": True}),
        "arms": {arm: {**flags, "shared": deepcopy(shared)} for arm, flags in ARMS.items()},
        "components": component_specs,
        "question_annotation": question,
        "session_annotation": session,
        "scheduling": scheduling,
        "observation_window": observation,
        "request_budget": budget.runtime_specification(),
        "cognition_storage": deepcopy(COGNITION_STORAGE),
        "scenario_role_inputs_sha256": role_index,
    }
    manifest = freeze_design(design)
    selected = []
    requested = {(row["scenario_id"], row["arm"]): row for row in plan["assignments"]}
    for row in manifest["assignments"]:
        if (row["scenario_id"], row["arm"]) in requested:
            selected.append(deepcopy(row))
    if len(selected) != 8 or {row["scenario_id"] for row in selected} != set(role_index):
        raise ValueError("Selected validation assignments drifted")
    raw = {
        "schema": "g5-fresh-family-v12-execution-binding-v1",
        "classification": "development-validation-only",
        "authorization_id": authorization_id,
        "authorized_external_payload": "eight frozen internal scenarios, role cards and dialogue context",
        "provider": "ollama",
        "model": model,
        "endpoint_id": endpoint_id,
        "base_url_sha256": digest("https://ollama.com/api/chat"),
        "credential_serialized": False,
        "source_revision": source_revision,
        "frame_sha256": frame["sha256"],
        "role_pack_sha256": roles["sha256"],
        "validation_plan_sha256": plan["sha256"],
        "prospective_gate_sha256": plan["prospective_gate_sha256"],
        "manifest": manifest,
        "selected_assignments": selected,
        "dialogue_count": 8,
        "max_steps": max_steps,
        "max_revisions": max_revisions,
        "evaluation_authorized": False,
        "complete_block_screening_authorized": False,
    }
    if reasoning_effort is not None:
        raw["reasoning_effort"] = reasoning_effort
    if max_plan_revisions:
        raw["max_plan_revisions"] = max_plan_revisions
    if max_question_revisions:
        raw["max_question_revisions"] = max_question_revisions
    if max_structured_revisions:
        raw["max_structured_revisions"] = max_structured_revisions
    return {**raw, "sha256": digest(raw)}


def _write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _public_transcript(source):
    messages = []
    for event in source["events"]:
        payload = event["payload"]
        row = {"turn": event["seq"], "event_id": event["event_id"],
               "speaker": payload["actor"], "action": payload["decision"]["action"]}
        if row["action"] == "speak":
            row["content"] = payload["decision"]["content"]
        if payload.get("receipt") is not None:
            row["receipt"] = payload["receipt"]
        messages.append(row)
    raw = {"schema": "g5-public-dialogue-v1", "world_id": source["world_id"],
           "assignment": source["binding"]["assignment"], "messages": messages,
           "seal_sha256": source["seal"]["sha256"]}
    return {**raw, "sha256": digest(raw)}


async def run_execution(execution, output, *, api_key, base_url="https://ollama.com",
                        transient_retries=3):
    """Resume the exact bound pilot; completed sealed sources are never replaced."""
    unsigned = {key: value for key, value in execution.items() if key != "sha256"}
    if execution.get("sha256") != digest(unsigned):
        raise ValueError("Execution binding checksum mismatch")
    verify_manifest(execution["manifest"])
    if execution.get("dialogue_count") != 8 or execution.get("evaluation_authorized") is not False:
        raise ValueError("Execution scope changed")
    if not isinstance(api_key, str) or not api_key.strip() or any(c.isspace() for c in api_key):
        raise ValueError("Explicit provider credential required")
    if type(transient_retries) is not int or transient_retries < 0:
        raise ValueError("Invalid retry limit")

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binding_path = output / "execution-binding.json"
    if binding_path.exists():
        if _load(binding_path) != execution:
            raise ValueError("Output belongs to another execution binding")
    else:
        _write_new(binding_path, execution)

    manifest, frame, roles = (execution["manifest"], fresh_family_frame_v3(),
                              fresh_family_role_pack_v3())
    worlds = {item["scenario_id"]: item for item in frame["worlds"]}
    binding = ModelBinding("ollama", execution["model"], execution["endpoint_id"], 0.2, 2048)
    budget = RequestBudget(524288, 262144)

    def route():
        return OllamaTransport(binding, base_url, api_key=api_key, timeout=240,
                               reasoning_effort=execution.get("reasoning_effort"))

    assembler = ExplicitRouteAssembler(
        {execution["endpoint_id"]: lambda: route()},
        {execution["endpoint_id"]: lambda: route()},
    )
    runtime_inputs = {scenario: {"spec": deepcopy(worlds[scenario]["world"]),
        "role_inputs": deepcopy(roles["scenario_roles"][scenario]),
        "max_steps": execution["max_steps"], "max_revisions": execution["max_revisions"],
        "allow_reopening": False, "reliable_reopening": False}
        for scenario in worlds}
    # Ensure the live route reconstructs every frozen adapter specification.
    store = World(output / "world.sqlite")
    factory = assembler.factory(world=store, manifest=manifest, runtime_inputs=runtime_inputs)
    try:
        for assignment in execution["selected_assignments"]:
            scenario = assignment["scenario_id"]
            source_path = output / "sources" / f"{scenario}.json"
            if source_path.exists():
                source = _load(source_path)
                verify_source(source, manifest)
                continue
            options = factory(assignment)
            runtime = await __import__("app.g5.runtime", fromlist=["Runtime"]).Runtime.open(**options)
            failures = 0
            while await runtime._store("frozen", runtime.world_id) is None:
                try:
                    result = await runtime.step()
                    failures = 0
                except StructuredOutputError:
                    # A terminal semantic/shape failure has already consumed the
                    # frozen component budget; restarting must not reset it.
                    raise
                except (TimeoutError, ConnectionError, ValueError, json.JSONDecodeError):
                    failures += 1
                    if failures > transient_retries:
                        raise
                    await asyncio.sleep(min(5, failures))
                    continue
                if result["status"] in ("session_closed", "cutoff"):
                    await runtime._store("freeze", runtime.world_id)
                elif result["status"] not in ("committed", "dialogue_frozen"):
                    raise ValueError("Unexpected pilot runtime outcome")
            source = await runtime._store("export_source", runtime.world_id)
            verify_source(source, manifest)
            _write_new(source_path, source)
            print(json.dumps({"milestone": "dialogue_sealed", "scenario": scenario,
                              "arm": assignment["arm"], "turns": len(source["events"]),
                              "source_sha256": source["sha256"]}), flush=True)

        transcripts = []
        for assignment in execution["selected_assignments"]:
            source = _load(output / "sources" / f"{assignment['scenario_id']}.json")
            verify_source(source, manifest)
            transcripts.append(_public_transcript(source))
        raw = {"schema": "g5-fresh-family-v12-public-transcripts-v1",
               "execution_sha256": execution["sha256"], "dialogues": transcripts}
        bundle = {**raw, "sha256": digest(raw)}
        transcript_path = output / "transcripts.json"
        if transcript_path.exists():
            if _load(transcript_path) != bundle:
                raise ValueError("Frozen transcript bundle changed")
        else:
            _write_new(transcript_path, bundle)
        print(json.dumps({"milestone": "pilot_dialogues_complete", "dialogues": 8,
                          "transcripts_sha256": bundle["sha256"]}), flush=True)
        return bundle
    finally:
        store.close()
