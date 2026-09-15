"""Opt-in async PostgreSQL adapter; never imported by legacy API startup.

Call install() explicitly in a separately authorized schema. Runtime uses this
adapter through Runtime.open(); model calls never hold a database transaction.
"""
from dataclasses import asdict
import json
import re

from app.factorial_study import digest
from app.g5.attempts import validate_record
from app.g5.world import Conflict, Snapshot, canonical, resolve_payload, validate_spec


class PostgresWorld:
    def __init__(self, pool, schema):
        if not isinstance(schema, str) or not re.fullmatch(r"g5_[a-z0-9_]{1,55}", schema):
            raise ValueError("An explicit g5_-prefixed schema is required")
        self.pool, self.schema = pool, schema

    async def install(self):
        s = self.schema
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(f"""
                    CREATE SCHEMA IF NOT EXISTS {s};
                    CREATE TABLE IF NOT EXISTS {s}.worlds (
                        id TEXT PRIMARY KEY, spec TEXT NOT NULL, binding TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS {s}.events (
                        world_id TEXT NOT NULL REFERENCES {s}.worlds(id), seq BIGINT NOT NULL,
                        request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
                        previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, payload TEXT NOT NULL,
                        PRIMARY KEY(world_id, seq), UNIQUE(world_id, request_id));
                    CREATE TABLE IF NOT EXISTS {s}.attempts (
                        id BIGSERIAL PRIMARY KEY, world_id TEXT NOT NULL REFERENCES {s}.worlds(id),
                        payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS {s}.reopening (
                        world_id TEXT NOT NULL REFERENCES {s}.worlds(id), request_id TEXT NOT NULL,
                        phase TEXT NOT NULL CHECK(phase IN ('input','result')), payload TEXT NOT NULL,
                        PRIMARY KEY(world_id, request_id, phase));
                    CREATE TABLE IF NOT EXISTS {s}.freezes (
                        world_id TEXT PRIMARY KEY REFERENCES {s}.worlds(id), payload TEXT NOT NULL);
                    CREATE OR REPLACE FUNCTION {s}.reject_mutation() RETURNS trigger AS $$
                        BEGIN RAISE EXCEPTION 'G5 records are append-only'; END;
                    $$ LANGUAGE plpgsql;
                """)
                for table in ("worlds", "events", "attempts", "reopening", "freezes"):
                    # Reinstall is explicit and atomic; existing data is never rewritten.
                    await connection.execute(f"""
                        CREATE OR REPLACE TRIGGER immutable BEFORE UPDATE OR DELETE ON {s}.{table}
                        FOR EACH ROW EXECUTE FUNCTION {s}.reject_mutation();
                        CREATE OR REPLACE TRIGGER no_truncate BEFORE TRUNCATE ON {s}.{table}
                        FOR EACH STATEMENT EXECUTE FUNCTION {s}.reject_mutation();
                    """)

    async def create(self, world_id, spec, binding):
        validate_spec(spec)
        if not isinstance(world_id, str) or not world_id:
            raise ValueError("World ID required")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(f"INSERT INTO {self.schema}.worlds VALUES ($1,$2,$3) "
                                         "ON CONFLICT DO NOTHING", world_id, canonical(spec), canonical(binding))
                row = await connection.fetchrow(f"SELECT spec,binding FROM {self.schema}.worlds WHERE id=$1", world_id)
                if row["spec"] != canonical(spec) or row["binding"] != canonical(binding):
                    raise Conflict("Existing world has a different frozen definition")

    async def _snapshot(self, connection, world_id):
        row = await connection.fetchrow(f"SELECT spec,binding FROM {self.schema}.worlds WHERE id=$1", world_id)
        if row is None:
            raise ValueError("Unknown world")
        spec, binding = json.loads(row["spec"]), json.loads(row["binding"])
        previous = digest([world_id, spec, binding])
        events = []
        for row in await connection.fetch(f"SELECT * FROM {self.schema}.events WHERE world_id=$1 ORDER BY seq", world_id):
            payload = json.loads(row["payload"])
            expected = digest([world_id, row["seq"], row["request_id"], row["request_hash"], previous, payload])
            if row["seq"] != len(events) + 1 or row["previous_hash"] != previous or row["event_hash"] != expected:
                raise ValueError("Event chain integrity failure")
            events.append({"seq": row["seq"], "event_id": expected, "request_id": row["request_id"],
                           "request_hash": row["request_hash"], "payload": payload})
            previous = expected
        return Snapshot(world_id, spec, binding, events)

    async def _read(self, world_id, method, *args):
        async with self.pool.acquire() as connection:
            async with connection.transaction(isolation="repeatable_read", readonly=True):
                snapshot = await self._snapshot(connection, world_id)
                return getattr(snapshot, method)(world_id, *args)

    async def definition(self, world_id):
        return await self._read(world_id, "definition")

    async def events(self, world_id):
        return await self._read(world_id, "events")

    async def facts(self, world_id):
        return await self._read(world_id, "facts")

    async def observe(self, world_id, actor):
        return await self._read(world_id, "observe", actor)

    async def export_source(self, world_id):
        from app.g5.artifacts import source_bundle
        async with self.pool.acquire() as connection:
            async with connection.transaction(isolation="repeatable_read", readonly=True):
                snapshot = await self._snapshot(connection, world_id)
                spec, binding = snapshot.definition(world_id)
                attempts = [json.loads(r["payload"]) for r in await connection.fetch(
                    f"SELECT payload FROM {self.schema}.attempts WHERE world_id=$1 ORDER BY id", world_id)]
                rows = {}
                for row in await connection.fetch(f"SELECT request_id,phase,payload FROM {self.schema}.reopening WHERE world_id=$1 ORDER BY request_id", world_id):
                    rows.setdefault(row["request_id"], {})[row["phase"]] = json.loads(row["payload"])
                reopening = [{"request": r["input"], "result": r.get("result")} for r in rows.values()]
                return source_bundle(world_id, spec, binding, snapshot.events(world_id), attempts,
                                     reopening, await self._frozen(connection, world_id))

    async def _frozen(self, connection, world_id):
        from app.g5.freezing import make_freeze
        value = await connection.fetchval(f"SELECT payload FROM {self.schema}.freezes WHERE world_id=$1", world_id)
        if value is None:
            return None
        seal = json.loads(value)
        if seal != make_freeze(await self._snapshot(connection, world_id)):
            raise ValueError("Dialogue seal integrity failure")
        return seal

    async def frozen(self, world_id):
        async with self.pool.acquire() as connection:
            async with connection.transaction(isolation="repeatable_read", readonly=True):
                if await connection.fetchval(f"SELECT id FROM {self.schema}.worlds WHERE id=$1", world_id) is None:
                    raise ValueError("Unknown world")
                return await self._frozen(connection, world_id)

    async def freeze(self, world_id):
        from app.g5.freezing import make_freeze
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.fetchval(f"SELECT id FROM {self.schema}.worlds WHERE id=$1 FOR UPDATE", world_id)
                seal = await self._frozen(connection, world_id)
                if seal is None:
                    seal = make_freeze(await self._snapshot(connection, world_id))
                    await connection.execute(f"INSERT INTO {self.schema}.freezes VALUES ($1,$2)", world_id, canonical(seal))
                return seal

    async def _reopening_check(self, connection, world_id, request):
        from app.g5.reopening import inspect, validate
        validate(request)
        rows = {r["phase"]: json.loads(r["payload"]) for r in await connection.fetch(
            f"SELECT phase,payload FROM {self.schema}.reopening WHERE world_id=$1 AND request_id=$2",
            world_id, request["id"])}
        result = inspect(await self._snapshot(connection, world_id), request, rows.get("input"), rows.get("result"),
                         frozen=await self._frozen(connection, world_id) is not None)
        return rows, result

    async def _reopening_insert(self, connection, world_id, request, phase, payload):
        await connection.execute(f"INSERT INTO {self.schema}.reopening VALUES ($1,$2,$3,$4)",
                                 world_id, request["id"], phase, canonical(payload))

    async def reopening(self, world_id, request, result=None):
        from app.g5.reopening import terminal
        if result is not None:
            terminal(result)
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.fetchval(f"SELECT id FROM {self.schema}.worlds WHERE id=$1 FOR UPDATE", world_id)
                rows, resolved = await self._reopening_check(connection, world_id, request)
                if "input" not in rows:
                    await self._reopening_insert(connection, world_id, request, "input", request)
                resolved = resolved if resolved is not None else result
                if resolved is not None and "result" not in rows:
                    await self._reopening_insert(connection, world_id, request, "result", resolved)
                return resolved

    async def commit(self, world_id, *, expected_version, request_id, actor, decision, audit, reopen_request=None):
        decision.validate()
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("Idempotency key required")
        request_hash = digest([actor, asdict(decision), audit])
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Lock immutable parent row to serialize writers of this world only.
                found = await connection.fetchval(f"SELECT id FROM {self.schema}.worlds WHERE id=$1 FOR UPDATE", world_id)
                if found is None:
                    raise ValueError("Unknown world")
                if reopen_request is not None:
                    from app.g5.reopening import Resolved, publication
                    rows, resolved = await self._reopening_check(connection, world_id, reopen_request)
                    if "input" not in rows:
                        raise ValueError("Reopening request must be registered")
                    if resolved is not None:
                        raise Resolved(resolved)
                    publication(reopen_request, expected_version, decision, audit)
                snapshot = await self._snapshot(connection, world_id)
                spec, binding = snapshot.definition(world_id)
                events = snapshot.events(world_id)
                for event in events:
                    if event["request_id"] == request_id:
                        if event["request_hash"] != request_hash:
                            raise Conflict("Idempotency key reused with changed decision")
                        return event
                if await self._frozen(connection, world_id) is not None:
                    raise Conflict("Sealed dialogue cannot publish new events")
                if type(expected_version) is not int or expected_version != len(events):
                    raise Conflict("Stale observation; regenerate against new view")
                from app.g5.cognition_storage import validate_commit
                validate_commit(binding, world_id, events, actor, audit)
                payload = resolve_payload(spec, snapshot.facts(world_id), actor, decision, audit)
                seq = len(events) + 1
                previous = events[-1]["event_id"] if events else digest([world_id, spec, binding])
                event_hash = digest([world_id, seq, request_id, request_hash, previous, payload])
                await connection.execute(f"INSERT INTO {self.schema}.events VALUES ($1,$2,$3,$4,$5,$6,$7)",
                    world_id, seq, request_id, request_hash, previous, event_hash, canonical(payload))
                event = {"seq": seq, "event_id": event_hash, "request_id": request_id,
                         "request_hash": request_hash, "payload": payload}
                if reopen_request is not None:
                    await self._reopening_insert(connection, world_id, reopen_request, "result", {"status": "committed", "event": event})
                return event

    async def record_attempt(self, world_id, record):
        validate_record(record)
        async with self.pool.acquire() as connection:
            await connection.execute(f"INSERT INTO {self.schema}.attempts(world_id,payload) VALUES ($1,$2)",
                                     world_id, canonical(record))

    async def attempts(self, world_id):
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(f"SELECT payload FROM {self.schema}.attempts WHERE world_id=$1 ORDER BY id", world_id)
            return [json.loads(row["payload"]) for row in rows]
