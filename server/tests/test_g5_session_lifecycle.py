import copy
import unittest
from app.g5.session_lifecycle import project_session


def event(eid, actor, text="We disagree; let's end here."):
    return {"event_id": eid, "actor": actor, "kind": "claim", "content": text}


def mark(kind="end_intent"):
    return {"kind": kind, "start": 0, "end": 3}


class SessionLifecycleTests(unittest.TestCase):
    def test_each_role_must_consent_but_closure_does_not_mean_task_success(self):
        events = [event("1", "a"), event("2", "a")]
        annotations = {"1": mark(), "2": mark()}
        self.assertEqual(project_session("s", ["a", "b"], events, annotations)["status"], "open")
        events.append(event("3", "b"))
        annotations["3"] = mark()
        state = project_session("s", ["a", "b"], events, annotations)
        self.assertEqual(state["status"], "closed")
        self.assertIsNone(state["task_completed"])
        self.assertEqual(set(state["transitions"][0]["consent"]), {"a", "b"})

    def test_fresh_discussion_and_continue_invalidate_stale_consent(self):
        events = [event("1", "a"), event("2", "b"), event("3", "b")]
        for middle in (None, mark("continue")):
            annotations = {"1": mark(), "3": mark()}
            if middle:
                annotations["2"] = middle
            state = project_session("s", ["a", "b"], events, annotations)
            self.assertEqual(state["status"], "open")
            self.assertEqual(set(state["consent"]), {"b"})

    def test_explicit_reopen_preserves_history_and_resets_consent(self):
        events = [event("1", "a"), event("2", "b"), event("3", "a", "New evidence; reopen discussion.")]
        annotations = {"1": mark(), "2": mark(), "3": mark("reopen")}
        original = copy.deepcopy([events, annotations])
        state = project_session("s", ["a", "b"], events, annotations)
        self.assertEqual((state["status"], state["episode"], state["consent"]), ("open", 2, {}))
        self.assertEqual([t["kind"] for t in state["transitions"]], ["closed", "reopened"])
        self.assertEqual(state, project_session("s", ["a", "b"], events, annotations))
        self.assertEqual([events, annotations], original)

    def test_invalid_sources_impersonation_and_unmarked_post_close_speech_fail(self):
        for events, annotations in [
            ([event("1", "a")], {"missing": mark()}),
            ([event("1", "outsider")], {"1": mark()}),
            ([event("1", "a")], {"1": {**mark(), "actor": "b"}}),
            ([event("1", "a")], {"1": mark("reopen")}),
            ([event("1", "a")], {"1": {**mark(), "end": 1000}}),
            ([event("1", "a"), event("2", "b"), event("3", "a")], {"1": mark(), "2": mark()}),
        ]:
            with self.assertRaises(ValueError):
                project_session("s", ["a", "b"], events, annotations)
