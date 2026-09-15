"""Opt-in local integration tests in freshly generated, disposable schemas.

G5_TEST_DSN must be supplied explicitly. Never uses application configuration.
"""
import asyncio
import os
import unittest
import uuid

from app.g5.postgres import PostgresWorld
from app.g5.runtime import Runtime
from app.g5.world import Conflict, Decision, World
from test_g5_runtime import spec, manifest


@unittest.skipUnless(os.environ.get("G5_TEST_DSN"), "G5_TEST_DSN not supplied")
class PostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.schema = "g5_test_" + uuid.uuid4().hex
        self.world = PostgresWorld(self.pool, self.schema)
        self.owned = False
        async with self.pool.acquire() as connection:
            await connection.execute(f"CREATE SCHEMA {self.schema}")
        self.owned = True
        await self.world.install()

    async def asyncTearDown(self):
        if self.owned:
            async with self.pool.acquire() as connection:
                # Only the unique schema successfully created by this test.
                await connection.execute(f"DROP SCHEMA {self.schema} CASCADE")
        await self.pool.close()

    async def runtime(self, policy, arm="A", cognition=None, governance=None):
        frozen = manifest()
        ordinal = next(r["ordinal"] for r in frozen["assignments"] if r["arm"] == arm)
        return await Runtime.open(world=self.world, world_id=arm, spec=spec(), manifest=frozen,
            ordinal=ordinal, policy=policy, max_steps=4, cognition=cognition, governance=governance)

    async def test_full_session_composition_four_arms_parity(self):
        await self.check_full_session_composition()

    async def test_full_reopening_four_arms_pool_reconnect_and_duplicate_rejection(self):
        import asyncpg
        from app.factorial_study import ARMS
        from test_g5_session_composed import session_options
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        for arm in ARMS:
            _, _, args = session_options(self.world, arm, closing=True, reopening=True)
            pg = await Runtime.open(**args)
            _, _, local_args = session_options(sqlite, arm, closing=True, reopening=True)
            local = Runtime(**local_args)
            for _ in range(4):
                self.assertEqual(await pg.step(), await local.step())
            before = await self.world.events(arm)
            questions = await pg.question_journal.project()
            await self.pool.close()
            self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
            self.world = PostgresWorld(self.pool, self.schema)
            harness, state, args = session_options(self.world, arm, closing=True, reopening=True)
            pg = await Runtime.open(**args)
            self.assertEqual((await pg.step())["status"], "session_closed")
            self.assertEqual(harness.calls, [])
            self.assertEqual(await pg.step(reopen=True), await local.step(reopen=True))
            committed = await self.world.events(arm)
            attempts = await self.world.attempts(arm)
            calls = len(state["requests"])
            with self.assertRaises(ValueError):
                await pg.step(reopen=True)
            self.assertEqual(await self.world.events(arm), committed)
            self.assertEqual(await self.world.attempts(arm), attempts)
            self.assertEqual(len(state["requests"]), calls)
            self.assertEqual(committed[:4], before)
            self.assertEqual((await pg.session_journal.project())["episode"], 2)
            self.assertEqual((await pg.question_journal.project())["questions"], questions["questions"])
            for _ in range(2):
                self.assertEqual(await pg.step(), await local.step())
            self.assertEqual(await pg.step(), await local.step())
            self.assertEqual((await pg.session_journal.project())["status"], "closed")
            self.assertEqual(await self.world.events(arm), sqlite.events(arm))
            self.assertEqual(await pg.session_journal.project(), await local.session_journal.project())
            for actor in pg.roles:
                self.assertEqual(await self.world.observe(arm, actor), sqlite.observe(arm, actor))

    async def test_full_session_closing_four_arms_and_reconnect(self):
        await self.check_full_session_composition(closing=True)

    async def check_full_session_composition(self, closing=False):
        from app.factorial_study import ARMS
        from test_g5_session_composed import session_options
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        for arm in ARMS:
            pg_harness, pg_state, pg_args = session_options(self.world, arm, closing=closing)
            local_harness, local_state, local_args = session_options(sqlite, arm, closing=closing)
            pg, local = await Runtime.open(**pg_args), Runtime(**local_args)
            for _ in range(4):
                self.assertEqual(await pg.step(), await local.step())
            self.assertEqual(pg_harness.calls, local_harness.calls)
            self.assertEqual(pg_state["requests"], local_state["requests"])
            self.assertEqual(await pg.session_journal.project(), await local.session_journal.project())
            self.assertEqual(await pg.question_journal.project(), await local.question_journal.project())
            for actor in pg.roles:
                self.assertEqual(await self.world.observe(arm, actor), sqlite.observe(arm, actor))
            before = len(pg_state["requests"])
            self.assertEqual((await pg.step())["status"], "session_closed" if closing else "cutoff")
            self.assertEqual(len(pg_state["requests"]), before)
            if closing:
                import asyncpg
                events = await self.world.events(arm)
                attempts = await self.world.attempts(arm)
                questions = await pg.question_journal.project()
                self.assertEqual(questions["questions"][0]["responses"]["sre"]["status"], "unanswered")
                await self.pool.close()
                self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
                self.world = PostgresWorld(self.pool, self.schema)
                rebuilt_harness, rebuilt_state, args = session_options(self.world, arm, closing=True)
                rebuilt = await Runtime.open(**args)
                result = await rebuilt.step()
                self.assertEqual(result["status"], "session_closed")
                self.assertIsNone(result["task_completed"])
                self.assertEqual(rebuilt_harness.calls, [])
                self.assertEqual(rebuilt_state["requests"], [])
                self.assertEqual(await self.world.events(arm), events)
                self.assertEqual(await self.world.attempts(arm), attempts)
                self.assertEqual(await rebuilt.question_journal.project(), questions)

    async def test_full_session_composition_failure_pool_reconnect(self):
        await self.check_full_session_failure()

    async def test_final_closing_annotation_failure_cannot_close_before_commit(self):
        await self.check_full_session_failure(closing=True)

    async def check_full_session_failure(self, closing=False):
        import asyncpg
        from test_g5_session_composed import session_options
        _, state, args = session_options(self.world, "D", closing=closing)
        runtime = await Runtime.open(**args)
        completed = 3 if closing else 1
        for _ in range(completed):
            await runtime.step()
        before = await self.world.events("D")
        session_before = await runtime.session_journal.project()
        questions_before = await runtime.question_journal.project()
        state["fail"] = True
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(await self.world.events("D"), before)
        self.assertEqual(await runtime.session_journal.project(), session_before)
        self.assertEqual(session_before["status"], "open")
        self.assertEqual(await runtime.question_journal.project(), questions_before)
        failure = (await self.world.attempts("D"))[-1]
        self.assertEqual((failure["stage"], failure["status"]), ("session_annotation", "failed"))
        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.schema)
        _, _, args = session_options(self.world, "D", closing=closing)
        runtime = await Runtime.open(**args)
        for _ in range(4 - completed):
            await runtime.step()
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        _, _, args = session_options(sqlite, "D", closing=closing)
        local = Runtime(**args)
        for _ in range(4):
            await local.step()
        self.assertEqual(await self.world.events("D"), sqlite.events("D"))
        self.assertEqual(await runtime.session_journal.project(), await local.session_journal.project())
        self.assertEqual(await runtime.question_journal.project(), await local.question_journal.project())
        self.assertIn(failure, await self.world.attempts("D"))
        if closing:
            stopped = await runtime.step()
            self.assertEqual(stopped["status"], "session_closed")
            self.assertIsNone(stopped["task_completed"])
            self.assertEqual((await runtime.question_journal.project())["questions"], questions_before["questions"])

    async def test_session_runtime_four_arms_parity_and_closed_reconnect(self):
        await self.check_session_runtime_parity()

    async def test_model_session_runtime_four_arms_receipts_and_reconnect(self):
        await self.check_session_runtime_parity(model_annotation=True)

    async def check_session_runtime_parity(self, model_annotation=False):
        import asyncpg
        from app.factorial_study import ARMS, digest, freeze_design
        from app.g5.runtime import Review
        from app.g5.session_journal import SESSION_PROTOCOL
        from test_g5_session_runtime import SessionAnnotator
        model_requests = []
        if model_annotation:
            from app.g5.model_session import ModelSessionAnnotator
            from app.g5.model_policy import ModelBinding, Completion
            async def transport(request):
                model_requests.append(request)
                return Completion('{"annotation":{"kind":"end_intent","start":0,"end":4}}',
                                  "ollama", "fixed", "offline", digest(request), "stop")
            annotator = ModelSessionAnnotator(ModelBinding("ollama", "fixed", "offline", 0.2, 512), transport)
            annotation_spec = annotator.runtime_specification()
        else:
            annotator = SessionAnnotator()
            annotation_spec = SessionAnnotator.specification
        design = manifest()["design"]
        design["session_annotation"] = annotation_spec
        for profile in design["arms"].values():
            profile["shared"]["stopping_policy_sha256"] = digest({
                "max_steps": 4, "max_revisions": 1, "session": SESSION_PROTOCOL})
        frozen = freeze_design(design)
        calls = []

        async def policy(view, feedback):
            calls.append(view["actor"])
            return Decision("speak", "End.")

        async def cognition(view):
            return {}

        async def governance(view, decision):
            return Review(True)

        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        for arm in ARMS:
            options = dict(world_id=arm, spec=spec(), manifest=frozen,
                ordinal=next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == arm),
                max_steps=4, policy=policy, session_annotator=annotator,
                cognition=cognition if ARMS[arm]["cognition"] else None,
                governance=governance if ARMS[arm]["governance"] else None)
            local = Runtime(world=sqlite, **options)
            pg = await Runtime.open(world=self.world, **options)
            for _ in range(2):
                self.assertEqual(await pg.step(), await local.step())
            self.assertEqual(await pg.session_journal.project(), await local.session_journal.project())
            before_events = await self.world.events(arm)
            before_attempts = await self.world.attempts(arm)
            before_calls = list(calls)
            before_model_calls = len(model_requests)
            if model_annotation:
                for event, request in zip(before_events, model_requests[-4::2]):
                    evidence = event["payload"]["audit"]["session_annotation_evidence"]
                    self.assertEqual(evidence["request_sha256"], digest(request))
                    self.assertEqual(evidence["specification"], annotation_spec)
            await self.pool.close()
            self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
            self.world = PostgresWorld(self.pool, self.schema)
            pg = await Runtime.open(world=self.world, **options)
            result = await pg.step()
            self.assertEqual(result, await local.step())
            self.assertEqual(result["status"], "session_closed")
            self.assertIsNone(result["task_completed"])
            self.assertEqual(calls, before_calls)
            self.assertEqual(len(model_requests), before_model_calls)
            self.assertEqual(await self.world.events(arm), before_events)
            self.assertEqual(await self.world.attempts(arm), before_attempts)
            for actor in ("security", "sre"):
                self.assertEqual(await self.world.observe(arm, actor), sqlite.observe(arm, actor))
                self.assertNotIn("session_annotation_evidence", str(await self.world.observe(arm, actor)))

    async def test_session_journal_parity_reconnect_and_reopen(self):
        import asyncpg
        from app.g5.session_journal import SessionJournal, SESSION_PROTOCOL
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        scenario = {"roles": ["a", "b"], "facts": {}, "actions": {}}
        binding = {"session": SESSION_PROTOCOL}
        sqlite.create("session", scenario, binding)
        await self.world.create("session", scenario, binding)
        pg, local = SessionJournal(self.world, "session"), SessionJournal(sqlite, "session")
        for i, actor in enumerate(("a", "b")):
            args = dict(expected_version=i, request_id=str(i), actor=actor, decision=Decision("speak", "End here."),
                        annotation={"kind": "end_intent", "start": 0, "end": 9})
            self.assertEqual(await pg.commit(**args), await local.commit(**args))
        closed = await pg.project()
        self.assertEqual(closed, await local.project())
        self.assertEqual(closed["status"], "closed")
        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.schema)
        pg = SessionJournal(self.world, "session")
        self.assertEqual(await pg.project(), closed)
        self.assertEqual(await pg.commit(**args), await local.commit(**args))
        args = dict(expected_version=2, request_id="reopen", actor="a", decision=Decision("speak", "New question."),
                    annotation={"kind": "reopen", "start": 0, "end": 13})
        self.assertEqual(await pg.commit(**args), await local.commit(**args))
        self.assertEqual(await pg.project(), await local.project())
        self.assertEqual((await pg.project())["episode"], 2)
        for actor in ("a", "b"):
            self.assertEqual(await self.world.observe("session", actor), sqlite.observe("session", actor))

    async def test_session_concurrent_reopening_and_invalid_commit_isolation(self):
        from app.g5.session_journal import SessionJournal, SESSION_PROTOCOL
        await self.world.create("session", {"roles": ["a", "b"], "facts": {}, "actions": {}},
                                {"session": SESSION_PROTOCOL})
        journal = SessionJournal(self.world, "session")
        for i, actor in enumerate(("a", "b")):
            await journal.commit(expected_version=i, request_id=str(i), actor=actor, decision=Decision("speak", "End."),
                                 annotation={"kind": "end_intent", "start": 0, "end": 4})
        before = await self.world.events("session")
        for annotation in (None, {"kind": "reopen", "start": 0, "end": 99}):
            with self.assertRaises(ValueError):
                await journal.commit(expected_version=2, request_id="bad", actor="a", decision=Decision("speak", "New."),
                                     annotation=annotation)
        self.assertEqual(await self.world.events("session"), before)
        async def reopen(key):
            return await journal.commit(expected_version=2, request_id=key, actor="a", decision=Decision("speak", "New."),
                                        annotation={"kind": "reopen", "start": 0, "end": 4})
        results = await asyncio.gather(reopen("one"), reopen("two"), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, Conflict) for r in results), 1)
        winner = next(r for r in results if isinstance(r, dict))
        first, second = await asyncio.gather(reopen(winner["request_id"]), reopen(winner["request_id"]))
        self.assertEqual(first, second)
        self.assertEqual(len(await self.world.events("session")), 3)
        self.assertEqual(len((await journal.project())["transitions"]), 2)

    async def test_combined_session_question_reconnect_and_atomic_validation(self):
        import asyncpg
        from app.g5.session_journal import SessionJournal, SESSION_PROTOCOL
        from app.g5.question_journal import QuestionJournal, QUESTION_PROTOCOL
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        scenario = {"roles": ["a", "b"], "facts": {}, "actions": {}}
        binding = {"session": SESSION_PROTOCOL, "questions": QUESTION_PROTOCOL}
        sqlite.create("combined", scenario, binding)
        await self.world.create("combined", scenario, binding)
        local, pg = SessionJournal(sqlite, "combined"), SessionJournal(self.world, "combined")
        args = dict(expected_version=0, request_id="q", actor="a", decision=Decision("speak", "Ready?"),
                    question_annotations=[{"kind": "question", "start": 0, "end": 6, "targets": ["b"]}])
        self.assertEqual(await pg.commit(**args), await local.commit(**args))
        original = await QuestionJournal(self.world, "combined").project()
        for i, actor in enumerate(("a", "b"), 1):
            args = dict(expected_version=i, request_id=str(i), actor=actor, decision=Decision("speak", "End."),
                        annotation={"kind": "end_intent", "start": 0, "end": 4}, question_annotations=[])
            self.assertEqual(await pg.commit(**args), await local.commit(**args))
        self.assertEqual((await pg.project())["status"], "closed")
        self.assertEqual((await QuestionJournal(self.world, "combined").project())["questions"], original["questions"])
        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.schema)
        pg = SessionJournal(self.world, "combined")
        self.assertEqual(await pg.project(), await local.project())
        before = await self.world.events("combined")
        args = dict(expected_version=3, request_id="reopen", actor="b", decision=Decision("speak", "Reopen. Later."),
                    annotation={"kind": "reopen", "start": 0, "end": 7}, question_annotations=[{
                        "kind": "response", "start": 8, "end": 14,
                        "question_id": original["questions"][0]["id"], "status": "deferred"}])
        for invalid in ({"annotation": None}, {"question_annotations": [{
                "kind": "response", "start": 8, "end": 14, "question_id": "unknown", "status": "deferred"}]}):
            with self.assertRaises(ValueError):
                await pg.commit(**{**args, **invalid})
            self.assertEqual(await self.world.events("combined"), before)
            self.assertEqual(await pg.project(), await local.project())
        result = await pg.commit(**args)
        self.assertEqual(result, await local.commit(**args))
        self.assertEqual(await pg.commit(**args), result)
        self.assertEqual(await self.world.events("combined"), sqlite.events("combined"))
        self.assertEqual(await pg.project(), await local.project())
        self.assertEqual((await pg.project())["episode"], 2)
        questions = await QuestionJournal(self.world, "combined").project()
        self.assertEqual(questions, await QuestionJournal(sqlite, "combined").project())
        self.assertEqual(questions["questions"][0]["responses"]["b"]["status"], "deferred")
        for actor in ("a", "b"):
            self.assertEqual(await self.world.observe("combined", actor), sqlite.observe("combined", actor))

    async def check_process_recovery(self, mode, code, committed, stage, scheduled=False):
        from pathlib import Path
        import sys
        from test_g5_process_recovery import POSTGRES_CHILD
        from test_g5_composed_runtime import Harness

        server = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join([str(server), str(server / "tests")])
        child = await asyncio.create_subprocess_exec(
            sys.executable, "-c", POSTGRES_CHILD, self.schema, mode,
            "scheduled" if scheduled else "legacy", env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=20)
        except BaseException:
            if child.returncode is None:
                child.kill()  # This test's owned client only, never the DB service.
                await child.wait()
            raise
        self.assertEqual(child.returncode, code, stderr.decode())
        self.assertEqual(stdout, b"")
        self.assertEqual(len(await self.world.events("D")), committed)
        journal = await self.world.attempts("D")
        self.assertEqual((journal[-1]["stage"], journal[-1]["status"]), (stage, "started"))
        def runtime_options(world):
            if scheduled:
                from test_g5_scheduled_runtime import options
                return options(world, "D")[1]
            return Harness().runtime_options(world, "D")
        resumed = await Runtime.open(**runtime_options(self.world))
        reference = World(":memory:")
        self.addCleanup(reference.close)
        uninterrupted = Runtime(**runtime_options(reference))
        for _ in range(4 - committed):
            await resumed.step()
        for _ in range(4):
            await uninterrupted.step()
        self.assertEqual(await self.world.events("D"), reference.events("D"))
        self.assertEqual(await resumed.question_journal.project(), await uninterrupted.question_journal.project())
        self.assertEqual((await self.world.attempts("D"))[:len(journal)], journal)
        for actor in spec()["roles"]:
            self.assertEqual(await self.world.observe("D", actor), reference.observe("D", actor))
        self.assertEqual((await resumed.step())["status"], "cutoff")
        if scheduled:
            selections = [e["payload"]["audit"]["scheduling"] for e in await self.world.events("D")]
            self.assertEqual([s["mode"] for s in selections], ["base", "priority", "base", "base"])
            self.assertEqual([s["actor"] for s in selections], ["security", "sre", "sre", "security"])

    async def test_scheduled_process_before_commit_retains_priority(self):
        await self.check_process_recovery("before_commit", 73, 1, "annotation", scheduled=True)

    async def test_scheduled_process_after_commit_does_not_repeat_priority(self):
        await self.check_process_recovery("after_commit", 74, 2, "commit", scheduled=True)

    async def test_scheduled_four_arms_switches_match_sqlite(self):
        from app.factorial_study import ARMS
        from test_g5_scheduled_runtime import options

        for enabled in (False, True):
            for arm in ARMS:
                with self.subTest(enabled=enabled, arm=arm):
                    sqlite = World(":memory:")
                    self.addCleanup(sqlite.close)
                    pg_harness, pg_args = options(self.world, arm, enabled)
                    local_harness, local_args = options(sqlite, arm, enabled)
                    world_id = arm + str(enabled)
                    pg_args["world_id"] = local_args["world_id"] = world_id
                    pg = await Runtime.open(**pg_args)
                    local = Runtime(**local_args)
                    for _ in range(4):
                        self.assertEqual(await pg.step(), await local.step())
                    self.assertEqual(pg_harness.calls, local_harness.calls)
                    self.assertEqual(await pg.question_journal.project(), await local.question_journal.project())
                    for actor in spec()["roles"]:
                        self.assertEqual(await self.world.observe(world_id, actor), sqlite.observe(world_id, actor))
                    self.assertEqual((await pg.step())["status"], "cutoff")

    async def test_process_exit_before_commit_recovers_same_turn(self):
        await self.check_process_recovery("before_commit", 73, 1, "annotation")

    async def test_process_exit_after_commit_does_not_duplicate_turn(self):
        await self.check_process_recovery("after_commit", 74, 2, "commit")

    async def test_composed_four_arms_match_sqlite_events_views_and_calls(self):
        from app.factorial_study import ARMS
        from test_g5_composed_runtime import Harness

        for arm, flags in ARMS.items():
            with self.subTest(arm=arm):
                pg_harness, sqlite_harness = Harness(), Harness()
                sqlite = World(":memory:")
                self.addCleanup(sqlite.close)
                pg_runtime = await Runtime.open(**pg_harness.runtime_options(self.world, arm))
                sqlite_runtime = sqlite_harness.runtime(sqlite, arm)
                for _ in range(4):
                    self.assertEqual(await pg_runtime.step(), await sqlite_runtime.step())
                    for actor in spec()["roles"]:
                        self.assertEqual(await self.world.observe(arm, actor), sqlite.observe(arm, actor))
                self.assertEqual(await pg_runtime.question_journal.project(),
                                 await sqlite_runtime.question_journal.project())
                self.assertEqual(pg_harness.calls, sqlite_harness.calls)
                kinds = [kind for kind, _ in pg_harness.calls]
                self.assertEqual("reflection" in kinds, flags["cognition"])
                self.assertEqual("audit" in kinds, flags["governance"])
                count = len(pg_harness.calls)
                self.assertEqual((await pg_runtime.step())["status"], "cutoff")
                self.assertEqual(len(pg_harness.calls), count)

    async def test_composed_revision_paths_match_sqlite_and_preserve_failed_attempts(self):
        from test_g5_composed_runtime import Harness

        for arm in ("C", "D"):
            for mode in ("revise", "exhaust", "fail_once"):
                with self.subTest(arm=arm, mode=mode):
                    world_id = arm + "-" + mode
                    pg_harness, local_harness = Harness(mode), Harness(mode)
                    sqlite = World(":memory:")
                    self.addCleanup(sqlite.close)
                    pg_options = pg_harness.runtime_options(self.world, arm)
                    local_options = local_harness.runtime_options(sqlite, arm)
                    pg_options["world_id"] = local_options["world_id"] = world_id
                    pg_runtime = await Runtime.open(**pg_options)
                    local_runtime = Runtime(**local_options)
                    if mode == "fail_once":
                        for runtime in (pg_runtime, local_runtime):
                            with self.assertRaises(TimeoutError):
                                await runtime.step()
                        self.assertEqual(await self.world.events(world_id), [])
                        failed = await self.world.attempts(world_id)
                        self.assertEqual((failed[-1]["stage"], failed[-1]["status"]), ("policy", "failed"))
                    result = await pg_runtime.step()
                    self.assertEqual(result, await local_runtime.step())
                    self.assertEqual(pg_harness.calls, local_harness.calls)
                    self.assertEqual(await pg_runtime.question_journal.project(),
                                     await local_runtime.question_journal.project())
                    for actor in spec()["roles"]:
                        self.assertEqual(await self.world.observe(world_id, actor), sqlite.observe(world_id, actor))
                    audit = result["event"]["payload"]["audit"]
                    self.assertEqual(len(audit["attempts"]), 2)
                    self.assertFalse(audit["attempts"][0]["review"]["allowed"])
                    self.assertEqual(audit["attempts"][1]["review"]["allowed"], mode != "exhaust")
                    public = (await self.world.observe(world_id, "sre"))[1]
                    self.assertNotIn("Bad draft", str(public))
                    if mode == "exhaust":
                        self.assertEqual(audit["outcome"], "unresolved_after_revisions")
                        self.assertEqual(public["observations"], [])
                        self.assertNotIn("annotation", [kind for kind, _ in pg_harness.calls])
                    if mode == "fail_once":
                        self.assertEqual((await self.world.attempts(world_id))[:len(failed)], failed)

    async def test_composed_failure_reconnect_preserves_state_and_retry_history(self):
        import asyncpg
        from test_g5_composed_runtime import Harness

        harness = Harness()
        runtime = await Runtime.open(**harness.runtime_options(self.world, "D"))
        await runtime.step()
        events = await self.world.events("D")
        observations = {actor: await self.world.observe("D", actor) for actor in spec()["roles"]}
        harness.fail_annotation = True
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(await self.world.events("D"), events)
        for actor, observation in observations.items():
            self.assertEqual(await self.world.observe("D", actor), observation)
        failed_attempts = await self.world.attempts("D")
        self.assertEqual(failed_attempts[-1]["stage"], "annotation")
        self.assertEqual(failed_attempts[-1]["status"], "failed")

        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.schema)
        resumed = await Runtime.open(**Harness().runtime_options(self.world, "D"))
        self.assertEqual(await self.world.attempts("D"), failed_attempts)
        for _ in range(3):
            await resumed.step()
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        reference = Harness().runtime(sqlite, "D")
        for _ in range(4):
            await reference.step()
        self.assertEqual(await self.world.events("D"), sqlite.events("D"))
        self.assertEqual(await resumed.question_journal.project(), await reference.question_journal.project())
        self.assertGreater(len(await self.world.attempts("D")), len(sqlite.attempts("D")))

    async def test_sqlite_postgres_event_and_visibility_parity(self):
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        sqlite.create("parity", spec(), {})
        await self.world.create("parity", spec(), {})
        for version, (actor, decision) in enumerate([
            ("sre", Decision("execute", operation="contain")),
            ("security", Decision("execute", operation="preserve")),
            ("sre", Decision("execute", operation="contain")),
            ("security", Decision("speak", "Rollback is complete.")),
        ]):
            args = dict(expected_version=version, request_id=str(version), actor=actor, decision=decision, audit={})
            self.assertEqual(sqlite.commit("parity", **args), await self.world.commit("parity", **args))
            for observer in spec()["roles"]:
                self.assertEqual(sqlite.observe("parity", observer), await self.world.observe("parity", observer))

    async def test_concurrent_writers_and_idempotent_duplicate(self):
        await self.world.create("race", spec(), {})

        async def write(key):
            return await self.world.commit("race", expected_version=0, request_id=key, actor="security",
                                           decision=Decision("execute", operation="preserve"), audit={})

        results = await asyncio.gather(write("one"), write("two"), return_exceptions=True)
        self.assertEqual(sum(isinstance(x, Conflict) for x in results), 1)
        winner = next(x for x in results if isinstance(x, dict))
        first, second = await asyncio.gather(write(winner["request_id"]), write(winner["request_id"]))
        self.assertEqual(first, second)
        self.assertEqual(len(await self.world.events("race")), 1)

    async def test_reconnect_continues_cursor_and_retains_receipt(self):
        import asyncpg

        async def policy(view, feedback):
            return Decision("execute", operation="preserve" if view["actor"] == "security" else "contain")

        runtime = await self.runtime(policy)
        first = await runtime.step()
        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.schema)
        runtime = await self.runtime(policy)
        second = await runtime.step()
        self.assertEqual(second["event"]["payload"]["actor"], "sre")
        events = await self.world.events("A")
        self.assertEqual(events[0], first["event"])
        self.assertEqual(len(events), 2)
        self.assertTrue((await self.world.facts("A"))["contained"]["value"])
        self.assertEqual(len(await self.world.attempts("A")), 8)

    async def test_failed_call_persists_without_secret_and_retry_keeps_cursor(self):
        async def broken(view, feedback):
            raise TimeoutError("Authorization: secret-token, private-provider-url")

        runtime = await self.runtime(broken)
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(await self.world.events("A"), [])
        records = await self.world.attempts("A")
        self.assertEqual([r["status"] for r in records], ["started", "failed"])
        self.assertEqual(records[-1]["error_code"], "timeout")
        self.assertNotIn("secret-token", str(records))

        async def recovered(view, feedback):
            self.assertEqual(view["actor"], "security")
            return Decision("wait")

        runtime = await self.runtime(recovered)
        await runtime.step()
        self.assertEqual(len(await self.world.events("A")), 1)
        self.assertEqual((await self.world.attempts("A"))[:2], records)

    async def test_immutable_tables_and_atomic_rollback(self):
        import asyncpg
        await self.world.create("immutable", spec(), {})
        async with self.pool.acquire() as connection:
            for statement in (f"UPDATE {self.schema}.worlds SET spec='{{}}'",
                              f"TRUNCATE {self.schema}.attempts"):
                with self.assertRaises(asyncpg.PostgresError):
                    await connection.execute(statement)
            await connection.execute(f"""CREATE TRIGGER inject_failure BEFORE INSERT ON {self.schema}.events
                FOR EACH ROW EXECUTE FUNCTION {self.schema}.reject_mutation()""")
        args = dict(expected_version=0, request_id="retry", actor="security",
                    decision=Decision("execute", operation="preserve"), audit={})
        with self.assertRaises(asyncpg.PostgresError):
            await self.world.commit("immutable", **args)
        self.assertEqual(await self.world.events("immutable"), [])
        self.assertFalse((await self.world.facts("immutable"))["preserved"]["value"])
        async with self.pool.acquire() as connection:
            await connection.execute(f"DROP TRIGGER inject_failure ON {self.schema}.events")
        await self.world.commit("immutable", **args)
        await self.world.install()
        self.assertTrue((await self.world.facts("immutable"))["preserved"]["value"])

    async def test_all_arms_use_same_postgres_loop(self):
        from app.factorial_study import ARMS
        from app.g5.runtime import Review
        for arm, switches in ARMS.items():
            calls = []

            async def cognition(view):
                calls.append("cognition")
                return {"owner": view["actor"]}

            async def governance(view, decision):
                calls.append("governance")
                return Review(True)

            async def policy(view, feedback):
                if view["actor"] == "security":
                    return Decision("speak", "New evidence")
                self.assertEqual(view["observations"][0]["content"], "New evidence")
                self.assertNotIn("secret", view["facts"])
                return Decision("wait")

            runtime = await self.runtime(policy, arm,
                cognition if switches["cognition"] else None,
                governance if switches["governance"] else None)
            await runtime.step()
            await runtime.step()
            self.assertEqual(calls.count("cognition"), 2 * switches["cognition"])
            self.assertEqual(calls.count("governance"), 2 * switches["governance"])

    async def question_journal(self):
        from app.g5.question_journal import QuestionJournal, QUESTION_PROTOCOL
        await self.world.create("questions", spec(), {"questions": QUESTION_PROTOCOL})
        return QuestionJournal(self.world, "questions")

    async def test_model_question_runtime_postgres_evidence_and_response(self):
        import json
        from app.factorial_study import digest, freeze_design
        from app.g5.model_policy import ModelBinding, Completion
        from app.g5.model_questions import ModelQuestionAnnotator
        binding = ModelBinding("ollama", "offline-fixed", "mock", 0.2, 512)
        async def transport(request):
            context = json.loads(request["messages"][1]["content"])["context"]
            if context["actor"] == "security":
                items = [{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}]
            else:
                items = [{"kind": "response", "start": 0, "end": 6, "status": "deferred",
                          "question_id": context["questions"]["questions"][0]["id"]}]
            return Completion(json.dumps({"annotations": items}), "ollama", "offline-fixed", "mock", digest(request), "stop")
        annotator = ModelQuestionAnnotator(binding, transport)
        design = manifest()["design"]
        design["question_annotation"] = annotator.runtime_specification()
        frozen = freeze_design(design)
        async def policy(view, feedback):
            return Decision("speak", "Ready?" if view["actor"] == "security" else "Later.")
        runtime = await Runtime.open(world=self.world, world_id="model-queue", spec=spec(), manifest=frozen,
            ordinal=next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == "A"),
            max_steps=4, policy=policy, question_annotator=annotator)
        await runtime.step()
        await runtime.step()
        events = await self.world.events("model-queue")
        self.assertTrue(all(e["payload"]["audit"]["question_annotation_evidence"]["request_sha256"] for e in events))
        projection = await runtime.question_journal.project()
        self.assertEqual(projection["questions"][0]["responses"]["sre"]["status"], "deferred")
        _, observed = await self.world.observe("model-queue", "sre")
        self.assertNotIn("question_annotation_evidence", str(observed))

    def question_args(self, request_id="q"):
        return dict(expected_version=0, request_id=request_id, actor="security",
                    decision=Decision("speak", "Ready?"),
                    annotations=[{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}])

    async def test_question_journal_parity_reconnect_and_response(self):
        import asyncpg
        from app.g5.question_journal import QuestionJournal, QUESTION_PROTOCOL
        journal = await self.question_journal()
        sqlite = World(":memory:")
        self.addCleanup(sqlite.close)
        sqlite.create("questions", spec(), {"questions": QUESTION_PROTOCOL})
        reference = QuestionJournal(sqlite, "questions")
        event = await journal.commit(**self.question_args())
        self.assertEqual(event, await reference.commit(**self.question_args()))
        before = await journal.project()
        self.assertEqual(before, await reference.project())
        await self.pool.close()
        self.pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=4)
        self.world = PostgresWorld(self.pool, self.schema)
        journal = QuestionJournal(self.world, "questions")
        self.assertEqual(await journal.project(), before)
        args = dict(expected_version=1, request_id="answer", actor="sre", decision=Decision("speak", "Later."),
                    annotations=[{"kind": "response", "start": 0, "end": 6,
                                  "question_id": before["questions"][0]["id"], "status": "deferred"}])
        self.assertEqual(await journal.commit(**args), await reference.commit(**args))
        self.assertEqual(await journal.project(), await reference.project())
        self.assertEqual((await journal.project())["questions"][0]["pending_targets"], ["sre"])

    async def test_question_journal_concurrent_and_identical_retry(self):
        journal = await self.question_journal()
        results = await asyncio.gather(journal.commit(**self.question_args("one")),
                                       journal.commit(**self.question_args("two")), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, Conflict) for r in results), 1)
        winner = next(r for r in results if isinstance(r, dict))
        retries = await asyncio.gather(*(journal.commit(**self.question_args(winner["request_id"])) for _ in range(2)))
        self.assertEqual(retries, [winner, winner])
        self.assertEqual(len((await journal.project())["questions"]), 1)
        self.assertEqual(len(await self.world.events("questions")), 1)

    async def test_question_journal_database_failure_rolls_back_both(self):
        import asyncpg
        journal = await self.question_journal()
        async with self.pool.acquire() as connection:
            await connection.execute(f"""CREATE TRIGGER inject_question_failure BEFORE INSERT ON {self.schema}.events
                FOR EACH ROW EXECUTE FUNCTION {self.schema}.reject_mutation()""")
        with self.assertRaises(asyncpg.PostgresError):
            await journal.commit(**self.question_args())
        self.assertEqual(await self.world.events("questions"), [])
        self.assertEqual((await journal.project())["questions"], [])
        async with self.pool.acquire() as connection:
            await connection.execute(f"DROP TRIGGER inject_question_failure ON {self.schema}.events")
        await journal.commit(**self.question_args())
        self.assertEqual(len((await journal.project())["questions"]), 1)


if __name__ == "__main__":
    unittest.main()
