import tempfile
import unittest

from app.g5.world import World, Decision, Conflict
from app.g5.question_journal import QuestionJournal, QUESTION_PROTOCOL
from test_g5_runtime import spec


class JournalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + "/world.sqlite"
        self.world = World(self.path)
        self.world.create("w", spec(), {"questions": QUESTION_PROTOCOL})
        self.journal = QuestionJournal(self.world, "w")

    def tearDown(self):
        self.world.close()
        self.tmp.cleanup()

    async def ask(self):
        return await self.journal.commit(expected_version=0, request_id="q", actor="security",
            decision=Decision("speak", "Ready?"),
            annotations=[{"kind": "question", "start": 0, "end": 6, "targets": ["sre"]}])

    async def test_restart_atomic_replay_and_idempotent_retry(self):
        event = await self.ask()
        first = await self.journal.project()
        self.assertEqual(await self.ask(), event)
        self.world.close()
        self.world = World(self.path)
        self.journal = QuestionJournal(self.world, "w")
        self.assertEqual(await self.journal.project(), first)
        qid = first["questions"][0]["id"]
        await self.journal.commit(expected_version=1, request_id="r", actor="sre",
            decision=Decision("speak", "Later."), annotations=[{"kind": "response", "start": 0,
            "end": 6, "question_id": qid, "status": "deferred"}])
        self.assertEqual((await self.journal.project())["questions"][0]["pending_targets"], ["sre"])
        self.assertEqual(len(self.world.events("w")), 2)

    async def test_invalid_annotation_never_commits_speech(self):
        with self.assertRaises(ValueError):
            await self.journal.commit(expected_version=0, request_id="bad", actor="security",
                decision=Decision("speak", "Ready?"), annotations=[{"kind": "question", "start": 0,
                "end": 6, "targets": ["invisible"]}])
        self.assertEqual(self.world.events("w"), [])

    async def test_stale_and_changed_retry_rejected(self):
        await self.ask()
        for rid in ("q", "new"):
            with self.assertRaises(Conflict):
                await self.journal.commit(expected_version=0, request_id=rid, actor="security",
                                         decision=Decision("speak", "Changed"), annotations=[])
        self.assertEqual(len(self.world.events("w")), 1)

    async def test_explicit_freeze_and_public_view_isolation(self):
        self.world.create("old", spec(), {})
        with self.assertRaises(ValueError):
            await QuestionJournal(self.world, "old").project()
        await self.ask()
        _, observed = self.world.observe("w", "sre")
        self.assertNotIn("question_annotations", str(observed))
        self.assertEqual(observed["observations"][0]["content"], "Ready?")
