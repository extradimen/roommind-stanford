"""Explicit session-consent protocol on the atomic world log; not a Runtime hook."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.question_journal import invoke, QUESTION_PROTOCOL, replay as replay_questions
from app.g5.session_lifecycle import project_session
from app.g5.world import Conflict

SESSION_PROTOCOL = {"schema": "g5-session-journal-v1", "projection": "g5-public-session-consent-v1",
                    "closure": "all-participants-end-intent", "reopen": "participant-public-span",
                    "task_success": "not-inferred"}


def replay(scope, participants, events):
    observations, annotations = [], {}
    for event in events:
        payload = event["payload"]
        annotation = payload["audit"].get("session_annotation")
        speech = payload["decision"]["action"] == "speak"
        if not speech and annotation is not None:
            raise ValueError("Session annotation requires speech")
        observations.append({"event_id": event["event_id"], "kind": "claim" if speech else "action",
                             "actor": payload["actor"], "content": payload["decision"]["content"]})
        if annotation is not None:
            annotations[event["event_id"]] = deepcopy(annotation)
    return project_session(scope, participants, observations, annotations)


class SessionJournal:
    def __init__(self, store, world_id):
        self.store, self.world_id = store, world_id

    async def _definition(self):
        spec, binding = await invoke(self.store, "definition", self.world_id)
        if binding.get("session") != SESSION_PROTOCOL:
            raise ValueError("Session protocol must be explicitly frozen")
        return spec, digest([self.world_id, binding])

    async def project(self):
        spec, scope = await self._definition()
        return replay(scope, spec["roles"], await invoke(self.store, "events", self.world_id))

    async def commit(self, *, expected_version, request_id, actor, decision, annotation=None, audit=None,
                     question_annotations=None, reopen_request=None):
        spec, scope = await self._definition()
        _, binding = await invoke(self.store, "definition", self.world_id)
        questions_enabled = "questions" in binding
        if questions_enabled:
            if binding["questions"] != QUESTION_PROTOCOL or not isinstance(question_annotations, list):
                raise ValueError("Frozen question protocol and explicit annotations required")
        elif question_annotations is not None:
            raise ValueError("Question annotations require frozen protocol")
        if (annotation is not None and not isinstance(annotation, dict)) or (audit is not None and not isinstance(audit, dict)):
            raise ValueError("Invalid session commit")
        combined = deepcopy(audit or {})
        if "session_annotation" in combined or "question_annotations" in combined:
            raise ValueError("Use explicit annotation argument")
        combined["session_annotation"] = deepcopy(annotation)
        if questions_enabled:
            combined["question_annotations"] = deepcopy(question_annotations)
        events = await invoke(self.store, "events", self.world_id)
        if not any(e["request_id"] == request_id for e in events):
            if len(events) != expected_version:
                raise Conflict("World changed before session annotation")
            decision.validate()
            state = replay(scope, spec["roles"], events)
            if state["status"] == "closed" and (annotation or {}).get("kind") != "reopen":
                raise ValueError("Closed session requires explicit reopening")
            preview = {"event_id": "pending:" + digest([request_id, len(events)]), "payload": {
                "actor": actor, "decision": {"action": decision.action, "content": decision.content,
                                              "operation": decision.operation}, "audit": combined}}
            replay(scope, spec["roles"], [*events, preview])
            if questions_enabled:
                replay_questions(scope, spec["roles"], [*events, preview])
        return await invoke(self.store, "commit", self.world_id, expected_version=expected_version,
                            request_id=request_id, actor=actor, decision=decision, audit=combined,
                            **({"reopen_request": reopen_request} if reopen_request is not None else {}))
