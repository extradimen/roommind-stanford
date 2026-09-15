import copy
import unittest

from app.g5.questions import project_questions, question_id


def event(eid, actor, content):
    return {"event_id": eid, "kind": "claim", "actor": actor, "content": content}


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.events = [event("q", "a", "B and C, ready?"), event("b", "b", "Not yet"), event("c", "c", "I decline")]
        self.qid = question_id("world", "q", 0, 15)
        self.annotations = {"q": [{"kind": "question", "start": 0, "end": 15, "targets": ["b", "c"]}],
                            "b": [self.response("deferred", 7)], "c": [self.response("declined", 9)]}

    def response(self, status, end):
        return {"kind": "response", "start": 0, "end": end, "question_id": self.qid, "status": status}

    def project(self):
        return project_questions("world", ["a", "b", "c"], self.events, self.annotations)

    def test_multi_target_defer_and_decline(self):
        q = self.project()["questions"][0]
        self.assertEqual(q["pending_targets"], ["b"])
        self.assertEqual(q["responses"]["c"]["status"], "declined")
        self.assertFalse(q["all_targets_responded"])
        self.events.append(event("b2", "b", "Now ready"))
        self.annotations["b2"] = [self.response("answered", 9)]
        q = self.project()["questions"][0]
        self.assertTrue(q["all_targets_responded"])
        self.assertEqual(len(q["responses"]["b"]["history"]), 2)
        self.assertNotIn("task_completed", q)

    def test_replay_deterministic_and_inputs_unchanged(self):
        before = copy.deepcopy([self.events, self.annotations])
        self.assertEqual(self.project(), self.project())
        self.assertEqual([self.events, self.annotations], before)

    def test_impersonation_and_terminal_overwrite_rejected(self):
        self.events.append(event("x", "a", "Answer"))
        self.annotations["x"] = [self.response("answered", 6)]
        with self.assertRaises(ValueError):
            self.project()
        self.events[-1]["actor"] = "c"
        with self.assertRaises(ValueError):
            self.project()

    def test_invisible_future_and_bad_span_rejected(self):
        self.annotations["hidden"] = []
        with self.assertRaises(ValueError):
            self.project()
        del self.annotations["hidden"]
        self.annotations["b"][0]["question_id"] = "future"
        with self.assertRaises(ValueError):
            self.project()
        self.annotations["b"][0]["question_id"] = self.qid
        self.annotations["q"][0]["end"] = 999
        with self.assertRaises(ValueError):
            self.project()

    def test_scope_isolation_and_no_implicit_question_detection(self):
        self.assertNotEqual(question_id("other", "q", 0, 15), self.qid)
        with self.assertRaises(ValueError):
            project_questions("other", ["a", "b", "c"], self.events, self.annotations)
        self.assertEqual(project_questions("world", ["a", "b", "c"], self.events, {})["questions"], [])
