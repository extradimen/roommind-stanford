"""Opt-in pure opportunity selection; never turns an opportunity into an answer.

Runtime optionally freezes this policy and persists selection with the event.
History must contain only committed selections.
"""
from app.g5.questions import require


class QuestionScheduler:
    def __init__(self, *, priority_enabled=False, max_priority_streak=1):
        require(type(priority_enabled) is bool, "Explicit priority switch required")
        require(type(max_priority_streak) is int and max_priority_streak > 0, "Invalid priority bound")
        self.enabled = priority_enabled
        self.limit = max_priority_streak

    def runtime_specification(self):
        return {"scheduler": "g5-bounded-question-opportunities-v1", "priority_enabled": self.enabled,
                "max_priority_streak": self.limit, "base_cursor": "base-opportunities-only",
                "priority_per_question_target": 1, "automatic_answer": False}

    def select(self, participants, projection, history):
        require(isinstance(participants, list) and bool(participants)
                and all(isinstance(p, str) and p for p in participants)
                and len(set(participants)) == len(participants), "Invalid participants")
        require(isinstance(history, list), "Invalid scheduling history")
        base, streak, offered = 0, 0, set()
        for item in history:
            require(isinstance(item, dict) and set(item) == {"actor", "mode", "question_id", "base_index"},
                    "Invalid committed selection")
            require(type(item["base_index"]) is int and item["base_index"] == base
                    and item["actor"] in participants, "Invalid selection cursor or actor")
            if item["mode"] == "base":
                require(item["actor"] == participants[base % len(participants)] and item["question_id"] is None,
                        "Invalid base opportunity")
                base, streak = base + 1, 0
            else:
                qid = item["question_id"]
                require(item["mode"] == "priority" and self.enabled and streak < self.limit
                        and isinstance(qid, str) and bool(qid), "Invalid priority opportunity")
                key = (qid, item["actor"])
                require(key not in offered, "Duplicate priority opportunity")
                offered.add(key)
                streak += 1
        # Disabled policy never inspects question annotations.
        if self.enabled and streak < self.limit:
            require(isinstance(projection, dict) and projection.get("schema") == "g5-question-projection-v1"
                    and isinstance(projection.get("questions"), list), "Validated question projection required")
            candidates, seen = [], set()
            for question in projection["questions"]:
                require(isinstance(question, dict), "Invalid question")
                qid, targets, responses = question.get("id"), question.get("targets"), question.get("responses")
                require(isinstance(qid, str) and bool(qid) and qid not in seen, "Invalid question ID")
                seen.add(qid)
                require(isinstance(targets, list) and bool(targets)
                        and all(isinstance(t, str) and t in participants for t in targets)
                        and len(set(targets)) == len(targets) and isinstance(responses, dict)
                        and set(responses) == set(targets), "Invalid target ownership")
                for target in targets:
                    response = responses[target]
                    require(isinstance(response, dict) and response.get("status") in
                            ("unanswered", "deferred", "answered", "declined"), "Invalid response state")
                    # Deferred is still pending but is not an invitation to nag.
                    if response["status"] == "unanswered" and (qid, target) not in offered:
                        candidates.append((qid, target))
            if candidates:
                qid, target = candidates[0]
                return {"actor": target, "mode": "priority", "question_id": qid, "base_index": base}
        return {"actor": participants[base % len(participants)], "mode": "base",
                "question_id": None, "base_index": base}
