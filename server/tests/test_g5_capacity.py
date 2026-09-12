import copy
import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.capacity import BudgetTransport, RequestBudget, CapacityExceeded, measurements
from app.g5.components import specification
from app.g5.model_policy import Completion
from app.g5.runtime import Runtime
from app.g5.world import World, canonical


def budget_options(world, arm, budget):
    from test_g5_hierarchical_planning import session_hierarchy_options
    from test_g5_observation_window import configure
    from app.g5.observation import ObservationWindow
    harness, state, script, args = session_hierarchy_options(world, "D")
    seen = set()
    def wrap(adapter, path):
        if adapter is None or id(adapter) in seen:
            return
        seen.add(id(adapter))
        for name in ("memory", "semantic_scorer", "reflector", "planner", "auditor"):
            wrap(getattr(adapter, name, None), path + "." + name)
        if hasattr(getattr(adapter, "binding", None), "model"):
            adapter.transport = BudgetTransport(adapter.transport, budget, delegate_id="synthetic:" + path)
        if hasattr(adapter, "specification") and hasattr(adapter, "runtime_specification"):
            adapter.specification = adapter.runtime_specification()
    for key in ("policy", "cognition", "governance", "question_annotator", "session_annotator"):
        wrap(args[key], key)
    design = args["manifest"]["design"]
    design["request_budget"] = budget.runtime_specification()
    design["components"] = {key: specification(args[key]) for key in ("policy", "cognition", "governance")}
    design["question_annotation"] = specification(args["question_annotator"])
    design["session_annotation"] = specification(args["session_annotator"])
    for profile in design["arms"].values():
        profile["shared"]["model_bindings_sha256"] = digest(design["components"])
    args["manifest"] = freeze_design(design)
    args["world_id"] = arm
    args["ordinal"] = next(a["ordinal"] for a in args["manifest"]["assignments"] if a["arm"] == arm)
    for key in ("cognition", "governance"):
        if not ARMS[arm][key]:
            args[key] = None
    return harness, state, script, configure(args, ObservationWindow(2, 2048))


async def long_probe(world, arm, steps=40, *, delta_storage=False):
    from app.g5.session_journal import SESSION_PROTOCOL
    from app.g5.reopening import PROTOCOL
    if delta_storage:
        from test_g5_cognition_storage import storage_options
        _, _, args = storage_options(world, arm)
    else:
        _, _, _, args = budget_options(world, arm, RequestBudget(100000, 100000))
    captured = []
    if delta_storage and args["cognition"] is not None:
        original = args["cognition"]
        class Capture:
            def __getattr__(self, key):
                return getattr(original, key)
            async def __call__(self, view):
                state = await original(view)
                captured.append((view["actor"], copy.deepcopy(state)))
                return state
        args["cognition"] = Capture()
    design = args["manifest"]["design"]
    for value in design["arms"].values():
        value["shared"]["stopping_policy_sha256"] = digest({"max_steps": steps, "max_revisions": 1,
            "session": SESSION_PROTOCOL, "reopening": PROTOCOL})
    args["manifest"] = freeze_design(design)
    args["max_steps"] = steps
    runtime = await Runtime.open(**args)
    for version in range(steps):
        session = await runtime.session_journal.project()
        if session["status"] == "closed":
            result = await runtime.step(reopen_request={"id": f"probe-{session['episode']}",
                "episode": session["episode"], "version": version})
        else:
            result = await runtime.step()
        if result["status"] != "committed":
            raise AssertionError("Synthetic probe did not advance: " + result["status"])
        if captured:
            actor, expected = captured[-1]
            _, view = await runtime._store("observe", arm, actor)
            if canonical(view["cognition_state"]) != canonical(expected):
                raise AssertionError("Stored cognition did not reconstruct original model state")
    await runtime._store("freeze", arm)
    return await runtime._store("export_source", arm)


class CapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_http_delegate_is_bounded_without_recursive_wrapper_requirement(self):
        import httpx
        from app.g5.capacity import verify_declared_budget
        from app.g5.ollama_transport import OllamaTransport
        from app.g5.model_policy import ModelBinding, ModelPolicy
        from test_g5_model_policy import view
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(200, json={"model": "fixed", "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": '{"action":"wait","content":"","operation":""}'}})
        binding = ModelBinding("ollama", "fixed", "synthetic-http", .2, 512)
        budget = RequestBudget(100000, 100000)
        native = OllamaTransport(binding, "https://provider.invalid", http_transport=httpx.MockTransport(respond))
        adapter = ModelPolicy(binding, BudgetTransport(native, budget, delegate_id="synthetic-http"))
        verify_declared_budget(adapter.runtime_specification(), budget.runtime_specification())
        self.assertEqual((await adapter(view(), ())).action, "wait")
        self.assertEqual(len(calls), 1)
        native._timeout += 1
        with self.assertRaises(ValueError):
            await adapter(view(), ())
        self.assertEqual(len(calls), 1)

    async def test_exact_unicode_request_boundary_and_response_limit_no_truncation(self):
        calls = []
        async def transport(request):
            calls.append(copy.deepcopy(request))
            return Completion("原文", "offline", "fixed", "mock", digest(request), "stop")
        request = {"binding": {}, "messages": [{"role": "user", "content": "完整中文🙂"}]}
        size = len(canonical(request).encode("utf-8"))
        captured = []
        token = measurements.set(captured)
        try:
            exact = BudgetTransport(transport, RequestBudget(size, 1000), delegate_id="synthetic")
            self.assertEqual((await exact(request)).content, "原文")
            self.assertEqual(calls, [request])
            rejected = BudgetTransport(transport, RequestBudget(size - 1, 1000), delegate_id="synthetic")
            with self.assertRaises(CapacityExceeded):
                await rejected(request)
            self.assertEqual(len(calls), 1)
            oversized = BudgetTransport(transport, RequestBudget(size, 1), delegate_id="synthetic")
            with self.assertRaises(CapacityExceeded):
                await oversized(request)
            self.assertEqual([r["status"] for r in captured], ["received", "request_capacity_exceeded", "response_capacity_exceeded"])
            self.assertEqual(captured[0]["request_bytes"], size)
            self.assertNotIn("完整", canonical(captured))
        finally:
            measurements.reset(token)

    async def test_all_arms_overflow_before_transport_keeps_world_and_reports_capacity(self):
        for arm in ARMS:
            world = World(":memory:")
            self.addCleanup(world.close)
            harness, state, script, args = budget_options(world, arm, RequestBudget(1, 100000))
            runtime = Runtime(**args)
            with self.assertRaises(CapacityExceeded):
                await runtime.step()
            self.assertEqual(world.events(arm), [])
            self.assertEqual(harness.calls + state["requests"] + script.calls, [])
            last = world.attempts(arm)[-1]
            self.assertEqual(last["error_code"], "capacity_exceeded")
            self.assertEqual(last["model_io"][0]["status"], "request_capacity_exceeded")
            runtime.policy.transport.budget = RequestBudget(100000, 100000)
            with self.assertRaises(ValueError):
                await runtime.step()
            self.assertEqual(world.events(arm), [])

    async def test_common_declaration_rejects_unprotected_nested_model(self):
        world = World(":memory:")
        self.addCleanup(world.close)
        _, _, _, args = budget_options(world, "D", RequestBudget(100000, 100000))
        changed = copy.deepcopy(args["manifest"]["design"])
        del changed["components"]["cognition"]["planner_specification"]["transport"]
        for profile in changed["arms"].values():
            profile["shared"]["model_bindings_sha256"] = digest(changed["components"])
        with self.assertRaises(ValueError):
            freeze_design(changed)
        args["policy"].transport = args["policy"].transport.delegate
        with self.assertRaises(ValueError):
            Runtime(**args)

    async def test_metadata_scope_does_not_leak_between_async_tasks(self):
        import asyncio
        async def transport(request):
            await asyncio.sleep(0)
            return Completion("ok", "offline", "fixed", "mock", digest(request), "stop")
        wrapped = BudgetTransport(transport, RequestBudget(1000, 1000), delegate_id="synthetic")
        async def run(i):
            own = []
            token = measurements.set(own)
            try:
                await wrapped({"request": i})
                return own
            finally:
                measurements.reset(token)
        one, two = await asyncio.gather(run(1), run(2))
        self.assertEqual([r["request_sha256"] for r in one], [digest({"request": 1})])
        self.assertEqual([r["request_sha256"] for r in two], [digest({"request": 2})])
        self.assertIsNone(measurements.get())

    async def test_forty_turns_reopening_retains_history_and_measures_total_input(self):
        from app.g5.capacity_profile import profile
        for arm in ARMS:
            world = World(":memory:")
            self.addCleanup(world.close)
            source = await long_probe(world, arm)
            result = profile(source)
            self.assertEqual(len(result["events"]), 40)
            self.assertEqual(len(source["reopening"]), 12)
            self.assertTrue(all(v["request_bytes"]["max"] <= 100000 for v in result["stage_io"].values()))
            self.assertEqual(result["stage_io"]["policy"]["request_bytes"]["count"], 40)
            self.assertGreater(result["source_json_bytes"], sum(e["event_bytes"] for e in result["events"]))
            self.assertEqual(source["seal"]["version"], 40)


if __name__ == "__main__":
    # Explicit synthetic evidence run, separate from unittest discovery. Preserve
    # its source database and all four source/profile files in a NEW directory.
    import argparse
    import asyncio
    import json
    import os
    from pathlib import Path
    from app.g5.capacity_profile import profile
    parser = argparse.ArgumentParser(description="Offline scripted capacity probe; no live model calls")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700)
    def write(name, value):
        fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    async def run():
        world = World(str(directory / "synthetic-world.sqlite"))
        results = {}
        try:
            for arm in ARMS:
                source = await long_probe(world, arm)
                result = profile(source)
                write(arm + "-source.json", source)
                write(arm + "-profile.json", result)
                results[arm] = {"source_sha256": source["sha256"], "profile_sha256": result["sha256"],
                    "source_json_bytes": result["source_json_bytes"], "events": len(result["events"]),
                    "peak_request_bytes": max(s["request_bytes"]["max"] for s in result["stage_io"].values())}
            raw = {"schema": "g5-synthetic-capacity-probe-v1", "evidence_use": "synthetic-engineering-only",
                   "arms": results, "real_model_calls": 0, "qualification": "not_inferred"}
            write("summary.json", {**raw, "sha256": digest(raw)})
            print(json.dumps(raw, sort_keys=True))
        finally:
            world.close()
    asyncio.run(run())
