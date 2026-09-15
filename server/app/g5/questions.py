"""Pure question projection from ordered visible claims and explicit annotations.

Annotations require public text spans, but semantic correctness is not inferred
here. No scheduler, database writes, completion claims or model calls.
"""
from copy import deepcopy

from app.factorial_study import digest


def require(ok, message):
    if not ok:
        raise ValueError(message)


def question_id(scope, event_id, start, end):
    return digest({"scope": scope, "event_id": event_id, "start": start, "end": end})


def project_questions(scope, participants, observations, annotations):
    require(isinstance(scope, str) and bool(scope), "Explicit question scope required")
    require(isinstance(participants, list) and bool(participants)
            and all(isinstance(p, str) and p for p in participants)
            and len(set(participants)) == len(participants), "Invalid participants")
    require(isinstance(observations, list) and isinstance(annotations, dict), "Invalid question inputs")
    questions, seen = {}, set()
    for event in observations:
        require(isinstance(event, dict) and isinstance(event.get("event_id"), str)
                and event["event_id"] and event["event_id"] not in seen, "Invalid or duplicate visible event")
        eid = event["event_id"]
        seen.add(eid)
        items = annotations.get(eid, [])
        require(isinstance(items, list), "Invalid event annotations")
        if not items:
            continue
        require(event.get("kind") == "claim" and event.get("actor") in participants
                and isinstance(event.get("content"), str), "Only visible speech may change question state")
        actor, content = event["actor"], event["content"]
        changed = set()
        for item in items:
            require(isinstance(item, dict), "Invalid question annotation")
            kind = item.get("kind")
            fields = {"kind", "start", "end", "targets"} if kind == "question" else {"kind", "start", "end", "question_id", "status"}
            require(kind in ("question", "response") and set(item) == fields, "Invalid annotation fields")
            start, end = item["start"], item["end"]
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(content), "Invalid public speech span")
            if kind == "question":
                targets = item["targets"]
                require(isinstance(targets, list) and bool(targets) and all(isinstance(t, str) for t in targets)
                        and len(set(targets)) == len(targets) and set(targets) <= set(participants)
                        and actor not in targets, "Invalid question targets")
                qid = question_id(scope, eid, start, end)
                require(qid not in questions, "Duplicate question span")
                questions[qid] = {"id": qid, "asker": actor, "event_id": eid,
                                  "quote": content[start:end], "targets": deepcopy(targets),
                                  "responses": {t: {"status": "unanswered", "history": []} for t in targets}}
            else:
                qid, status = item["question_id"], item["status"]
                require(isinstance(qid, str) and qid in questions, "Unknown or future question")
                q = questions[qid]
                require(q["event_id"] != eid and actor in q["responses"], "Response must follow question and belong to target")
                require(status in ("answered", "deferred", "declined"), "Invalid response status")
                require(qid not in changed, "Conflicting responses within one event")
                changed.add(qid)
                response = q["responses"][actor]
                require(response["status"] in ("unanswered", "deferred"), "Terminal response cannot be overwritten")
                response["history"].append({"event_id": eid, "quote": content[start:end], "status": status})
                response["status"] = status
    require(set(annotations) <= seen, "Annotations reference invisible events")
    result = list(questions.values())
    for q in result:
        q["pending_targets"] = [t for t in q["targets"] if q["responses"][t]["status"] in ("unanswered", "deferred")]
        q["all_targets_responded"] = not q["pending_targets"]
    return {"schema": "g5-question-projection-v1", "scope": scope, "questions": result,
            "input_sha256": digest([scope, participants, observations, annotations])}
