"""Durable local reference world with append-only, versioned simulated actions.

SQLite is the offline reference adapter, not a replacement for the production
Postgres store. No network/tool side effects occur here. Speech never changes
world facts; only the frozen scenario and registered executor effects do.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
import json
import sqlite3
from typing import Any

from app.factorial_study import digest


# Shared engine contract, not the inputs of any one scenario. Scenario inputs
# have their own snapshot hash so a factorial panel can contain different worlds.
WORLD_CONTRACT_SHA256 = digest({"schema": "g5-local-world-v1",
    "truth_sources": ["scenario", "successful_registered_simulation_effect"],
    "visibility": "public_or_registered_observers", "speech": "claim_not_world_mutation"})


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


class Conflict(ValueError):
    """The world changed after the actor observed it; do not publish stale work."""


@dataclass(frozen=True)
class Decision:
    action: str
    content: str = ""
    operation: str = ""

    def validate(self) -> None:
        if self.action not in ("speak", "wait", "execute"):
            raise ValueError("Unknown actor action")
        if not isinstance(self.content, str) or not isinstance(self.operation, str):
            raise ValueError("Decision fields must be strings")
        if self.action == "speak" and (not self.content.strip() or self.operation):
            raise ValueError("Speech must contain text, not an executor operation")
        if self.action == "execute" and (not self.operation or self.content):
            raise ValueError("Execute only a registered operation; no invented result prose")
        if self.action == "wait" and (self.content or self.operation):
            raise ValueError("Wait has no public speech or effects")


def validate_spec(spec: dict) -> None:
    if not isinstance(spec, dict) or set(spec) != {"roles", "facts", "actions"}:
        raise ValueError("Invalid world specification")
    roles = spec["roles"]
    if (not isinstance(roles, list) or not roles
            or not all(isinstance(x, str) and x and x == x.strip() for x in roles)
            or len(set(roles)) != len(roles)):
        raise ValueError("Roles must be unique nonempty IDs")

    def visibility(value):
        if value is not None and (not isinstance(value, list) or not value
                or not all(isinstance(x, str) and x in roles for x in value)
                or len(set(value)) != len(value)):
            raise ValueError("Visibility must be public (null) or registered observers")

    if not isinstance(spec["facts"], dict) or not isinstance(spec["actions"], dict):
        raise ValueError("Facts and actions must be mappings")
    for key, fact in spec["facts"].items():
        if (not isinstance(key, str) or not key or not isinstance(fact, dict)
                or set(fact) != {"value", "visible_to", "disclosable"}
                or type(fact["disclosable"]) is not bool):
            raise ValueError("Invalid fact definition")
        visibility(fact["visible_to"])
        if fact["visible_to"] is None and not fact["disclosable"]:
            raise ValueError("Already public facts cannot be marked non-disclosable")
        canonical(fact["value"])
    for name, action in spec["actions"].items():
        if (not isinstance(name, str) or not name or not isinstance(action, dict)
                or set(action) != {"actors", "requires", "effects", "outcome", "visible_to"}):
            raise ValueError("Invalid action definition")
        actors = action["actors"]
        if (not isinstance(actors, list) or not actors
                or not all(isinstance(x, str) and x in roles for x in actors)
                or len(set(actors)) != len(actors)):
            raise ValueError("Invalid action authority")
        visibility(action["visible_to"])
        if action["visible_to"] is not None and not set(actors) <= set(action["visible_to"]):
            raise ValueError("Executors must see their own receipt")
        if action["outcome"] not in ("success", "failed"):
            raise ValueError("Invalid configured outcome")
        for field in ("requires", "effects"):
            if not isinstance(action[field], dict) or not set(action[field]) <= set(spec["facts"]):
                raise ValueError("Action refers to undefined facts")
            canonical(action[field])
        # Receipt effects must not accidentally declassify private facts.
        for key in action["effects"]:
            if spec["facts"][key]["visible_to"] != action["visible_to"]:
                raise ValueError("Effect and receipt visibility must match")


def resolve_payload(spec, facts, actor, decision, audit):
    """Shared deterministic execution for SQLite and PostgreSQL adapters."""
    decision.validate()
    if actor not in spec["roles"]:
        raise ValueError("Unregistered actor")
    if not isinstance(audit, dict) or ("cognition_state" in audit
                                      and not isinstance(audit["cognition_state"], dict)):
        raise ValueError("Audit and cognition state must be JSON objects")
    receipt, visibility = None, None
    if decision.action == "execute":
        action = spec["actions"].get(decision.operation)
        status, reason, effects = "blocked", "not_authorized_or_unknown", {}
        visibility = [actor]
        if action and actor in action["actors"]:
            visibility = action["visible_to"]
            if any(canonical(facts[key]["value"]) != canonical(value)
                   for key, value in action["requires"].items()):
                reason = "prerequisites_not_met"
            else:
                status = action["outcome"]
                reason = "executed_in_simulation" if status == "success" else "configured_failure"
                if status == "success":
                    effects = action["effects"]
        receipt = {"operation": decision.operation, "status": status, "reason": reason,
                   "effects": effects, "scope": "simulation_only"}
    return deepcopy({"actor": actor, "decision": asdict(decision), "audit": audit,
                     "receipt": receipt, "visible_to": visibility})


class World:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS g5_worlds (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, binding TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS g5_events (
                world_id TEXT NOT NULL REFERENCES g5_worlds(id), seq INTEGER NOT NULL,
                request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
                previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(world_id, seq), UNIQUE(world_id, request_id));
            CREATE TABLE IF NOT EXISTS g5_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                world_id TEXT NOT NULL REFERENCES g5_worlds(id), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS g5_reopening (
                world_id TEXT NOT NULL REFERENCES g5_worlds(id), request_id TEXT NOT NULL,
                phase TEXT NOT NULL CHECK(phase IN ('input','result')), payload TEXT NOT NULL,
                PRIMARY KEY(world_id, request_id, phase));
            CREATE TABLE IF NOT EXISTS g5_freezes (
                world_id TEXT PRIMARY KEY REFERENCES g5_worlds(id), payload TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS g5_freezes_no_update BEFORE UPDATE ON g5_freezes
                BEGIN SELECT RAISE(ABORT, 'dialogue seals are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_freezes_no_delete BEFORE DELETE ON g5_freezes
                BEGIN SELECT RAISE(ABORT, 'dialogue seals are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_reopening_no_update BEFORE UPDATE ON g5_reopening
                BEGIN SELECT RAISE(ABORT, 'reopening receipts are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_reopening_no_delete BEFORE DELETE ON g5_reopening
                BEGIN SELECT RAISE(ABORT, 'reopening receipts are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_attempts_no_update BEFORE UPDATE ON g5_attempts
                BEGIN SELECT RAISE(ABORT, 'attempts are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_attempts_no_delete BEFORE DELETE ON g5_attempts
                BEGIN SELECT RAISE(ABORT, 'attempts are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_events_no_update BEFORE UPDATE ON g5_events
                BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_events_no_delete BEFORE DELETE ON g5_events
                BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS g5_worlds_no_update BEFORE UPDATE ON g5_worlds
                BEGIN SELECT RAISE(ABORT, 'world specification is frozen'); END;
            CREATE TRIGGER IF NOT EXISTS g5_worlds_no_delete BEFORE DELETE ON g5_worlds
                BEGIN SELECT RAISE(ABORT, 'world specification is frozen'); END;
        """)

    def close(self):
        self.db.close()

    def record_attempt(self, world_id: str, record: dict) -> None:
        from app.g5.attempts import validate_record
        validate_record(record)
        self.db.execute("INSERT INTO g5_attempts(world_id, payload) VALUES (?, ?)",
                        (world_id, canonical(record)))

    def attempts(self, world_id: str) -> list[dict]:
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT payload FROM g5_attempts WHERE world_id=? ORDER BY id", (world_id,))]

    def export_source(self, world_id):
        from app.g5.artifacts import source_bundle
        self.db.execute("BEGIN")
        try:
            spec, binding = self.definition(world_id)
            rows = {}
            for request_id, phase, payload in self.db.execute(
                    "SELECT request_id,phase,payload FROM g5_reopening WHERE world_id=? ORDER BY request_id", (world_id,)):
                rows.setdefault(request_id, {})[phase] = json.loads(payload)
            reopening = [{"request": row["input"], "result": row.get("result")} for row in rows.values()]
            return source_bundle(world_id, spec, binding, self.events(world_id), self.attempts(world_id),
                                 reopening, self.frozen(world_id))
        finally:
            self.db.execute("ROLLBACK")

    def frozen(self, world_id):
        from app.g5.freezing import make_freeze
        row = self.db.execute("SELECT payload FROM g5_freezes WHERE world_id=?", (world_id,)).fetchone()
        if row is None:
            self.definition(world_id)
            return None
        spec, binding = self.definition(world_id)
        seal = json.loads(row[0])
        if seal != make_freeze(Snapshot(world_id, spec, binding, self.events(world_id))):
            raise ValueError("Dialogue seal integrity failure")
        return seal

    def freeze(self, world_id):
        from app.g5.freezing import make_freeze
        self.db.execute("BEGIN IMMEDIATE")
        try:
            seal = self.frozen(world_id)
            if seal is None:
                spec, binding = self.definition(world_id)
                seal = make_freeze(Snapshot(world_id, spec, binding, self.events(world_id)))
                self.db.execute("INSERT INTO g5_freezes VALUES (?,?)", (world_id, canonical(seal)))
            self.db.execute("COMMIT")
            return seal
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def _reopening_check(self, world_id, request):
        from app.g5.reopening import inspect, validate
        validate(request)
        rows = dict(self.db.execute("SELECT phase,payload FROM g5_reopening "
                                    "WHERE world_id=? AND request_id=?", (world_id, request["id"])))
        spec, binding = self.definition(world_id)
        snapshot = Snapshot(world_id, spec, binding, self.events(world_id))
        original = json.loads(rows["input"]) if "input" in rows else None
        result = inspect(snapshot, request, original, json.loads(rows["result"]) if "result" in rows else None,
                         frozen=self.frozen(world_id) is not None)
        return original, result

    def _reopening_insert(self, world_id, request, phase, payload):
        self.db.execute("INSERT INTO g5_reopening VALUES (?,?,?,?)",
                        (world_id, request["id"], phase, canonical(payload)))

    def reopening(self, world_id, request, result=None):
        """Register/read a request or finalize a non-public outcome under the world lock."""
        from app.g5.reopening import terminal
        if result is not None:
            terminal(result)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            original, resolved = self._reopening_check(world_id, request)
            if original is None:
                self._reopening_insert(world_id, request, "input", request)
            existing = self.db.execute("SELECT 1 FROM g5_reopening WHERE world_id=? "
                "AND request_id=? AND phase='result'", (world_id, request["id"])).fetchone()
            resolved = resolved if resolved is not None else result
            if resolved is not None and existing is None:
                self._reopening_insert(world_id, request, "result", resolved)
            self.db.execute("COMMIT")
            return deepcopy(resolved)
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def create(self, world_id: str, spec: dict, binding: dict) -> None:
        validate_spec(spec)
        if not isinstance(world_id, str) or not world_id:
            raise ValueError("World ID required")
        # Idempotent creation must not overwrite a previous experiment.
        self.db.execute("INSERT OR IGNORE INTO g5_worlds VALUES (?, ?, ?)",
                        (world_id, canonical(spec), canonical(binding)))
        if self.definition(world_id) != (spec, binding):
            raise Conflict("Existing world has a different frozen definition")

    def definition(self, world_id: str) -> tuple[dict, dict]:
        row = self.db.execute("SELECT spec, binding FROM g5_worlds WHERE id=?", (world_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown world")
        return json.loads(row[0]), json.loads(row[1])

    def events(self, world_id: str) -> list[dict]:
        spec, binding = self.definition(world_id)
        previous = digest([world_id, spec, binding])
        rows = self.db.execute("SELECT seq, request_id, request_hash, previous_hash, event_hash, payload "
                               "FROM g5_events WHERE world_id=? ORDER BY seq", (world_id,)).fetchall()
        events = []
        for seq, request_id, request_hash, prev, event_hash, raw in rows:
            payload = json.loads(raw)
            expected = digest([world_id, seq, request_id, request_hash, previous, payload])
            if seq != len(events) + 1 or prev != previous or event_hash != expected:
                raise ValueError("Event chain integrity failure")
            events.append({"seq": seq, "event_id": event_hash, "request_id": request_id,
                           "request_hash": request_hash, "payload": payload})
            previous = event_hash
        return events

    def facts(self, world_id: str, events: list[dict] | None = None) -> dict:
        spec, _ = self.definition(world_id)
        facts = json.loads(canonical(spec["facts"]))
        for fact in facts.values():
            fact["source"] = "scenario"
        for event in self.events(world_id) if events is None else events:
            receipt = event["payload"].get("receipt")
            if receipt and receipt["status"] == "success":
                for key, value in receipt["effects"].items():
                    facts[key]["value"] = value
                    facts[key]["source"] = event["event_id"]
        return facts

    def observe(self, world_id: str, actor: str) -> tuple[int, dict]:
        spec, binding = self.definition(world_id)
        if actor not in spec["roles"]:
            raise ValueError("Unregistered observer")
        events = self.events(world_id)
        visible = lambda scope: scope is None or actor in scope
        facts = {key: fact for key, fact in self.facts(world_id, events).items()
                 if visible(fact["visible_to"])}
        public = []
        from app.g5.cognition_storage import replay
        private_state = replay(binding, world_id, events, actor).get(actor, ({}, None, 0))[0]
        for event in events:
            data = event["payload"]
            if data["decision"]["action"] == "speak":
                public.append({"event_id": event["event_id"], "kind": "claim",
                               "actor": data["actor"], "content": data["decision"]["content"]})
            receipt = data.get("receipt")
            if receipt and visible(data["visible_to"]):
                public.append({"event_id": event["event_id"], "kind": "simulation_receipt",
                               "actor": data["actor"], "receipt": receipt})
        # The internal revision/cursor is returned separately, never in the model view.
        return len(events), {"actor": actor, "participants": spec["roles"], "facts": facts,
                             "observations": public, "cognition_state": private_state,
                             "operations": [name for name, action in spec["actions"].items()
                                            if actor in action["actors"]]}

    def commit(self, world_id: str, *, expected_version: int, request_id: str,
               actor: str, decision: Decision, audit: dict, reopen_request=None) -> dict:
        decision.validate()
        if not isinstance(audit, dict):
            raise ValueError("Audit must be a JSON object")
        if "cognition_state" in audit and not isinstance(audit["cognition_state"], dict):
            raise ValueError("Cognition state must be an object")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("Idempotency key required")
        request_hash = digest([actor, asdict(decision), audit])
        self.db.execute("BEGIN IMMEDIATE")
        try:
            spec, binding = self.definition(world_id)
            if reopen_request is not None:
                from app.g5.reopening import Resolved, publication
                original, resolved = self._reopening_check(world_id, reopen_request)
                if original is None:
                    raise ValueError("Reopening request must be registered")
                if resolved is not None:
                    raise Resolved(resolved)
                publication(reopen_request, expected_version, decision, audit)
            if actor not in spec["roles"]:
                raise ValueError("Unregistered actor")
            events = self.events(world_id)
            for event in events:
                if event["request_id"] == request_id:
                    if event["request_hash"] != request_hash:
                        raise Conflict("Idempotency key reused with changed decision")
                    self.db.execute("COMMIT")
                    return event
            if self.frozen(world_id) is not None:
                raise Conflict("Sealed dialogue cannot publish new events")
            if type(expected_version) is not int or expected_version != len(events):
                raise Conflict("Stale observation; regenerate against the new view")
            from app.g5.cognition_storage import validate_commit
            validate_commit(binding, world_id, events, actor, audit)
            payload = resolve_payload(spec, self.facts(world_id, events), actor, decision, audit)
            seq = len(events) + 1
            previous = events[-1]["event_id"] if events else digest([world_id, spec, binding])
            event_hash = digest([world_id, seq, request_id, request_hash, previous, payload])
            self.db.execute("INSERT INTO g5_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (world_id, seq, request_id, request_hash, previous, event_hash, canonical(payload)))
            event = {"seq": seq, "event_id": event_hash, "request_id": request_id,
                     "request_hash": request_hash, "payload": json.loads(canonical(payload))}
            if reopen_request is not None:
                self._reopening_insert(world_id, reopen_request, "result", {"status": "committed", "event": event})
            self.db.execute("COMMIT")
            return event
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise


class Snapshot(World):
    """Read-only in-memory projection sharing the reference world's semantics.

    No SQLite connection is created. The Postgres adapter supplies verified rows.
    """
    def __init__(self, world_id, spec, binding, events):
        self.world_id = world_id
        self.spec, self.binding, self.rows = deepcopy((spec, binding, events))

    def definition(self, world_id):
        if world_id != self.world_id:
            raise ValueError("Unknown snapshot")
        return deepcopy((self.spec, self.binding))

    def events(self, world_id):
        self.definition(world_id)
        return deepcopy(self.rows)
