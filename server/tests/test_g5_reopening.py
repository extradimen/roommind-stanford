"""Reliable request package: identical contract on both real local databases.

All model responses are synthetic. Concurrent inference may repeat; publication
and terminal receipts must not. Each test owns its database/schema.
"""
import asyncio
import json
import os
import sys
import tempfile
import unittest
import uuid

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.reopening import PROTOCOL
from app.g5.runtime import Runtime
from app.g5.world import Conflict, World
from app.g5.model_session import SessionAnnotation
from test_g5_session_composed import session_options


def options(world, arm="D"):
    harness, state, args = session_options(world, arm, closing=True, reopening=True)
    design = args["manifest"]["design"]
    for profile in design["arms"].values():
        from app.g5.session_journal import SESSION_PROTOCOL
        profile["shared"]["stopping_policy_sha256"] = digest({"max_steps": 8,
            "max_revisions": 1, "session": SESSION_PROTOCOL, "reopening": PROTOCOL})
    args["manifest"] = freeze_design(design)
    args["reliable_reopening"] = True
    return harness, state, args


REQUEST = {"id": "request-1", "episode": 1, "version": 4}


class Contract:
    async def test_delta_storage_full_components_four_arms_reconnect_and_parity(self):
        import copy
        from test_g5_cognition_storage import storage_options
        from app.g5.artifacts import verify_source
        local = World(":memory:")
        self.addCleanup(local.close)
        for arm in ARMS:
            _, _, args = storage_options(self.world, arm)
            runtime = await Runtime.open(**args)
            _, _, local_args = storage_options(local, arm)
            reference = Runtime(**local_args)
            for _ in range(4):
                self.assertEqual(await runtime.step(), await reference.step())
            await self.reconnect()
            _, _, args = storage_options(self.world, arm)
            runtime = await Runtime.open(**args)
            self.assertEqual(await runtime.step(reopen_request=REQUEST), await reference.step(reopen_request=REQUEST))
            for _ in range(2):
                self.assertEqual(await runtime.step(), await reference.step())
            for role in args["spec"]["roles"]:
                self.assertEqual(await runtime._store("observe", arm, role), local.observe(arm, role))
            if ARMS[arm]["cognition"]:
                from app.g5.world import Decision
                events = await runtime._store("events", arm)
                broken = copy.deepcopy(events[-1]["payload"]["audit"])
                broken["cognition_state"]["base_sha256"] = "corrupt"
                with self.assertRaises(ValueError):
                    await runtime._store("commit", arm, expected_version=len(events), request_id="bad-base",
                        actor=events[-1]["payload"]["actor"], decision=Decision("wait"), audit=broken)
                self.assertEqual(await runtime._store("events", arm), events)
            await runtime._store("freeze", arm)
            bundle = await runtime._store("export_source", arm)
            verify_source(bundle, args["manifest"])
            await self.reconnect()
            from app.g5.question_journal import invoke
            self.assertEqual(await invoke(self.world, "export_source", arm), bundle)

    async def test_delta_storage_process_death_and_receipt_recovery(self):
        from test_g5_cognition_storage import storage_options
        child = CHILD.replace("from test_g5_reopening import options, REQUEST",
                              "from test_g5_reopening import REQUEST\nfrom test_g5_cognition_storage import storage_options as options")
        for arm, mode in (("B", "inside"), ("D", "after")):
            _, _, args = storage_options(self.world, arm)
            runtime = await Runtime.open(**args)
            for _ in range(4):
                await runtime.step()
            before = await runtime._store("events", arm)
            process = await asyncio.create_subprocess_exec(sys.executable, "-c", child,
                self.backend, self.location, arm, mode, env={**os.environ, "PYTHONPATH": "server:server/tests"},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                _, stderr = await asyncio.wait_for(process.communicate(), 30)
            except BaseException:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                raise
            self.assertEqual(process.returncode, {"inside": 75, "after": 74}[mode], stderr.decode())
            await self.reconnect()
            harness, _, args = storage_options(self.world, arm)
            runtime = await Runtime.open(**args)
            self.assertEqual((await runtime.step(reopen_request=REQUEST))["status"], "committed")
            self.assertEqual((await runtime._store("events", arm))[:4], before)
            self.assertEqual(len(await runtime._store("events", arm)), 5)
            if mode == "after":
                self.assertEqual(harness.calls, [])
            for _ in range(2):
                await runtime.step()
            await runtime._store("freeze", arm)
            await runtime._store("export_source", arm)

    async def test_full_request_budget_four_arms_reconnect_and_export(self):
        from test_g5_capacity import budget_options
        from app.g5.capacity import RequestBudget
        from app.g5.artifacts import verify_source
        from app.g5.question_journal import invoke
        budget = RequestBudget(100000, 100000)
        for arm in ARMS:
            _, _, _, args = budget_options(self.world, arm, budget)
            runtime = await Runtime.open(**args)
            for _ in range(4):
                await runtime.step()
            await self.reconnect()
            _, _, _, args = budget_options(self.world, arm, budget)
            runtime = await Runtime.open(**args)
            await runtime.step(reopen_request=REQUEST)
            await runtime.step()
            await runtime.step()
            await runtime._store("freeze", arm)
            bundle = await runtime._store("export_source", arm)
            verify_source(bundle, args["manifest"])
            rows = [m for a in bundle["attempts"] for m in a.get("model_io", [])]
            self.assertTrue(rows)
            self.assertTrue(all(m["budget_sha256"] == digest(budget.runtime_specification()) and
                m["request_bytes"] <= budget.max_request_bytes and m["response_bytes"] <= budget.max_response_bytes
                for m in rows))
            stages = {a["stage"] for a in bundle["attempts"] if a.get("model_io")}
            self.assertEqual(stages, {"policy", "annotation", "session_annotation"} |
                ({"cognition"} if ARMS[arm]["cognition"] else set()) |
                ({"governance"} if ARMS[arm]["governance"] else set()))
            await self.reconnect()
            self.assertEqual(await invoke(self.world, "export_source", arm), bundle)

    async def test_full_window_hierarchy_recovers_from_simulated_store_outage(self):
        from app.g5.question_journal import invoke
        from test_g5_hierarchical_planning import session_hierarchy_options
        from test_g5_observation_window import configure
        from app.g5.observation import ObservationWindow
        class UnavailableStore:
            def __init__(self, delegate, phase):
                self.delegate, self.phase = delegate, phase
                self.down = phase == "read"
            def __getattr__(self, name):
                async def call(*args, **kwargs):
                    if name == "record_attempt" and args[1]["stage"] == self.phase:
                        if args[1]["status"] == ("succeeded" if self.phase == "policy" else "started"):
                            if self.phase == "commit":
                                await invoke(self.delegate, name, *args, **kwargs)
                            self.down = True
                    if self.down:
                        raise ConnectionError("synthetic unavailable store")
                    return await invoke(self.delegate, name, *args, **kwargs)
                return call
        for arm in ARMS:
            # Separate owned world IDs for each failure point; never replace a run.
            for phase in ("read", "policy", "commit"):
                world_id = arm + "-" + phase
                reference = World(":memory:")
                self.addCleanup(reference.close)
                _, _, _, args = session_hierarchy_options(self.world, arm)
                args["world_id"] = world_id
                runtime = await Runtime.open(**configure(args, ObservationWindow(2, 2048)))
                _, _, _, local_args = session_hierarchy_options(reference, arm)
                local_args["world_id"] = world_id
                local = Runtime(**configure(local_args, ObservationWindow(2, 2048)))
                self.assertEqual(await runtime.step(), await local.step())
                before = await runtime._store("events", world_id)
                proxy = UnavailableStore(self.world, phase)
                runtime.world = proxy
                runtime.question_journal.store = proxy
                runtime.session_journal.store = proxy
                with self.assertRaises(ConnectionError):
                    await runtime.step()
                self.assertEqual(await invoke(self.world, "events", world_id), before)
                await self.reconnect()
                _, _, _, args = session_hierarchy_options(self.world, arm)
                args["world_id"] = world_id
                runtime = await Runtime.open(**configure(args, ObservationWindow(2, 2048)))
                for _ in range(3):
                    self.assertEqual(await runtime.step(), await local.step())
                await runtime._store("freeze", world_id)
                bundle = await runtime._store("export_source", world_id)
                self.assertEqual(bundle["events"], reference.events(world_id))
                if phase != "read":
                    self.assertTrue(any(r["status"] == "started" and not any(
                        f["attempt_id"] == r["attempt_id"] and f["status"] != "started"
                        for f in bundle["attempts"]) for r in bundle["attempts"]))

    async def test_source_export_all_journals_four_arms_and_offline_reverification(self):
        import copy
        from app.g5.artifacts import verify_source
        for arm in ARMS:
            runtime, _, _, args = await self.prepare(arm)
            await runtime.step(reopen_request=REQUEST)
            await runtime.step()
            await runtime.step()
            with self.assertRaises(ValueError):
                await runtime._store("export_source", arm)
            await runtime._store("freeze", arm)
            await runtime.step(reopen_request={"id": "late-frozen", "episode": 2, "version": 7})
            bundle = await runtime._store("export_source", arm)
            summary = verify_source(bundle, args["manifest"])
            self.assertEqual(summary["events"], 7)
            self.assertEqual(summary["reopening_requests"], 2)
            self.assertEqual(bundle["attempts"], await runtime._store("attempts", arm))
            self.assertEqual(summary["projections"]["session"], await runtime.session_journal.project())
            self.assertEqual(summary["projections"]["questions"], await runtime.question_journal.project())
            await self.reconnect()
            from app.g5.question_journal import invoke
            self.assertEqual(await invoke(self.world, "export_source", arm), bundle)
            for mutation in ("event", "attempt", "receipt", "seal"):
                changed = copy.deepcopy(bundle)
                if mutation == "event":
                    changed["events"][0]["payload"]["decision"]["content"] += "corruption"
                elif mutation == "attempt":
                    changed["attempts"][0]["actor"] = "unregistered"
                elif mutation == "receipt":
                    changed["reopening"] = [r for r in changed["reopening"] if r["request"]["id"] != REQUEST["id"]]
                else:
                    changed["seal"]["version"] -= 1
                changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
                with self.assertRaises(ValueError):
                    verify_source(changed, args["manifest"])

    async def test_seal_four_arms_survives_reconnect_and_prevents_new_publication(self):
        from app.g5.world import Decision
        for arm in ARMS:
            runtime, _, _, _ = await self.prepare(arm)
            original = await runtime.step(reopen_request=REQUEST)
            await runtime.step()
            await runtime.step()
            before = await runtime._store("events", arm)
            seal = await runtime._store("freeze", arm)
            self.assertEqual(seal["events_sha256"], digest(before))
            await self.reconnect()
            harness, _, args = options(self.world, arm)
            runtime = await Runtime.open(**args)
            self.assertEqual(await runtime._store("freeze", arm), seal)
            self.assertEqual((await runtime.step())["status"], "dialogue_frozen")
            self.assertEqual(await runtime.step(reopen_request=REQUEST), original)
            self.assertEqual((await runtime.step(reopen_request={"id": "after-seal", "episode": 2, "version": 7}))["status"], "reopen_frozen")
            self.assertEqual(harness.calls, [])
            with self.assertRaises(Conflict):
                await runtime._store("commit", arm, expected_version=7, request_id="new-event", actor="sre",
                                     decision=Decision("speak", "New speech"), audit={})
            self.assertEqual(await runtime._store("events", arm), before)

    async def test_freeze_racing_reopening_prevents_inflight_publication(self):
        runtime, _, _, _ = await self.prepare()
        entered, release = asyncio.Event(), asyncio.Event()
        delegate = runtime.session_annotator
        class Gate:
            def runtime_specification(self):
                return delegate.runtime_specification()
            async def __call__(self, *args):
                result = await delegate(*args)
                entered.set()
                await asyncio.wait_for(release.wait(), 5)
                return result
        runtime.session_annotator = Gate()
        task = asyncio.create_task(runtime.step(reopen_request=REQUEST))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            seal = await runtime._store("freeze", "D")
            release.set()
            self.assertEqual((await task)["status"], "reopen_frozen")
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(len(await runtime._store("events", "D")), 4)
        self.assertEqual(await runtime._store("frozen", "D"), seal)

    async def test_window_full_components_four_arms_with_reopen_and_database_parity(self):
        from test_g5_hierarchical_planning import session_hierarchy_options
        from test_g5_observation_window import configure
        from app.g5.observation import ObservationWindow
        reference = World(":memory:")
        self.addCleanup(reference.close)
        for arm in ARMS:
            harness, state, script, args = session_hierarchy_options(self.world, arm)
            runtime = await Runtime.open(**configure(args, ObservationWindow(2, 2048)))
            _, _, _, local_args = session_hierarchy_options(reference, arm)
            local = Runtime(**configure(local_args, ObservationWindow(2, 2048)))
            for _ in range(4):
                self.assertEqual(await runtime.step(), await local.step())
            await self.reconnect()
            harness, state, script, args = session_hierarchy_options(self.world, arm)
            runtime = await Runtime.open(**configure(args, ObservationWindow(2, 2048)))
            self.assertEqual(await runtime.step(reopen_request=REQUEST), await local.step(reopen_request=REQUEST))
            for _ in range(2):
                self.assertEqual(await runtime.step(), await local.step())
            self.assertEqual(await runtime._store("events", arm), reference.events(arm))
            self.assertEqual((await runtime.step())["status"], "session_closed")
            for kind, data in harness.calls:
                if kind not in {"policy", "audit", "annotation"}:
                    continue
                context = data["role_view"] if kind == "policy" else data["context"]
                self.assertLessEqual(len(context["observations"]), 2)
                self.assertGreater(context["observation_delivery"]["omitted_count"], 0)
            for request in state["requests"]:
                context = json.loads(request["messages"][1]["content"])["context"]
                self.assertLessEqual(len(context["observations"]), 2)
                self.assertGreater(context["observation_delivery"]["omitted_count"], 0)

    async def test_hierarchy_current_components_across_sessions_four_arms(self):
        from test_g5_hierarchical_planning import session_hierarchy_options
        reference = World(":memory:")
        self.addCleanup(reference.close)
        for arm in ARMS:
            _, _, script, args = session_hierarchy_options(self.world, arm)
            runtime = await Runtime.open(**args)
            _, _, _, local_args = session_hierarchy_options(reference, arm)
            local = Runtime(**local_args)
            for _ in range(4):
                self.assertEqual(await runtime.step(), await local.step())
            old = await runtime._store("events", arm)
            await self.reconnect()
            _, _, script, args = session_hierarchy_options(self.world, arm)
            runtime = await Runtime.open(**args)
            self.assertEqual(await runtime.step(reopen_request=REQUEST), await local.step(reopen_request=REQUEST))
            for _ in range(2):
                self.assertEqual(await runtime.step(), await local.step())
            self.assertEqual(await runtime._store("events", arm), reference.events(arm))
            self.assertEqual((await runtime._store("events", arm))[:4], old)
            self.assertEqual((await runtime.session_journal.project())["status"], "closed")
            for actor in runtime.roles:
                _, view = await runtime._store("observe", arm, actor)
                if ARMS[arm]["cognition"]:
                    self.assertEqual(view["cognition_state"]["plans"][0]["proposal"],
                                     view["cognition_state"]["plans"][-1]["proposal"])
                    self.assertGreater(len(view["cognition_state"]["plans"]), 1)
                    self.assertEqual(view["cognition_state"]["owner"], actor)
                else:
                    self.assertEqual(view["cognition_state"], {})
            if not ARMS[arm]["cognition"]:
                self.assertEqual(script.calls, [])

    async def prepare(self, arm="D"):
        harness, state, args = options(self.world, arm)
        runtime = await Runtime.open(**args)
        for _ in range(4):
            await runtime.step()
        return runtime, harness, state, args

    async def test_four_arms_receipt_survives_reclose_and_reconnect(self):
        for arm in ARMS:
            runtime, harness, state, args = await self.prepare(arm)
            old = await runtime._store("events", arm)
            questions = await runtime.question_journal.project()
            result = await runtime.step(reopen_request=REQUEST)
            self.assertEqual(result["status"], "committed")
            self.assertEqual(result["event"]["payload"]["actor"], "sre")
            self.assertEqual((await runtime.session_journal.project())["episode"], 2)
            self.assertEqual((await runtime.question_journal.project())["questions"], questions["questions"])
            self.assertEqual((await runtime._store("events", arm))[:4], old)
            await runtime.step()
            await runtime.step()
            self.assertEqual((await runtime.step())["status"], "session_closed")
            await self.reconnect()
            harness, state, args = options(self.world, arm)
            runtime = await Runtime.open(**args)
            attempts = await runtime._store("attempts", arm)
            self.assertEqual(await runtime.step(reopen_request=REQUEST), result)
            self.assertEqual(harness.calls, [])
            self.assertEqual(state["requests"], [])
            self.assertEqual(await runtime._store("attempts", arm), attempts)
            self.assertEqual(len(await runtime._store("events", arm)), 7)
            self.assertNotIn("reopen_request", str(await runtime._store("observe", arm, "sre")))
            late = {**REQUEST, "id": "late-original-target"}
            self.assertEqual((await runtime.step(reopen_request=late))["status"], "reopen_stale")
            with self.assertRaises(Conflict):
                await runtime.step(reopen_request={**REQUEST, "episode": 2, "version": 7})
            # Fresh request preserves total eight-step budget, not eight per episode.
            await runtime.step(reopen_request={"id": "new", "episode": 2, "version": 7})
            self.assertEqual((await runtime.step())["status"], "cutoff")
            self.assertEqual(len(await runtime._store("events", arm)), 8)

    async def test_technical_failure_retries_identity_without_history_reset(self):
        runtime, harness, state, args = await self.prepare()
        old = await runtime._store("events", "D")
        state["fail"] = True
        with self.assertRaises(TimeoutError):
            await runtime.step(reopen_request=REQUEST)
        self.assertEqual(await runtime._store("events", "D"), old)
        failed = [a for a in await runtime._store("attempts", "D") if a.get("reopen_request") == REQUEST]
        self.assertTrue(any(a["error_code"] == "timeout" for a in failed))
        await self.reconnect()
        _, _, args = options(self.world)
        runtime = await Runtime.open(**args)
        self.assertEqual((await runtime.step(reopen_request=REQUEST))["status"], "committed")
        self.assertEqual((await runtime._store("events", "D"))[:4], old)
        retained = await runtime._store("attempts", "D")
        self.assertTrue(all(a in retained for a in failed))

    async def test_decline_is_durable_and_does_not_publish(self):
        runtime, harness, state, args = await self.prepare()
        delegate = runtime.session_annotator
        class Decline:
            def runtime_specification(self):
                return delegate.runtime_specification()
            async def __call__(self, *args):
                evidence = await delegate(*args)
                return SessionAnnotation(None, evidence.model_evidence)
        runtime.session_annotator = Decline()
        result = await runtime.step(reopen_request=REQUEST)
        self.assertEqual(result["status"], "reopen_declined")
        self.assertEqual(len(await runtime._store("events", "D")), 4)
        await self.reconnect()
        harness, state, args = options(self.world)
        runtime = await Runtime.open(**args)
        self.assertEqual(await runtime.step(reopen_request=REQUEST), result)
        self.assertEqual(harness.calls, [])
        self.assertEqual((await runtime.session_journal.project())["status"], "closed")

    async def test_concurrent_same_or_different_request_publish_once(self):
        for arm, same in (("A", True), ("D", False)):
            runtime, _, _, args = await self.prepare(arm)
            _, _, other_args = options(self.world, arm)
            other = await Runtime.open(**other_args)
            ready = asyncio.Event()
            count = 0
            def gated(delegate):
                class Gate:
                    def runtime_specification(self):
                        return delegate.runtime_specification()
                    async def __call__(self, *args):
                        nonlocal count
                        result = await delegate(*args)
                        count += 1
                        if count == 2:
                            ready.set()
                        await asyncio.wait_for(ready.wait(), 5)
                        return result
                return Gate()
            runtime.session_annotator = gated(runtime.session_annotator)
            other.session_annotator = gated(other.session_annotator)
            request2 = REQUEST if same else {**REQUEST, "id": "competitor"}
            results = await asyncio.gather(runtime.step(reopen_request=REQUEST), other.step(reopen_request=request2))
            if same:
                self.assertEqual(results[0], results[1])
            else:
                self.assertEqual(sorted(r["status"] for r in results), ["committed", "reopen_stale"])
            self.assertEqual(len(await runtime._store("events", arm)), 5)
            self.assertEqual((await runtime.session_journal.project())["episode"], 2)

    async def test_event_and_receipt_atomic_on_failure_and_ack_loss(self):
        runtime, _, _, args = await self.prepare()
        original = self.world._reopening_insert
        if asyncio.iscoroutinefunction(original):
            async def fail(*args):
                if args[-2] == "result":
                    raise ConnectionError("injected receipt failure")
                return await original(*args)
        else:
            def fail(*args):
                if args[-2] == "result":
                    raise ConnectionError("injected receipt failure")
                return original(*args)
        self.world._reopening_insert = fail
        try:
            with self.assertRaises(ConnectionError):
                await runtime.step(reopen_request=REQUEST)
        finally:
            self.world._reopening_insert = original
        self.assertEqual(len(await runtime._store("events", "D")), 4)
        original_commit = self.world.commit
        if asyncio.iscoroutinefunction(original_commit):
            async def lose_ack(*args, **kwargs):
                await original_commit(*args, **kwargs)
                raise ConnectionError("injected ack loss")
        else:
            def lose_ack(*args, **kwargs):
                original_commit(*args, **kwargs)
                raise ConnectionError("injected ack loss")
        self.world.commit = lose_ack
        try:
            with self.assertRaises(ConnectionError):
                await runtime.step(reopen_request=REQUEST)
        finally:
            self.world.commit = original_commit
        await self.reconnect()
        harness, state, args = options(self.world)
        runtime = await Runtime.open(**args)
        result = await runtime.step(reopen_request=REQUEST)
        self.assertEqual(result["event"], (await runtime._store("events", "D"))[-1])
        self.assertEqual(len(await runtime._store("events", "D")), 5)
        self.assertEqual(harness.calls, [])

    async def test_invalid_target_and_protocol_drift_before_model_calls(self):
        runtime, harness, _, args = await self.prepare()
        count = len(harness.calls)
        for request in ({}, {**REQUEST, "version": True}, {**REQUEST, "id": " "},
                        {**REQUEST, "episode": 0}, {**REQUEST, "extra": "field"}):
            with self.assertRaises(ValueError):
                await runtime.step(reopen_request=request)
        with self.assertRaises(ValueError):
            await runtime.step(reopen=True)
        runtime.reliable_reopening = False
        with self.assertRaises(ValueError):
            await runtime.step(reopen_request=REQUEST)
        self.assertEqual(len(harness.calls), count)

    async def test_future_and_superseded_failed_requests_never_activate_later(self):
        runtime, harness, state, _ = await self.prepare()
        future = {"id": "future", "episode": 2, "version": 7}
        self.assertEqual((await runtime.step(reopen_request=future))["status"], "reopen_stale")
        state["fail"] = True
        with self.assertRaises(TimeoutError):
            await runtime.step(reopen_request=REQUEST)
        await runtime.step(reopen_request={**REQUEST, "id": "replacement-request"})
        await runtime.step()
        await runtime.step()
        count = len(harness.calls)
        for request in (future, REQUEST):
            self.assertEqual((await runtime.step(reopen_request=request))["status"], "reopen_stale")
        self.assertEqual(len(harness.calls), count)
        self.assertEqual(len(await runtime._store("events", "D")), 7)

    async def test_closed_budget_cutoff_receipt_never_resets_budget(self):
        harness, _, args = options(self.world)
        from app.g5.session_journal import SESSION_PROTOCOL
        design = args["manifest"]["design"]
        for profile in design["arms"].values():
            profile["shared"]["stopping_policy_sha256"] = digest({"max_steps": 4,
                "max_revisions": 1, "session": SESSION_PROTOCOL, "reopening": PROTOCOL})
        args.update(manifest=freeze_design(design), max_steps=4)
        runtime = await Runtime.open(**args)
        for _ in range(4):
            await runtime.step()
        count = len(harness.calls)
        result = await runtime.step(reopen_request=REQUEST)
        self.assertEqual(result["status"], "cutoff")
        self.assertEqual(await runtime.step(reopen_request=REQUEST), result)
        self.assertEqual(len(harness.calls), count)
        self.assertEqual(len(await runtime._store("events", "D")), 4)

    async def test_process_death_before_and_after_commit(self):
        for arm, mode in (("A", "before"), ("B", "inside"), ("D", "after")):
            runtime, _, _, _ = await self.prepare(arm)
            before = await runtime._store("events", arm)
            process = await asyncio.create_subprocess_exec(sys.executable, "-c", CHILD,
                self.backend, self.location, arm, mode, env={**os.environ, "PYTHONPATH": "server:server/tests"},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), 20)
            except BaseException:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                raise
            self.assertEqual(process.returncode, {"before": 73, "inside": 75, "after": 74}[mode], stderr.decode())
            await self.reconnect()
            harness, _, args = options(self.world, arm)
            runtime = await Runtime.open(**args)
            result = await runtime.step(reopen_request=REQUEST)
            self.assertEqual(result["status"], "committed")
            self.assertEqual((await runtime._store("events", arm))[:4], before)
            self.assertEqual(len(await runtime._store("events", arm)), 5)
            if mode == "after":
                self.assertEqual(harness.calls, [])
            attempts = await runtime._store("attempts", arm)
            starts = [a for a in attempts if a["stage"] == "commit" and a["status"] == "started"
                      and a.get("reopen_request") == REQUEST]
            self.assertTrue(any(not any(b["attempt_id"] == a["attempt_id"] and b["status"] != "started"
                                         for b in attempts) for a in starts))


CHILD = '''
import asyncio, os, sys
from app.g5.runtime import Runtime
from app.g5.world import World
from test_g5_reopening import options, REQUEST
async def run():
    backend, location, arm, mode = sys.argv[1:]
    if backend == "sqlite":
        world = World(location)
    else:
        import asyncpg
        from app.g5.postgres import PostgresWorld
        pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"])
        world = PostgresWorld(pool, location)
    _, _, args = options(world, arm)
    runtime = await Runtime.open(**args)
    delegate = world.commit
    insert = world._reopening_insert
    if mode == "inside":
        if backend == "sqlite":
            def interrupted(*args):
                if args[-2] == "result":
                    os._exit(75)
                return insert(*args)
        else:
            async def interrupted(*args):
                if args[-2] == "result":
                    os._exit(75)
                return await insert(*args)
        world._reopening_insert = interrupted
    async def die(*args, **kwargs):
        if mode == "before":
            os._exit(73)
        result = delegate(*args, **kwargs)
        if hasattr(result, "__await__"):
            await result
        os._exit(74)
    world.commit = die
    await runtime.step(reopen_request=REQUEST)
asyncio.run(run())
'''


class SQLiteReopening(Contract, unittest.IsolatedAsyncioTestCase):
    backend = "sqlite"
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="g5-reopening-")
        self.location = self.tmp.name + "/world.sqlite"
        self.world = World(self.location)
    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()
    async def reconnect(self):
        self.world.close()
        self.world = World(self.location)


@unittest.skipUnless(os.environ.get("G5_TEST_DSN"), "G5_TEST_DSN not supplied")
class PostgreSQLReopening(Contract, unittest.IsolatedAsyncioTestCase):
    backend = "postgres"
    async def asyncSetUp(self):
        import asyncpg
        from app.g5.postgres import PostgresWorld
        self.location = "g5_test_" + uuid.uuid4().hex
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.location)
        self.owned = False
        async with self.pool.acquire() as c:
            await c.execute(f"CREATE SCHEMA {self.location}")
        self.owned = True
        await self.world.install()
    async def asyncTearDown(self):
        if self.owned:
            async with self.pool.acquire() as c:
                await c.execute(f"DROP SCHEMA {self.location} CASCADE")
        await self.pool.close()
    async def reconnect(self):
        import asyncpg
        from app.g5.postgres import PostgresWorld
        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.location)

    async def test_exact_four_arm_sqlite_parity_including_hashes(self):
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        for arm in ARMS:
            pg, _, _, _ = await self.prepare(arm)
            _, _, args = options(sqlite, arm)
            local = Runtime(**args)
            for _ in range(4):
                await local.step()
            self.assertEqual(await pg.step(reopen_request=REQUEST), await local.step(reopen_request=REQUEST))
            for _ in range(2):
                self.assertEqual(await pg.step(), await local.step())
            self.assertEqual(await pg.session_journal.project(), await local.session_journal.project())
            self.assertEqual(await pg.question_journal.project(), await local.question_journal.project())
            self.assertEqual(await self.world.events(arm), sqlite.events(arm))
