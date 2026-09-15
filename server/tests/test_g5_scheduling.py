import copy
import unittest

from app.g5.scheduling import QuestionScheduler


def projection():
    return {"schema": "g5-question-projection-v1", "questions": [{"id": "q1", "targets": ["c", "b"],
        "responses": {t: {"status": "unanswered"} for t in ("c", "b")}}]}


class SchedulingTests(unittest.TestCase):
    roles = ["a", "b", "c"]

    def test_disabled_ignores_projection_and_preserves_round_robin(self):
        scheduler, history = QuestionScheduler(), []
        for _ in range(7):
            history.append(scheduler.select(self.roles, None, history))
        self.assertEqual([s["actor"] for s in history], ["a", "b", "c", "a", "b", "c", "a"])

    def test_ordered_targets_bounded_priority_and_base_cursor_not_skipped(self):
        scheduler, history = QuestionScheduler(priority_enabled=True), []
        state = projection()
        original = copy.deepcopy(state)
        for _ in range(7):
            history.append(scheduler.select(self.roles, state, history))
        self.assertEqual([s["actor"] for s in history], ["c", "a", "b", "b", "c", "a", "b"])
        self.assertEqual([s["mode"] for s in history[:4]], ["priority", "base", "priority", "base"])
        self.assertEqual(state, original)

    def test_deferred_and_terminal_are_not_forced_to_answer(self):
        for status in ("deferred", "answered", "declined"):
            state = projection()
            for response in state["questions"][0]["responses"].values():
                response["status"] = status
            self.assertEqual(QuestionScheduler(priority_enabled=True).select(self.roles, state, [])["mode"], "base")

    def test_replay_and_uncommitted_retry_do_not_consume_opportunity(self):
        scheduler = QuestionScheduler(priority_enabled=True)
        state, history = projection(), []
        first = scheduler.select(self.roles, state, history)
        self.assertEqual(first, scheduler.select(self.roles, state, history))
        history.append(first)
        self.assertEqual(scheduler.select(self.roles, state, history),
                         QuestionScheduler(priority_enabled=True).select(self.roles, state, copy.deepcopy(history)))

    def test_invalid_bound_cursor_and_duplicate_priority_rejected(self):
        for value in (0, -1, True):
            with self.assertRaises(ValueError):
                QuestionScheduler(max_priority_streak=value)
        scheduler = QuestionScheduler(priority_enabled=True, max_priority_streak=2)
        first = scheduler.select(self.roles, projection(), [])
        with self.assertRaises(ValueError):
            scheduler.select(self.roles, projection(), [first, first])
        with self.assertRaises(ValueError):
            scheduler.select(self.roles, projection(), [{**first, "base_index": 8}])
        state = projection()
        state["questions"][0]["targets"] = ["unknown"]
        with self.assertRaises(ValueError):
            scheduler.select(self.roles, state, [])
