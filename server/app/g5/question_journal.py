"""Opt-in atomic question annotations on the existing world event journal."""
from copy import deepcopy
import inspect

from app.factorial_study import digest
from app.g5.questions import project_questions
from app.g5.world import Conflict

QUESTION_PROTOCOL = {"schema": "g5-question-journal-v1", "projection": "g5-question-projection-v1",
                     "scheduling": "unchanged", "automatic_completion": False}


async def invoke(store, method, *args, **kwargs):
    result = getattr(store, method)(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


def replay(scope, participants, events):
    observations, annotations = [], {}
    for event in events:
        payload = event["payload"]
        items = payload["audit"].get("question_annotations", [])
        if payload["decision"]["action"] != "speak":
            if items:
                raise ValueError("Non-speech event has question annotations")
            continue
        observations.append({"event_id": event["event_id"], "kind": "claim",
                             "actor": payload["actor"], "content": payload["decision"]["content"]})
        annotations[event["event_id"]] = deepcopy(items)
    return project_questions(scope, participants, observations, annotations)


class QuestionJournal:
    def __init__(self, store, world_id):
        self.store, self.world_id = store, world_id

    async def _definition(self):
        spec, binding = await invoke(self.store, "definition", self.world_id)
        if binding.get("questions") != QUESTION_PROTOCOL:
            raise ValueError("Question protocol must be explicitly frozen in world binding")
        return spec, digest([self.world_id, binding])

    async def project(self):
        spec, scope = await self._definition()
        events = await invoke(self.store, "events", self.world_id)
        return replay(scope, spec["roles"], events)

    async def commit(self, *, expected_version, request_id, actor, decision, annotations, audit=None):
        spec, scope = await self._definition()
        if not isinstance(annotations, list) or (audit is not None and not isinstance(audit, dict)):
            raise ValueError("Invalid annotation commit")
        combined = deepcopy(audit or {})
        if "question_annotations" in combined:
            raise ValueError("Annotations must use explicit argument")
        combined["question_annotations"] = deepcopy(annotations)
        events = await invoke(self.store, "events", self.world_id)
        # Existing store resolves identical retries before its version check.
        if not any(e["request_id"] == request_id for e in events):
            if len(events) != expected_version:
                raise Conflict("World changed before question annotation")
            decision.validate()
            preview = {"event_id": "pending:" + digest([request_id, len(events)]),
                       "payload": {"actor": actor, "decision": {"action": decision.action,
                                   "content": decision.content, "operation": decision.operation}, "audit": combined}}
            replay(scope, spec["roles"], [*events, preview])
        return await invoke(self.store, "commit", self.world_id, expected_version=expected_version,
                            request_id=request_id, actor=actor, decision=decision, audit=combined)
