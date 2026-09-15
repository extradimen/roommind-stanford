"""Cooperating local synthetic batch entry, not an online research launcher.

Factories are trusted executable dependencies, not sandboxed plugins. This
module does not import a network transport. It cannot prevent malicious callbacks
or independent legacy writers from bypassing its single-host coordination.
"""
from copy import deepcopy
import json
import sqlite3
from pathlib import Path

from app.factorial_study import digest
from app.g5.artifacts import verify_source
from app.g5.evaluation import packet_from_source
from app.g5.local_worker import LocalWorker
from app.g5.family_registry import verify_export
from app.g5.measurement import require
from app.g5.reopening import validate as validate_request
from app.g5.runtime import Runtime
from app.g5.study_preflight import require_local_contract
from app.g5.world import canonical


class LocalBatch:
    def __init__(self, control_path, *, world, contract, frozen_registry, registry_reader,
                 annotation, results, factory, reopen_requests):
        require(str(control_path) != ":memory:", "Persistent private coordination file required")
        require(contract["sample_plan"]["scope"] == "synthetic_control"
            and contract["manifest"]["design"]["stage"] == "exploration", "Local entry permits synthetic exploration only")
        self.contract, self.registry = deepcopy(contract), deepcopy(frozen_registry)
        self.annotation, self.results = deepcopy(annotation), deepcopy(results)
        self.reader, self.world, self.factory = registry_reader, world, factory
        self.manifest = self.contract["manifest"]
        ordinals = {str(a["ordinal"]) for a in self.manifest["assignments"]}
        require(isinstance(reopen_requests, dict) and set(reopen_requests) == ordinals, "Explicit reopen schedule for every assignment required")
        for requests in reopen_requests.values():
            require(isinstance(requests, list), "Reopen schedule must be a list")
            for request in requests: validate_request(request)
            require(len({r["id"] for r in requests}) == len(requests)
                and len({r["version"] for r in requests}) == len(requests)
                and [r["version"] for r in requests] == sorted(r["version"] for r in requests), "Ambiguous reopen schedule")
        paired_schedules = {}
        for assignment in self.manifest["assignments"]:
            block = assignment["block_id"]
            schedule = canonical(reopen_requests[str(assignment["ordinal"])])
            require(block not in paired_schedules or paired_schedules[block] == schedule,
                    "Paired conditions must receive the same frozen reopen schedule")
            paired_schedules[block] = schedule
        self.requests = deepcopy(reopen_requests)
        self.preflight = self._preflight()
        self.header = {"schema": "g5-local-synthetic-batch-v1", "contract_sha256": contract["sha256"],
            "manifest_sha256": self.manifest["manifest_sha256"], "reopen_requests": self.requests,
            "annotation_sha256": annotation["sha256"], "results_sha256": results["sha256"],
            "preflight_sha256": self.preflight["sha256"]}
        self.db = sqlite3.connect(control_path, isolation_level=None, timeout=10)
        try:
            self.worker = LocalWorker(control_path)
            with self.worker.claim():
                self.db.execute("BEGIN IMMEDIATE")
                tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                require(not tables or tables == {"batch_header", "batch_store"}, "Unrelated control database")
                self.db.execute("CREATE TABLE IF NOT EXISTS batch_header(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
                self.db.execute("CREATE TABLE IF NOT EXISTS batch_store(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
                old = self.db.execute("SELECT payload FROM batch_header WHERE id=1").fetchone()
                if old is None: self.db.execute("INSERT INTO batch_header VALUES(1,?)", (canonical(self.header),))
                else: require(old[0] == canonical(self.header), "Batch control belongs to another frozen execution")
                for table in ("batch_header", "batch_store"):
                    for action in ("UPDATE", "DELETE"):
                        self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable batch control'); END")
                self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction: self.db.execute("ROLLBACK")
            self.db.close(); raise

    def _preflight(self):
        return require_local_contract(self.contract, self.registry, self.reader(),
            annotation=self.annotation, results=self.results)

    def _check(self):
        self.worker.check()
        require(self.db.execute("SELECT payload FROM batch_header WHERE id=1").fetchone()[0] == canonical(self.header), "Batch header changed")
        current = self.reader(); verify_export(current)
        require(current["sha256"] == self.contract["registry_sha256"], "Registry changed; stop before next operation")

    async def _bind_store(self):
        from app.g5.world import World
        from app.g5.postgres import PostgresWorld
        if type(self.world) is World:
            filename = self.world.db.execute("PRAGMA database_list").fetchone()[2]
            require(bool(filename), "Persistent world database required")
            path = Path(filename).resolve(strict=True); info = path.stat()
            identity = {"backend": "sqlite", "path": str(path), "device": info.st_dev, "inode": info.st_ino}
        elif type(self.world) is PostgresWorld:
            async with self.world.pool.acquire() as connection:
                row = await connection.fetchrow("SELECT current_database() AS db, inet_server_addr()::text AS addr, inet_server_port() AS port, oid FROM pg_namespace WHERE nspname=$1", self.world.schema)
            require(row is not None, "Missing configured schema")
            identity = {"backend": "postgres", "schema": self.world.schema, **dict(row)}
        else:
            raise ValueError("Supported persistent world store required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT payload FROM batch_store WHERE id=1").fetchone()
            if old is None: self.db.execute("INSERT INTO batch_store VALUES(1,?)", (canonical(identity),))
            else: require(old[0] == canonical(identity), "Batch world storage changed; refuse replacement run")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK"); raise

    def close(self):
        require(not self.worker.active, "Close the batch stream before closing storage")
        self.db.close()

    def _configured(self):
        runtimes = []
        required = {"components", "request_budget", "observation_window", "cognition_storage", "scheduling",
                    "question_annotation", "session_annotation"}
        require(required <= set(self.manifest["design"]), "Complete composed runtime declarations required")
        def providers(value):
            if isinstance(value, dict):
                return ([value["provider"]] if "provider" in value else []) + [p for v in value.values() for p in providers(v)]
            if isinstance(value, list): return [p for v in value for p in providers(v)]
            return []
        declared = providers(self.manifest["design"])
        require(declared and all(p == "offline" for p in declared), "Only declared offline fixture providers are allowed")
        for assignment in self.manifest["assignments"]:
            options = dict(self.factory(deepcopy(assignment)))
            require(options["manifest"] == self.manifest and options["ordinal"] == assignment["ordinal"]
                and options["world"] is self.world and options.get("role_inputs") is not None
                and options.get("reliable_reopening") is True, "Factory returned another assignment or incomplete inputs")
            options["world_id"] = "g5-batch-" + digest([self.header, assignment["ordinal"]])
            runtime = Runtime.__new__(Runtime)
            runtime._configure(**options)  # Validate ALL assignments before creating any world.
            require(all(r["version"] < runtime.max_steps for r in self.requests[str(assignment["ordinal"])]),
                    "Reopening scheduled outside the common step budget")
            runtimes.append(runtime)
        return runtimes

    async def run(self):
        with self.worker.claim():
            self._preflight(); self._check()
            runtimes = self._configured()
            await self._bind_store()
            for runtime in runtimes:
                self._check()
                await runtime._store("create", runtime.world_id, runtime.spec, runtime.binding)
                ordinal = runtime.binding["assignment"]["ordinal"]
                while True:
                    self._check()
                    if await runtime._store("frozen", runtime.world_id) is not None:
                        source = await runtime._store("export_source", runtime.world_id)
                        verify_source(source, self.manifest)
                        yield {"status": "sealed", "ordinal": ordinal, "source_sha256": source["sha256"]}
                        break
                    events = await runtime._store("events", runtime.world_id)
                    schedule = self.requests[str(ordinal)]
                    request = next((r for r in schedule if r["version"] == len(events)), None)
                    result = await runtime.step(**({"reopen_request": request} if request else {}))
                    if result["status"] == "committed":
                        yield {"status": "committed", "ordinal": ordinal, "version": len(events) + 1}
                    elif result["status"] in ("session_closed", "cutoff", "reopen_declined"):
                        require(not any(r["version"] > len(events) for r in schedule), "Session stopped before its frozen reopen schedule")
                        await runtime._store("freeze", runtime.world_id)
                    else:
                        raise ValueError("Unexpected batch runtime outcome: " + result["status"])

    async def evaluation_inputs(self):
        """No evaluation call: require and verify every sealed assigned source."""
        with self.worker.claim():
            self._preflight(); self._check()
            await self._bind_store()
            sources = []
            for runtime in self._configured():
                self._check()
                source = await runtime._store("export_source", runtime.world_id)
                verify_source(source, self.manifest); sources.append(source)
            raw = {"schema": "g5-local-batch-evaluation-inputs-v1", "header": deepcopy(self.header),
                "manifest": deepcopy(self.manifest), "sources": sources,
                "packets": [packet_from_source(s, self.manifest) for s in sources],
                "external_evaluation_authorized": False}
            return {**raw, "sha256": digest(raw)}
