"""Private, source-bound hierarchical intentions, never a task-success oracle."""
from copy import deepcopy
import json
from app.g5.world import canonical

PROTOCOL = "g5-hierarchical-intentions-v1"
DELTA_PROTOCOL = "g5-hierarchical-intention-updates-v1"
FIELDS = {"id", "parent", "depends_on", "actor", "intent", "text", "operation",
          "source_ids", "status", "status_source_ids"}
STATUSES = {"planned", "active", "deferred", "cancelled", "completed"}


def require(value, message):
    if not value:
        raise ValueError(message)


def pin_sources(selected, memory, previous_plan, facts, *, active_only=False, extra_ids=()):
    """Retain only cited plan evidence beyond top-k, not the entire memory store."""
    selected = deepcopy(selected)
    needed = set(extra_ids)
    if previous_plan:
        for step in previous_plan["proposal"]["steps"]:
            if active_only and step["status"] in {"completed", "cancelled"}:
                continue
            needed.update(step["source_ids"])
            needed.update(step["status_source_ids"])
    known = {row["id"] for row in selected["retrieved"]}
    for node in memory["nodes"]:
        if node["id"] in needed and node["id"] not in known:
            current = facts.get(node["fact_key"]) if node["kind"] == "fact" else None
            row = {**deepcopy(node), "retrieval_reason": "persistent_plan_source"}
            row["historical_fact"] = bool(node["kind"] == "fact" and (
                current is None or current["source"] != node["source"]
                or canonical(json.loads(node["text"]).get(node["fact_key"])) != canonical(current["value"])))
            selected["retrieved"].append(row)
    return selected


def projection(previous_plan, max_active_tasks):
    """Model view is bounded by open work, while the durable plan is never erased."""
    if previous_plan is None:
        return None
    rows = previous_plan["proposal"]["steps"]
    active = [r for r in rows if r["status"] not in {"completed", "cancelled"}]
    require(len(active) <= max_active_tasks, "Active plan capacity exceeded; do not truncate unresolved work")
    dependencies = {key for r in active for key in r["depends_on"]}
    terminal = [r for r in rows if r["status"] in {"completed", "cancelled"}]
    return {"id": previous_plan["id"], "kind": "intention", "proposal": {
        "goal": previous_plan["proposal"]["goal"], "steps": deepcopy(active)},
        "terminal_dependencies": [{"id": r["id"], "status": r["status"]} for r in terminal if r["id"] in dependencies],
        "terminal_counts": {status: sum(r["status"] == status for r in terminal) for status in ("completed", "cancelled")}}


def expand_updates(update, previous_plan, available):
    require(isinstance(update, dict) and set(update) == {"goal", "updates"}
            and isinstance(update["updates"], list), "Invalid incremental plan envelope")
    rows = {r["id"]: deepcopy(r) for r in previous_plan["proposal"]["steps"]} if previous_plan else {}
    seen = set()
    for row in update["updates"]:
        require(isinstance(row, dict) and set(row) == FIELDS and isinstance(row["id"], str), "Invalid task update")
        require(row["id"] not in seen, "Duplicate task update")
        seen.add(row["id"])
        for field in ("source_ids", "status_source_ids"):
            require(isinstance(row[field], list) and all(isinstance(x, str) for x in row[field])
                    and set(row[field]) <= available.keys(), "Updated task cites evidence outside supplied context")
        rows[row["id"]] = deepcopy(row)
    return {"goal": update["goal"], "steps": list(rows.values())}


def validate(proposal, previous_plan, actor, operations, available):
    require(isinstance(proposal, dict) and set(proposal) == {"goal", "steps"}, "Invalid hierarchical plan")
    require(isinstance(proposal["goal"], str) and proposal["goal"].strip(), "Plan goal required")
    require(isinstance(proposal["steps"], list) and proposal["steps"], "Plan steps required")
    rows = {}
    for row in proposal["steps"]:
        require(isinstance(row, dict) and set(row) == FIELDS, "Invalid hierarchical step fields")
        key = row["id"]
        require(isinstance(key, str) and key.strip() == key and 0 < len(key) <= 128 and key not in rows,
                "Stable unique task IDs required")
        rows[key] = row
        require(row["actor"] == actor, "Cannot plan for another actor")
        require(isinstance(row["intent"], str) and row["intent"] in {"goal", "ask", "speak", "execute", "wait", "defer", "decline"}, "Invalid intention")
        require(isinstance(row["text"], str) and row["text"].strip(), "Task text required")
        require(isinstance(row["status"], str) and row["status"] in STATUSES, "Invalid task status")
        require(isinstance(row["operation"], str), "Invalid operation")
        require(row["operation"] in operations if row["intent"] == "execute" else row["operation"] == "",
                "Unavailable operation or non-action execution")
        for field in ("source_ids", "status_source_ids", "depends_on"):
            ids = row[field]
            require(isinstance(ids, list) and all(isinstance(x, str) for x in ids)
                    and len(ids) == len(set(ids)), "Invalid or duplicate references")
            if field != "depends_on":
                require(set(ids) <= available.keys(), "Unavailable plan evidence")
        require(bool(row["source_ids"]) or (not available and row["intent"] in {"goal", "ask", "wait", "defer", "decline"}),
                "Plan source required")
    previous = {r["id"]: r for r in previous_plan["proposal"]["steps"]} if previous_plan else {}
    require(previous.keys() <= rows.keys(), "Do not erase existing intentions; cancel or defer them explicitly")
    children = {key: [] for key in rows}
    edges = {}
    for key, row in rows.items():
        parent = row["parent"]
        require(parent is None or (isinstance(parent, str) and parent in rows and rows[parent]["intent"] == "goal"),
                "Parent must be an existing goal")
        if parent is not None:
            children[parent].append(key)
        require(set(row["depends_on"]) <= rows.keys(), "Unknown prerequisite")
        edges[key] = [*row["depends_on"], *([parent] if parent is not None else [])]
        old = previous.get(key)
        if old:
            require(all(row[f] == old[f] for f in ("actor", "intent", "text", "operation", "parent", "depends_on", "source_ids")),
                    "Task identity cannot silently change; retain old task and create a new one")
            require(old["status"] not in {"completed", "cancelled"} or row == old,
                    "Terminal task is immutable; use a new explicitly sourced task")
        if row["intent"] != "goal" and (not old or row != old) and row["status"] != "planned":
            require(bool(row["status_source_ids"]), "Task transition needs observed evidence")
        if row["intent"] != "goal" and row["status"] in {"active", "completed"}:
            require(all(rows[d]["status"] == "completed" for d in row["depends_on"]), "Unmet plan prerequisite")
        if row["intent"] != "goal" and row["status"] == "completed":
            require(old is not None, "Do not retroactively create completed intentions")
            origins = previous_plan.get("task_origins", {}).get(key)
            require(isinstance(origins, list), "Task creation evidence boundary missing")
            supported = False
            for source_id in row["status_source_ids"]:
                if source_id in origins:
                    continue
                node = available[source_id]
                if node["kind"] not in {"claim", "simulation_receipt"}:
                    continue
                observation = json.loads(node["text"])
                if row["intent"] == "execute":
                    receipt = observation.get("receipt", {})
                    supported |= (node["kind"] == "simulation_receipt" and observation.get("actor") == actor
                        and receipt.get("operation") == row["operation"] and receipt.get("status") == "success")
                elif row["intent"] in {"ask", "speak", "decline"}:
                    # Completion means this utterance occurred, not that an issue was resolved.
                    supported |= (node["kind"] == "claim" and observation.get("actor") == actor
                                  and observation.get("content") == row["text"])
            require(supported, "Completion requires own matching public utterance or successful simulation receipt")
    visiting, done = set(), set()
    def visit(key):
        require(key not in visiting, "Cyclic hierarchy or prerequisites")
        if key in done:
            return
        visiting.add(key)
        for dependency in edges[key]:
            visit(dependency)
        visiting.remove(key)
        done.add(key)
    for key in rows:
        visit(key)
    for key, row in rows.items():
        if row["intent"] == "goal":
            require(bool(children[key]), "Goal requires child intentions")
            if key in previous and previous[key]["status"] in {"completed", "cancelled"}:
                require(set(children[key]) == {r["id"] for r in previous.values() if r["parent"] == key},
                        "Do not add work beneath a terminal goal")
            statuses = [rows[k]["status"] for k in children[key]]
            expected = ("completed" if all(s == "completed" for s in statuses) else
                "cancelled" if all(s in {"completed", "cancelled"} for s in statuses) else
                "active" if "active" in statuses else "deferred" if "deferred" in statuses else "planned")
            require(row["status"] == expected, "Goal status must agree with children, not imply world success")
    return deepcopy(proposal)
