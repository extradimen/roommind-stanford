import unittest

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.runtime import Runtime, Review
from app.g5.session_journal import SESSION_PROTOCOL
from app.g5.world import World, Decision
from test_g5_runtime import manifest, spec


class SessionAnnotator:
    specification = {"adapter": "offline-session-v1"}

    async def __call__(self, context, decision):
        assert "facts" not in context and "cognition" not in context
        return {"kind": "end_intent", "start": 0, "end": len(decision.content)}


class SessionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = World(":memory:")
        self.addCleanup(self.world.close)
        self.calls = []

    def runtime(self, annotator, arm="A", wrong_stop=False, policy_override=None,
                governance_override=None, question_annotator=None, session_specification=None, scheduler=None,
                allow_reopening=False):
        design = manifest()["design"]
        design["session_annotation"] = session_specification or {"adapter": "offline-session-v1"}
        if question_annotator is not None:
            design["question_annotation"] = question_annotator.specification
        if scheduler is not None:
            design["scheduling"] = scheduler.runtime_specification()
            for profile in design["arms"].values():
                profile["shared"]["base_scheduler_sha256"] = digest(design["scheduling"])
        if not wrong_stop:
            for profile in design["arms"].values():
                stop = {"max_steps": 4, "max_revisions": 1, "session": SESSION_PROTOCOL}
                if allow_reopening:
                    stop["reopening"] = "explicit-request-next-scheduled-role-v1"
                profile["shared"]["stopping_policy_sha256"] = digest(stop)
        frozen = freeze_design(design)

        async def policy(view, feedback):
            self.calls.append(view["actor"])
            return Decision("speak", "End.")

        async def cognition(view):
            return {}

        async def governance(view, decision):
            return Review(True)

        return Runtime(world=self.world, world_id=arm, spec=spec(), manifest=frozen,
            ordinal=next(a["ordinal"] for a in frozen["assignments"] if a["arm"] == arm),
            max_steps=4, policy=policy_override or policy, session_annotator=annotator,
            question_annotator=question_annotator, scheduler=scheduler, allow_reopening=allow_reopening,
            cognition=cognition if ARMS[arm]["cognition"] else None,
            governance=(governance_override or governance) if ARMS[arm]["governance"] else None)

    async def test_explicit_reopening_preserves_history_and_total_budget_four_arms(self):
        class Reopening(SessionAnnotator):
            async def __call__(self, context, decision):
                return {"kind": "reopen" if decision.content == "Reopen." else "end_intent",
                        "start": 0, "end": len(decision.content)}
        async def policy(view, feedback):
            return Decision("speak", "Reopen." if view.get("session_reopening") else "End.")
        for arm in ARMS:
            runtime = self.runtime(Reopening(), arm, policy_override=policy, allow_reopening=True)
            await runtime.step()
            await runtime.step()
            before = self.world.events(arm)
            self.assertEqual((await runtime.step())["status"], "session_closed")
            result = await runtime.step(reopen=True)
            self.assertEqual(result["event"]["payload"]["actor"], "security")
            self.assertEqual(self.world.events(arm)[:2], before)
            self.assertEqual((await runtime.session_journal.project())["episode"], 2)
            await runtime.step()
            self.assertEqual((await runtime.step())["status"], "cutoff")
            self.assertEqual(len(self.world.events(arm)), 4)

    async def test_reopening_requires_closed_enabled_and_candidate_consent(self):
        runtime = self.runtime(SessionAnnotator(), allow_reopening=True)
        with self.assertRaises(ValueError):
            await runtime.step(reopen=True)
        await runtime.step()
        await runtime.step()
        before = self.world.events("A")
        self.assertEqual((await runtime.step(reopen=True))["status"], "reopen_declined")
        self.assertEqual(self.world.events("A"), before)
        self.assertEqual((await runtime.session_journal.project())["status"], "closed")
        disabled = self.runtime(SessionAnnotator(), "B")
        with self.assertRaises(ValueError):
            await disabled.step(reopen=True)

    async def test_reopening_governance_exhaustion_and_switch_drift_do_not_publish(self):
        class Tracking(SessionAnnotator):
            def __init__(self):
                self.calls = 0
            async def __call__(self, context, decision):
                self.calls += 1
                return await super().__call__(context, decision)
        policies = []
        async def policy(view, feedback):
            policies.append((view["actor"], feedback))
            return Decision("speak", "Reopen." if view.get("session_reopening") else "End.")
        async def review(view, decision):
            return Review(not bool(view.get("session_reopening")), "Do not reopen without a valid reason")
        for arm in ("C", "D"):
            annotator = Tracking()
            runtime = self.runtime(annotator, arm, policy_override=policy, governance_override=review,
                                   allow_reopening=True)
            await runtime.step()
            await runtime.step()
            before = self.world.events(arm)
            self.assertEqual((await runtime.step(reopen=True))["status"], "reopen_declined")
            self.assertEqual([actor for actor, _ in policies[-2:]], ["security", "security"])
            self.assertTrue(policies[-1][1])
            self.assertEqual(annotator.calls, 2)
            self.assertEqual(self.world.events(arm), before)
            self.assertEqual((await runtime.session_journal.project())["status"], "closed")
            runtime.allow_reopening = False
            with self.assertRaises(ValueError):
                await runtime.step()
            self.assertEqual(self.world.events(arm), before)

    async def test_reopening_at_exhausted_budget_makes_no_calls(self):
        calls = []
        async def policy(view, feedback):
            calls.append(view["actor"])
            return Decision("wait") if len(calls) <= 2 else Decision("speak", "End.")
        runtime = self.runtime(SessionAnnotator(), policy_override=policy, allow_reopening=True)
        for _ in range(4):
            await runtime.step()
        self.assertEqual((await runtime.session_journal.project())["status"], "closed")
        before = self.world.attempts("A")
        self.assertEqual((await runtime.step(reopen=True))["status"], "cutoff")
        self.assertEqual(len(calls), 4)
        self.assertEqual(self.world.attempts("A"), before)

    async def test_priority_end_intent_cannot_replace_other_participant_consent(self):
        from app.g5.scheduling import QuestionScheduler
        class Questions:
            specification = {"adapter": "offline-pending-v1"}
            async def __call__(self, context, decision):
                return ([{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}]
                        if decision.content == "Ready?" else [])
        class Session(SessionAnnotator):
            async def __call__(self, context, decision):
                return None if decision.content == "Ready?" else await super().__call__(context, decision)
        async def policy(view, feedback):
            return Decision("speak", "Ready?" if not view["observations"] else "End.")
        for arm in ARMS:
            def build():
                return self.runtime(Session(), arm, policy_override=policy, question_annotator=Questions(),
                                    scheduler=QuestionScheduler(priority_enabled=True))
            runtime = build()
            await runtime.step()
            original = (await runtime.question_journal.project())["questions"]
            await runtime.step()  # Priority response opportunity belongs to sre.
            runtime = build()  # Reconstruct from committed selection and consent.
            await runtime.step()  # sre's base opportunity cannot stand for security.
            self.assertEqual((await runtime.session_journal.project())["status"], "open")
            await runtime.step()
            events = self.world.events(arm)
            self.assertEqual([e["payload"]["actor"] for e in events], ["security", "sre", "sre", "security"])
            self.assertEqual([e["payload"]["audit"]["scheduling"]["mode"] for e in events],
                             ["base", "priority", "base", "base"])
            self.assertEqual((await runtime.question_journal.project())["questions"], original)
            # Closed at the exact step cap is closure, not a fabricated task success.
            stopped = await runtime.step()
            self.assertEqual(stopped["status"], "session_closed")
            self.assertIsNone(stopped["task_completed"])

    async def test_model_receipts_null_and_closure_are_private_across_four_arms(self):
        import json
        from app.g5.model_policy import ModelBinding, Completion
        from app.g5.model_session import ModelSessionAnnotator
        for arm in ARMS:
            requests = []
            bodies = []
            async def transport(request):
                requests.append(request)
                body = '{"annotation":null}' if len(requests) == 1 else (
                    '{"annotation":{"kind":"end_intent","start":0,"end":4}}')
                bodies.append(body)
                return Completion(body, "ollama", "fixed", "offline", digest(request), "stop")
            adapter = ModelSessionAnnotator(ModelBinding("ollama", "fixed", "offline", 0.2, 512), transport)
            runtime = self.runtime(adapter, arm, session_specification=adapter.runtime_specification())
            for _ in range(3):
                await runtime.step()
            events = self.world.events(arm)
            self.assertIsNone(events[0]["payload"]["audit"]["session_annotation"])
            for event, request, body in zip(events, requests, bodies):
                evidence = event["payload"]["audit"]["session_annotation_evidence"]
                self.assertEqual(evidence["request_sha256"], digest(request))
                self.assertEqual(evidence["response_sha256"], digest(body))
                context = json.loads(request["messages"][1]["content"])["context"]
                self.assertEqual(set(context), {"actor", "participants", "observations", "session"})
            self.assertEqual((await runtime.step())["status"], "session_closed")
            self.assertEqual(len(requests), 3)
            for actor in runtime.roles:
                self.assertNotIn("session_annotation_evidence", str(self.world.observe(arm, actor)))

    async def test_model_receipt_failure_preserved_and_retry_commits_once(self):
        from app.g5.model_policy import ModelBinding, Completion
        from app.g5.model_session import ModelSessionAnnotator
        requests = []
        async def transport(request):
            requests.append(request)
            return Completion('{"annotation":null}', "ollama", "fixed", "offline",
                              "bad" if len(requests) == 1 else digest(request), "stop")
        adapter = ModelSessionAnnotator(ModelBinding("ollama", "fixed", "offline", 0.2, 512), transport)
        runtime = self.runtime(adapter, session_specification=adapter.runtime_specification())
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(self.world.events("A"), [])
        failed = self.world.attempts("A")[-1]
        self.assertEqual((failed["stage"], failed["status"]), ("session_annotation", "failed"))
        await runtime.step()
        self.assertEqual(len(self.world.events("A")), 1)
        self.assertIn(failed, self.world.attempts("A"))
        self.assertEqual(self.world.events("A")[0]["payload"]["audit"]["session_annotation_evidence"]
                         ["request_sha256"], digest(requests[1]))

    async def test_combined_queue_remains_pending_at_closed_session(self):
        class Questions:
            specification = {"adapter": "offline-pending-v1"}
            async def __call__(self, context, decision):
                if decision.content == "Ready?":
                    return [{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}]
                return []

        class Session(SessionAnnotator):
            async def __call__(self, context, decision):
                return None if decision.content == "Ready?" else await super().__call__(context, decision)

        async def policy(view, feedback):
            return Decision("speak", "Ready?" if not view["observations"] else "End.")

        for arm in ARMS:
            runtime = self.runtime(Session(), arm, policy_override=policy, question_annotator=Questions())
            await runtime.step()
            original = (await runtime.question_journal.project())["questions"]
            await runtime.step()
            await runtime.step()
            self.assertEqual((await runtime.step())["status"], "session_closed")
            self.assertEqual((await runtime.question_journal.project())["questions"], original)
            self.assertEqual(len(self.world.events(arm)), 3)

    async def test_revised_final_only_and_exhaustion_skip_session_annotation(self):
        class Tracking(SessionAnnotator):
            def __init__(self):
                self.seen = []
            async def __call__(self, context, decision):
                self.seen.append(decision.content)
                return await super().__call__(context, decision)

        async def policy(view, feedback):
            return Decision("speak", "End." if feedback else "Draft.")

        async def review(view, decision):
            return Review(decision.content == "End.", "Revise")

        for arm in ("C", "D"):
            annotator = Tracking()
            runtime = self.runtime(annotator, arm, policy_override=policy, governance_override=review)
            await runtime.step()
            self.assertEqual(annotator.seen, ["End."])
            self.assertEqual(self.world.events(arm)[0]["payload"]["decision"]["content"], "End.")

        async def reject(view, decision):
            return Review(False, "Revise")

        # Use a separate store to avoid changing any frozen world binding.
        self.world.close()
        self.world = World(":memory:")
        self.addCleanup(self.world.close)
        annotator = Tracking()
        runtime = self.runtime(annotator, "D", policy_override=policy, governance_override=reject)
        await runtime.step()
        self.assertEqual(annotator.seen, [])
        self.assertEqual(self.world.events("D")[0]["payload"]["decision"]["action"], "wait")
        self.assertEqual((await runtime.session_journal.project())["status"], "open")

    async def test_four_arms_stop_without_success_or_further_calls_and_reconstruct(self):
        for arm in ARMS:
            runtime = self.runtime(SessionAnnotator(), arm)
            await runtime.step()
            await runtime.step()
            events = self.world.events(arm)
            attempts = self.world.attempts(arm)
            calls = list(self.calls)
            runtime = self.runtime(SessionAnnotator(), arm)
            stopped = await runtime.step()
            self.assertEqual(stopped["status"], "session_closed")
            self.assertIsNone(stopped["task_completed"])
            self.assertEqual(self.calls, calls)
            self.assertEqual(self.world.events(arm), events)
            self.assertEqual(self.world.attempts(arm), attempts)
            self.assertEqual([e["payload"]["actor"] for e in events], ["security", "sre"])
            self.assertNotIn("session_annotation", str(self.world.observe(arm, "sre")))

    async def test_failed_annotation_no_publish_then_retry(self):
        class Broken(SessionAnnotator):
            async def __call__(self, context, decision):
                raise TimeoutError("scripted")
        runtime = self.runtime(Broken())
        with self.assertRaises(TimeoutError):
            await runtime.step()
        self.assertEqual(self.world.events("A"), [])
        self.assertEqual(self.world.attempts("A")[-1]["stage"], "session_annotation")
        self.assertEqual(self.world.attempts("A")[-1]["status"], "failed")
        await self.runtime(SessionAnnotator()).step()
        self.assertEqual(len(self.world.events("A")), 1)

    async def test_missing_drift_and_unbound_stopping_policy_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime(None)
        with self.assertRaises(ValueError):
            self.runtime(SessionAnnotator(), wrong_stop=True)
        annotator = SessionAnnotator()
        runtime = self.runtime(annotator)
        annotator.specification = {"adapter": "changed"}
        with self.assertRaises(ValueError):
            await runtime.step()
        self.assertEqual(self.world.events("A"), [])
