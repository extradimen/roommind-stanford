"""Opt-in local PostgreSQL JSONB persistence test in a uniquely owned schema.

Uses a new connection after commit (not a PostgreSQL server restart). No
application table, schema migration, or existing experiment is touched.
"""
import asyncio
import json
import os
import uuid
import asyncpg
from app.world.executor import execute, KEY, SCHEMA


async def main():
    schema = "executor_test_" + uuid.uuid4().hex
    dsn = os.environ.get("SIMULATION_TEST_DSN", "postgresql:///postgres")
    connection = await asyncpg.connect(dsn)
    config = {"simulation_executor": {"schema": SCHEMA, "initial_facts": {}, "actions": {
        "contain": {"actors": ["sre"], "field": "containment_active", "value": True}}}}
    request = {"request_id": "persisted", "operation": "contain"}
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        await connection.execute(f'CREATE TABLE "{schema}".states (condition text PRIMARY KEY, payload jsonb)')
        for condition in ("roommind", "baseline"):
            state = {}
            execute(config, state, actor_id="sre", request=request, turn_id=1)
            await connection.execute(f'INSERT INTO "{schema}".states VALUES ($1, $2::jsonb)', condition, json.dumps(state))
        await connection.close()
        connection = await asyncpg.connect(dsn)
        states = []
        for condition in ("roommind", "baseline"):
            state = json.loads(await connection.fetchval(f'SELECT payload FROM "{schema}".states WHERE condition=$1', condition))
            before = json.dumps(state, sort_keys=True)
            execute(config, state, actor_id="sre", request=request, turn_id=99)
            assert json.dumps(state, sort_keys=True) == before
            assert state[KEY]["facts"] == {"containment_active": True}
            states.append(state)
        assert states[0] == states[1]
        transaction = connection.transaction()
        await transaction.start()
        await connection.execute(f'UPDATE "{schema}".states SET payload=\'{{}}\'::jsonb')
        await transaction.rollback()
        assert await connection.fetchval(f'SELECT count(*) FROM "{schema}".states WHERE payload ? $1', KEY) == 2
        print("PostgreSQL: two-condition commit/reconnect/idempotency/rollback passed")
    finally:
        if connection.is_closed():
            connection = await asyncpg.connect(dsn)
        # Only the unique schema created by this test is eligible for cleanup.
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
