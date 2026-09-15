import tempfile
from pathlib import Path
import unittest

from app.g5.session_journal import SESSION_PROTOCOL, SessionJournal
from app.g5.world import World, Decision, Conflict


class SessionJournalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "session.sqlite")
        self.world = World(self.path)
        self.addCleanup(lambda: self.world.close())
        self.world.create("s", {"roles": ["a", "b"], "facts": {}, "actions": {}}, {"session": SESSION_PROTOCOL})
        self.journal = SessionJournal(self.world, "s")

    async def close_session(self):
        results = []
        for i, actor in enumerate(("a", "b")):
            results.append(await self.journal.commit(expected_version=i, request_id=str(i), actor=actor,
                decision=Decision("speak", "End here."), annotation={"kind": "end_intent", "start": 0, "end": 9}))
        return results

    async def combined(self):
        from app.g5.question_journal import QuestionJournal, QUESTION_PROTOCOL
        self.world.create("combined", {"roles": ["a", "b"], "facts": {}, "actions": {}},
                          {"session": SESSION_PROTOCOL, "questions": QUESTION_PROTOCOL})
        return SessionJournal(self.world, "combined"), QuestionJournal(self.world, "combined")

    async def test_combined_closure_and_reopen_keep_pending_question(self):
        session, questions = await self.combined()
        await session.commit(expected_version=0, request_id="q", actor="a", decision=Decision("speak", "Ready?"),
                             question_annotations=[{"kind": "question", "start": 0, "end": 6, "targets": ["b"]}])
        original = (await questions.project())["questions"]
        for i, actor in enumerate(("a", "b"), 1):
            await session.commit(expected_version=i, request_id=str(i), actor=actor, decision=Decision("speak", "End."),
                                 annotation={"kind": "end_intent", "start": 0, "end": 4}, question_annotations=[])
        self.assertEqual((await session.project())["status"], "closed")
        self.assertEqual((await questions.project())["questions"], original)
        args = dict(expected_version=3, request_id="reopen", actor="b", decision=Decision("speak", "Reopen. Later."),
                    annotation={"kind": "reopen", "start": 0, "end": 7}, question_annotations=[{
                        "kind": "response", "start": 8, "end": 14, "question_id": original[0]["id"], "status": "deferred"}])
        result = await session.commit(**args)
        self.assertEqual(await session.commit(**args), result)
        self.assertEqual((await session.project())["episode"], 2)
        self.assertEqual((await questions.project())["questions"][0]["responses"]["b"]["status"], "deferred")

    async def test_either_invalid_projection_rejects_entire_combined_event(self):
        session, _ = await self.combined()
        valid_question = [{"kind": "question", "start": 0, "end": 6, "targets": ["b"]}]
        for annotation, items in (({"kind": "reopen", "start": 0, "end": 6}, valid_question),
                                  ({"kind": "end_intent", "start": 0, "end": 6},
                                   [{"kind": "question", "start": 0, "end": 6, "targets": ["unknown"]}])):
            with self.assertRaises(ValueError):
                await session.commit(expected_version=0, request_id="bad", actor="a", decision=Decision("speak", "Ready?"),
                                     annotation=annotation, question_annotations=items)
        with self.assertRaises(ValueError):
            await session.commit(expected_version=0, request_id="omitted", actor="a", decision=Decision("wait"))
        self.assertEqual(self.world.events("combined"), [])

    async def test_reopen_database_and_session_preserves_history_and_idempotency(self):
        events = await self.close_session()
        self.world.close()
        self.world = World(self.path)
        self.journal = SessionJournal(self.world, "s")
        self.assertEqual((await self.journal.project())["status"], "closed")
        repeated = await self.journal.commit(expected_version=1, request_id="1", actor="b",
            decision=Decision("speak", "End here."), annotation={"kind": "end_intent", "start": 0, "end": 9})
        self.assertEqual(repeated, events[1])
        await self.journal.commit(expected_version=2, request_id="reopen", actor="a",
            decision=Decision("speak", "Reopen: new question."), annotation={"kind": "reopen", "start": 0, "end": 20})
        state = await self.journal.project()
        self.assertEqual((state["status"], state["episode"]), ("open", 2))
        self.assertIsNone(state["task_completed"])
        self.assertEqual(self.world.events("s")[:2], events)
        self.assertNotIn("session_annotation", str(self.world.observe("s", "b")))

    async def test_invalid_or_stale_reopening_does_not_commit(self):
        await self.close_session()
        before = self.world.events("s")
        for decision, annotation in ((Decision("wait"), None),
                                     (Decision("speak", "Talk"), None),
                                     (Decision("speak", "Talk"), {"kind": "reopen", "start": 0, "end": 99})):
            with self.assertRaises(ValueError):
                await self.journal.commit(expected_version=2, request_id="bad", actor="a",
                                          decision=decision, annotation=annotation)
        with self.assertRaises(Conflict):
            await self.journal.commit(expected_version=1, request_id="stale", actor="a", decision=Decision("wait"))
        self.assertEqual(self.world.events("s"), before)

    async def test_protocol_required_and_reserved_audit_rejected(self):
        self.world.create("off", {"roles": ["a"], "facts": {}, "actions": {}}, {})
        with self.assertRaises(ValueError):
            await SessionJournal(self.world, "off").project()
        with self.assertRaises(ValueError):
            await self.journal.commit(expected_version=0, request_id="x", actor="a", decision=Decision("wait"),
                                      audit={"session_annotation": None})
