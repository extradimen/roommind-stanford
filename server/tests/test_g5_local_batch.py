"""Complete synthetic batch entry/recovery, separate from online research."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

import test_g5_study_preflight as base
from test_g5_family_registry import register, exposure
from test_g5_cognition_storage import storage_options
from app.factorial_study import digest, freeze_design
from app.g5.measurement import freeze_analysis
from app.g5.study_preflight import freeze_contract
from app.g5.local_batch import LocalBatch
from app.g5.world import World


def factory(world, contract, calls):
    def build(assignment):
        harness, _, options = storage_options(world, assignment["arm"])
        calls.append(harness)
        options.update(manifest=contract["manifest"], ordinal=assignment["ordinal"])
        return options
    return build


class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await base.PreflightTests.asyncSetUp(self)
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.world = World(str(Path(self.directory.name) / "world.sqlite")); self.addCleanup(self.world.close)
        _, _, options = storage_options(self.world, "D")
        self.sample = {**self.sample, "family_count": 1}
        config = {**self.analysis["config"], "sample_size_plan_sha256": digest(self.sample)}
        self.analysis = freeze_analysis(config, version=3, sampling_target={"kind": "fixed-family-benchmark",
            "frame_sha256": digest(self.sample["sampling_frame"])})
        design = copy.deepcopy(options["manifest"]["design"])
        design.update(stage="exploration", analysis_plan_sha256=self.analysis["sha256"], sample_size_plan_sha256=digest(self.sample))
        for arm in design["arms"].values(): arm["shared"]["evaluator_plan_sha256"] = self.analysis["sha256"]
        self.study = freeze_design(design); register(self.registry, self.study)
        self.frozen_registry = self.registry.export()
        self.contract = freeze_contract(self.study, self.analysis, self.frozen_registry, self.sample, self.criteria)
        self.schedule = {str(a["ordinal"]): [{"id": "planned-reopen", "episode": 1, "version": 4}] for a in self.study["assignments"]}
        self.control = str(Path(self.directory.name) / "control.sqlite")
        self.harnesses = []

    def batch(self, **overrides):
        options = dict(world=self.world, contract=self.contract, frozen_registry=self.frozen_registry,
            registry_reader=self.registry.export, annotation=self.annotation, results=self.results,
            factory=factory(self.world, self.contract, self.harnesses), reopen_requests=self.schedule)
        options.update(overrides)
        return LocalBatch(self.control, **options)

    async def test_whole_batch_resume_sealed_reuse_and_evaluation_barrier(self):
        batch = self.batch()
        with self.assertRaises((ValueError, KeyError)): await batch.evaluation_inputs()
        stream = batch.run()
        for _ in range(3): self.assertEqual((await anext(stream))["status"], "committed")
        with self.assertRaises(ValueError): batch.close()
        await stream.aclose(); batch.close()
        batch = self.batch()
        try:
            rows = [r async for r in batch.run()]
            self.assertEqual(sum(r["status"] == "sealed" for r in rows), 4)
            bundle = await batch.evaluation_inputs()
            self.assertEqual([len(s["events"]) for s in bundle["sources"]], [7] * 4)
            old = copy.deepcopy(bundle)
            self.harnesses.clear()
            self.assertEqual(len([r async for r in batch.run()]), 4)
            self.assertTrue(all(not h.calls for h in self.harnesses))
            self.assertEqual(await batch.evaluation_inputs(), old)
        finally: batch.close()

    async def test_all_assignments_validated_before_first_world_and_registry_drift_stops(self):
        good = factory(self.world, self.contract, self.harnesses)
        def wrong(a):
            args = good(a)
            if a["ordinal"] == 4: args["max_steps"] += 1
            return args
        batch = self.batch(factory=wrong)
        with self.assertRaises(ValueError): await anext(batch.run())
        self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM g5_worlds").fetchone()[0], 0)
        batch.close()
        batch = self.batch(); stream = batch.run(); await anext(stream)
        self.registry.append({**exposure("f-0"), "id": "late-development"})
        with self.assertRaises(ValueError): await anext(stream)
        batch.close()

    async def test_competing_worker_changed_schedule_and_replaced_storage_rejected(self):
        first = self.batch(); second = self.batch()
        stream = first.run(); await anext(stream)
        with self.assertRaises(ValueError): await anext(second.run())
        await stream.aclose(); first.close(); second.close()
        altered = copy.deepcopy(self.schedule); altered["1"][0]["id"] = "different"
        with self.assertRaises(ValueError): self.batch(reopen_requests=altered)
        other = World(str(Path(self.directory.name) / "replacement.sqlite")); self.addCleanup(other.close)
        batch = self.batch(world=other, factory=factory(other, self.contract, []))
        try:
            with self.assertRaises(ValueError): await anext(batch.run())
            self.assertEqual(other.db.execute("SELECT COUNT(*) FROM g5_worlds").fetchone()[0], 0)
        finally: batch.close()

    async def test_technical_failure_is_retained_and_resume_does_not_reset_budget(self):
        good = factory(self.world, self.contract, self.harnesses)
        def failing(a):
            args = good(a)
            self.harnesses[-1].fail_annotation = True
            return args
        batch = self.batch(factory=failing)
        with self.assertRaises(TimeoutError): await anext(batch.run())
        batch.close()
        wid = self.world.db.execute("SELECT id FROM g5_worlds").fetchone()[0]
        self.assertEqual(self.world.events(wid), [])
        before = self.world.attempts(wid)
        self.assertEqual(before[-1]["status"], "failed")
        batch = self.batch()
        try:
            _ = [r async for r in batch.run()]
            self.assertEqual(self.world.attempts(wid)[:len(before)], before)
            self.assertEqual(len(self.world.events(wid)), 7)
        finally: batch.close()

    async def test_unfair_or_overbudget_schedule_rejected_before_generation(self):
        unfair = copy.deepcopy(self.schedule); unfair["1"] = []
        with self.assertRaises(ValueError): self.batch(reopen_requests=unfair)
        self.assertFalse(Path(self.control).exists())
        late = {k: [{**v[0], "version": 8}] for k,v in self.schedule.items()}
        batch = self.batch(reopen_requests=late)
        try:
            with self.assertRaises(ValueError): await anext(batch.run())
            self.assertEqual(self.world.db.execute("SELECT COUNT(*) FROM g5_worlds").fetchone()[0], 0)
        finally: batch.close()

    async def test_real_process_exit_before_and_after_commit_recovers_prefix(self):
        # One owned control/world pair per failure mode; never replace a study.
        for mode in ("before", "after"):
            world_path = str(Path(self.directory.name) / (mode + "-world.sqlite"))
            self.world = World(world_path); self.addCleanup(self.world.close)
            self.control = str(Path(self.directory.name) / (mode + "-control.sqlite"))
            config_path = Path(self.directory.name) / (mode + ".json")
            with config_path.open("x") as stream:
                json.dump({"contract": self.contract, "registry": self.frozen_registry, "annotation": self.annotation,
                           "results": self.results, "schedule": self.schedule}, stream)
            child = """import asyncio,json,os,sys
from app.g5.world import World
from app.g5.local_batch import LocalBatch
from test_g5_local_batch import factory
c=json.load(open(sys.argv[1])); w=World(sys.argv[2]); original=w.commit
def commit(*a,**kw):
    if sys.argv[4]=='before': os._exit(75)
    value=original(*a,**kw)
    os._exit(74)
w.commit=commit
async def run():
    b=LocalBatch(sys.argv[3],world=w,contract=c['contract'],frozen_registry=c['registry'],registry_reader=lambda:c['registry'],annotation=c['annotation'],results=c['results'],factory=factory(w,c['contract'],[]),reopen_requests=c['schedule'])
    async for r in b.run(): pass
asyncio.run(run())
"""
            process = await asyncio.create_subprocess_exec(sys.executable, "-c", child, str(config_path), world_path,
                self.control, mode, env={**os.environ, "PYTHONPATH": "server:server/tests"},
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try: _, stderr = await asyncio.wait_for(process.communicate(), 30)
            finally:
                if process.returncode is None: process.kill(); await process.wait()
            self.assertEqual(process.returncode, 75 if mode == "before" else 74, stderr.decode())
            old = self.world.db.execute("SELECT id FROM g5_worlds").fetchone()[0]
            prefix = self.world.events(old); self.assertEqual(len(prefix), 0 if mode == "before" else 1)
            batch = self.batch()
            try:
                _ = [r async for r in batch.run()]
                bundle = await batch.evaluation_inputs()
                self.assertEqual(self.world.events(old)[:len(prefix)], prefix)
                self.assertEqual(sum(len(s["events"]) for s in bundle["sources"]), 28)
            finally: batch.close()

    @unittest.skipUnless(os.environ.get("G5_TEST_DSN"), "Local PostgreSQL DSN required")
    async def test_postgres_complete_batch_pool_reconnect_and_sqlite_event_parity(self):
        import asyncpg
        from app.g5.postgres import PostgresWorld
        batch = self.batch()
        try:
            _ = [r async for r in batch.run()]; expected = await batch.evaluation_inputs()
        finally: batch.close()
        pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=2)
        schema = "g5_test_" + uuid.uuid4().hex
        owned = False
        try:
            async with pool.acquire() as c: await c.execute(f"CREATE SCHEMA {schema}")
            owned = True
            world = PostgresWorld(pool, schema); await world.install()
            self.control = str(Path(self.directory.name) / "pg-control.sqlite")
            batch = self.batch(world=world, factory=factory(world, self.contract, []))
            stream = batch.run(); await anext(stream); await stream.aclose(); batch.close()
            await pool.close(); pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=2)
            world = PostgresWorld(pool, schema)
            batch = self.batch(world=world, factory=factory(world, self.contract, []))
            try:
                _ = [r async for r in batch.run()]; actual = await batch.evaluation_inputs()
                self.assertEqual([s["events"] for s in expected["sources"]], [s["events"] for s in actual["sources"]])
            finally: batch.close()
        finally:
            if owned:
                async with pool.acquire() as c: await c.execute(f"DROP SCHEMA {schema} CASCADE")
            await pool.close()


if __name__ == "__main__":
    import argparse
    from app.g5.world import canonical
    parser = argparse.ArgumentParser(description="Local scripted full-component batch; no network provider")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    async def audit():
        case = BatchTests()
        try:
            await case.asyncSetUp()
            batch = case.batch(); stream = batch.run()
            progress = [await anext(stream) for _ in range(3)]
            await stream.aclose(); batch.close()
            wid = case.world.db.execute("SELECT id FROM g5_worlds").fetchone()[0]
            prefix = case.world.events(wid)
            batch = case.batch()
            try:
                progress += [r async for r in batch.run()]
                bundle = await batch.evaluation_inputs()
                if case.world.events(wid)[:len(prefix)] != prefix: raise ValueError("Recovery prefix changed")
                raw = {"schema": "g5-local-batch-entry-audit-v1", "classification": "synthetic-engineering-only",
                    "contract": case.contract, "registry": case.frozen_registry, "annotation": case.annotation,
                    "calibration_results": case.results, "preflight": batch.preflight, "progress": progress,
                    "recovery_prefix": prefix, "evaluation_inputs": bundle,
                    "real_model_calls": 0, "external_evaluation_authorized": False}
                raw["sha256"] = digest(raw)
                directory = Path(args.output_dir); directory.mkdir(mode=0o700, exist_ok=False)
                with os.fdopen(os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
                    output.write(canonical(raw)); output.flush(); os.fsync(output.fileno())
                print(json.dumps({"sha256": raw["sha256"], "sealed_dialogues": len(bundle["sources"]),
                    "committed_events": sum(len(s["events"]) for s in bundle["sources"])}))
            finally: batch.close()
        finally: case.doCleanups()
    asyncio.run(audit())
