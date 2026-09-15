"""Abrupt exit of owned offline child processes, never a live application process."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest

from app.g5.world import World
from test_g5_composed_runtime import Harness


CHILD = r'''
import asyncio, os, sys
from app.g5.world import World
from test_g5_composed_runtime import Harness

async def main():
    world = World(sys.argv[1])
    harness = Harness()
    runtime = harness.runtime(world, "D")
    await runtime.step()
    if sys.argv[2] == "before_commit":
        async def interrupted(request):
            os._exit(73)
        harness.annotator.transport = interrupted
    else:
        original = world.commit
        def interrupted(*args, **kwargs):
            original(*args, **kwargs)
            os._exit(74)
        world.commit = interrupted
    await runtime.step()
    raise RuntimeError("Crash injection not reached")

asyncio.run(main())
'''

POSTGRES_CHILD = r'''
import asyncio, os, sys, asyncpg
from app.g5.postgres import PostgresWorld
from app.g5.runtime import Runtime
from test_g5_composed_runtime import Harness

async def main():
    pool = await asyncpg.create_pool(os.environ["G5_TEST_DSN"], min_size=1, max_size=2)
    world = PostgresWorld(pool, sys.argv[1])
    harness = Harness()
    args = harness.runtime_options(world, "D")
    if len(sys.argv) > 3 and sys.argv[3] == "scheduled":
        from test_g5_scheduled_runtime import options
        harness, args = options(world, "D")
    runtime = await Runtime.open(**args)
    await runtime.step()
    if sys.argv[2] == "before_commit":
        async def interrupted(request):
            os._exit(73)
        harness.annotator.transport = interrupted
    else:
        original = world.commit
        async def interrupted(*args, **kwargs):
            await original(*args, **kwargs)
            os._exit(74)
        world.commit = interrupted
    await runtime.step()
    raise RuntimeError("Crash injection not reached")

asyncio.run(main())
'''


class ProcessRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def check_recovery(self, mode, code, committed, stage):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "owned-world.sqlite")
            server = Path(__file__).resolve().parents[1]
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join([str(server), str(server / "tests")])
            child = await asyncio.create_subprocess_exec(
                sys.executable, "-c", CHILD, path, mode, env=environment,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=20)
            except BaseException:
                if child.returncode is None:
                    child.kill()  # Only this test's own subprocess.
                    await child.wait()
                raise
            self.assertEqual(child.returncode, code, stderr.decode())
            self.assertEqual(stdout, b"")
            world = World(path)
            reference = World(":memory:")
            try:
                self.assertEqual(len(world.events("D")), committed)
                journal = world.attempts("D")
                self.assertEqual(journal[-1]["stage"], stage)
                self.assertEqual(journal[-1]["status"], "started")
                resumed = Harness().runtime(world, "D")
                uninterrupted = Harness().runtime(reference, "D")
                for _ in range(4 - committed):
                    await resumed.step()
                for _ in range(4):
                    await uninterrupted.step()
                self.assertEqual(world.events("D"), reference.events("D"))
                self.assertEqual(await resumed.question_journal.project(),
                                 await uninterrupted.question_journal.project())
                # Do not rewrite an interrupted attempt as success or failure.
                self.assertEqual(world.attempts("D")[:len(journal)], journal)
                for actor in ("security", "sre"):
                    self.assertEqual(world.observe("D", actor), reference.observe("D", actor))
                self.assertEqual((await resumed.step())["status"], "cutoff")
            finally:
                world.close()
                reference.close()

    async def test_abrupt_exit_before_commit_keeps_cursor_and_recovers(self):
        await self.check_recovery("before_commit", 73, 1, "annotation")

    async def test_abrupt_exit_after_commit_does_not_duplicate_published_turn(self):
        await self.check_recovery("after_commit", 74, 2, "commit")
