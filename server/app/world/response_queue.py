"""Persistent public response obligations; no model or speech-guard dependency."""
from copy import deepcopy

KEY = "response_queue"


class ResponseQueue:
    def __init__(self, state):
        self.data = deepcopy(state.get(KEY) or {"schema": "response-queue-v1", "entries": []})
        if self.data.get("schema") != "response-queue-v1":
            raise ValueError("Unknown response queue schema")

    def request(self, request_id, source_actor, targets, *, first=False):
        entries = self.data["entries"]
        old = [row for row in entries if row["request_id"] == request_id]
        targets = list(dict.fromkeys(targets))
        if old:
            if [row["target"] for row in old] != targets or any(row["source"] != source_actor for row in old):
                raise ValueError("Response request identity changed")
            return
        if first:
            for row in entries:
                if row["source"] == source_actor and row["target"] in targets and row["status"] in {"pending", "blocked"}:
                    row.update(status="superseded", superseded_by=request_id)
        rows = [{"request_id": request_id, "source": source_actor, "target": target,
                 "status": "pending", "answer": None} for target in targets]
        if first:
            entries[0:0] = rows
        else:
            entries.extend(rows)

    def pending(self):
        return list(dict.fromkeys(row["target"] for row in self.data["entries"]
                                 if row["status"] in {"pending", "blocked"}))

    def can_respond(self, actor):
        pending = self.pending()
        return not pending or pending[0] == actor

    def answered(self, actor, message_reference):
        if not self.can_respond(actor):
            raise ValueError("Response owner mismatch")
        for row in self.data["entries"]:
            if row["target"] == actor and row["status"] in {"pending", "blocked"}:
                row.update(status="answered", answer=message_reference)
                break

    def blocked(self, actor):
        for row in self.data["entries"]:
            if row["target"] == actor and row["status"] in {"pending", "blocked"}:
                row["status"] = "blocked"
                break

    def close(self):
        for row in self.data["entries"]:
            if row["status"] in {"pending", "blocked"}:
                row["status"] = "closed_unanswered"

    def save(self, state):
        state[KEY] = deepcopy(self.data)
        state["_pending_responses"] = self.pending()
