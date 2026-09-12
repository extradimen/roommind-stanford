"""Optional public-consent session projection, independent of task success.

Pure prototype: not a runtime stop rule. Annotations need semantic calibration.
Each participant speaks only for their own willingness to end this session.
"""
from copy import deepcopy
from app.factorial_study import digest
from app.g5.questions import require


def project_session(scope, participants, observations, annotations):
    require(isinstance(scope, str) and bool(scope), "Explicit session scope required")
    require(isinstance(participants, list) and bool(participants)
            and all(isinstance(p, str) and p for p in participants)
            and len(set(participants)) == len(participants), "Invalid participants")
    require(isinstance(observations, list) and isinstance(annotations, dict), "Invalid lifecycle inputs")
    seen, consent, transitions = set(), {}, []
    status, episode = "open", 1
    for event in observations:
        require(isinstance(event, dict) and isinstance(event.get("event_id"), str)
                and bool(event["event_id"]) and event["event_id"] not in seen, "Invalid event identity")
        eid = event["event_id"]
        seen.add(eid)
        item = annotations.get(eid)
        if item is None:
            if event.get("kind") == "claim":
                require(status == "open", "Closed session needs an explicit reopening event")
                # Fresh discussion invalidates stale willingness from all roles.
                consent = {}
            continue
        require(event.get("kind") == "claim" and event.get("actor") in participants
                and isinstance(event.get("content"), str), "Lifecycle requires participant public speech")
        require(isinstance(item, dict) and set(item) == {"kind", "start", "end"}, "Invalid lifecycle annotation")
        kind, start, end = item["kind"], item["start"], item["end"]
        require(kind in ("end_intent", "continue", "reopen") and type(start) is int and type(end) is int
                and 0 <= start < end <= len(event["content"]), "Invalid lifecycle span or kind")
        evidence = {"event_id": eid, "actor": event["actor"], "quote": event["content"][start:end]}
        if kind == "reopen":
            require(status == "closed", "Only a closed session can reopen")
            episode += 1
            status, consent = "open", {}
            transitions.append({"kind": "reopened", "episode": episode, **evidence})
        else:
            require(status == "open", "Closed session requires reopen")
            if kind == "continue":
                consent = {}
            else:
                consent[event["actor"]] = evidence
                if set(consent) == set(participants):
                    status = "closed"
                    transitions.append({"kind": "closed", "episode": episode,
                                        "event_id": eid, "consent": deepcopy(consent)})
    require(set(annotations) <= seen, "Lifecycle annotations reference invisible events")
    return {"schema": "g5-public-session-consent-v1", "scope": scope, "status": status,
            "episode": episode, "consent": consent, "transitions": transitions,
            "task_completed": None, "input_sha256": digest([scope, participants, observations, annotations])}
