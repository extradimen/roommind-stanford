"""Real local process ownership/recovery; synthetic transport only."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import test_g5_prediction_archive as fixtures
from app.factorial_study import digest
from app.g5.calibration_predictor import ModelPredictor
from app.g5.local_worker import LocalWorker
from app.g5.model_policy import ModelBinding, Completion
from app.g5.prediction_archive import PredictionArchive, verify_export


CHILD = '''
import asyncio,json,sys
from app.factorial_study import digest
from app.g5.calibration_predictor import ModelPredictor
from app.g5.model_policy import ModelBinding,Completion
from app.g5.prediction_archive import PredictionArchive
d=json.load(open(sys.argv[1])); mode=sys.argv[3]
async def transport(request):
 print('CALL',flush=True)
 if mode=='pending': sys.stdin.readline()
 return Completion(json.dumps({'prediction':'clear','rationale':'Synthetic response.'}), 'offline','fixed','mock',digest(request),'stop')
async def main():
 p=ModelPredictor(ModelBinding('offline','fixed','mock',.2,2048),transport,predictor_id='synthetic-predictor',kind='synthetic')
 a=PredictionArchive(sys.argv[2],d['annotation'],d['plan'])
 s=a.run_missing(p,resume_pending=True)
 try:
  try: await anext(s)
  except ValueError as e:
   print('BUSY' if 'owns this prediction' in str(e) else 'ERROR:'+str(e),flush=True)
   return
  print('COMMITTED',flush=True)
  if mode=='committed': sys.stdin.readline()
 finally:
  await s.aclose(); a.close()
asyncio.run(main())
'''


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.PredictionTests.asyncSetUp(self)

    async def test_same_database_competitor_cannot_resume_or_append_while_owner_awaits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "ledger.sqlite")
            owner = PredictionArchive(path, self.annotation, self.plan)
            rival = PredictionArchive(path, self.annotation, self.plan)
            entered, release = asyncio.Event(), asyncio.Event()
            async def transport(request):
                entered.set()
                await release.wait()
                return Completion(json.dumps({"prediction": "clear", "rationale": "Synthetic response."}),
                    "offline", "fixed", "mock", digest(request), "stop")
            predictor = ModelPredictor(ModelBinding("offline", "fixed", "mock", .2, 2048), transport,
                predictor_id="synthetic-predictor", kind="synthetic")
            async def run():
                stream = owner.run_missing(predictor)
                try:
                    return await anext(stream)
                finally:
                    await stream.aclose()
            task = asyncio.create_task(run())
            try:
                await asyncio.wait_for(entered.wait(), 10)
                saved = rival.export()
                for archive in (owner, rival):
                    with self.assertRaises(ValueError):
                        [r async for r in archive.run_missing(self.predictor, resume_pending=True)]
                    with self.assertRaises(ValueError):
                        archive.append(saved["events"][0])
                with self.assertRaises(ValueError):
                    owner.close()
                self.assertEqual(self.requests, [])
                release.set()
                await asyncio.wait_for(task, 10)
                self.assertEqual(len([r async for r in rival.run_missing(self.predictor)]), 3)
                self.assertEqual(len(rival.export()["results"]["attempts"]), 4)
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                owner.close(); rival.close()

    async def test_task_cancellation_releases_ownership_and_retains_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "ledger.sqlite")
            archive = PredictionArchive(path, self.annotation, self.plan)
            entered = asyncio.Event()
            async def transport(request):
                entered.set()
                await asyncio.Event().wait()
            predictor = ModelPredictor(ModelBinding("offline", "fixed", "mock", .2, 2048), transport,
                predictor_id="synthetic-predictor", kind="synthetic")
            async def run():
                return [r async for r in archive.run_missing(predictor)]
            task = asyncio.create_task(run())
            await asyncio.wait_for(entered.wait(), 10)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            saved = archive.export()
            archive.close()
            recovered = PredictionArchive(path, self.annotation, self.plan)
            try:
                with self.assertRaises(ValueError):
                    [r async for r in recovered.run_missing(self.predictor)]
                self.assertEqual(len([r async for r in recovered.run_missing(self.predictor, resume_pending=True)]), 4)
                self.assertEqual(recovered.export()["results"]["attempts"][0]["id"], saved["pending_indeterminate"][0]["id"])
            finally:
                recovered.close()

    async def test_transport_ignoring_cancellation_does_not_release_owner_early(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "ledger.sqlite")
            owner = PredictionArchive(path, self.annotation, self.plan)
            rival = PredictionArchive(path, self.annotation, self.plan)
            entered, ignored, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
            async def transport(request):
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    ignored.set()
                    await release.wait()
                return Completion(json.dumps({"prediction": "clear", "rationale": "Synthetic response."}),
                    "offline", "fixed", "mock", digest(request), "stop")
            predictor = ModelPredictor(ModelBinding("offline", "fixed", "mock", .2, 2048), transport,
                predictor_id="synthetic-predictor", kind="synthetic")
            async def run():
                stream = owner.run_missing(predictor)
                try: return await anext(stream)
                finally: await stream.aclose()
            task = asyncio.create_task(run())
            try:
                await asyncio.wait_for(entered.wait(), 10)
                task.cancel()
                await asyncio.wait_for(ignored.wait(), 10)
                with self.assertRaises(ValueError):
                    [r async for r in rival.run_missing(self.predictor, resume_pending=True)]
                self.assertEqual(self.requests, [])
                release.set()
                await asyncio.wait_for(task, 10)
                self.assertEqual(len([r async for r in rival.run_missing(self.predictor)]), 3)
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)
                owner.close(); rival.close()

    async def test_real_process_lock_competition_and_death_before_or_after_commit(self):
        self.process_evidence = []
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.json"
            source.write_text(json.dumps({"annotation": self.annotation, "plan": self.plan}))
            for mode in ("pending", "committed"):
                path = str(Path(folder) / (mode + ".sqlite"))
                async def spawn(child_mode):
                    return await asyncio.create_subprocess_exec(sys.executable, "-c", CHILD, str(source), path, child_mode,
                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                process = await spawn(mode)
                rival = None
                try:
                    self.assertEqual(await asyncio.wait_for(process.stdout.readline(), 15), b"CALL\n")
                    if mode == "committed":
                        self.assertEqual(await asyncio.wait_for(process.stdout.readline(), 15), b"COMMITTED\n")
                    rival = await spawn("compete")
                    out, err = await asyncio.wait_for(rival.communicate(), 15)
                    self.assertEqual(rival.returncode, 0, err.decode())
                    self.assertEqual(out, b"BUSY\n")
                    snapshot = PredictionArchive(path, self.annotation, self.plan)
                    before = snapshot.export()
                    snapshot.close()
                    process.kill()
                    await asyncio.wait_for(process.communicate(), 15)
                    self.assertLess(process.returncode, 0)
                    recovered = PredictionArchive(path, self.annotation, self.plan)
                    try:
                        calls = len(self.requests)
                        completed = [r async for r in recovered.run_missing(self.predictor, resume_pending=True)]
                        after = recovered.export()
                        self.assertEqual(len(completed), 4 if mode == "pending" else 3)
                        self.assertEqual(len(self.requests) - calls, len(completed))
                        self.assertEqual(len(after["results"]["attempts"]), 4)
                        self.assertEqual(after["events"][:len(before["events"])], before["events"])
                        self.assertEqual(verify_export(after)["pending_indeterminate"], 0)
                        self.process_evidence.append({"mode": mode, "competing_process_calls": 0,
                            "exit_code": process.returncode, "recovery_calls": len(completed),
                            "before": before, "after": after})
                    finally:
                        recovered.close()
                finally:
                    for child in (process, rival):
                        if child is not None and child.returncode is None:
                            child.kill()
                            await child.communicate()

    async def test_lock_replacement_blocks_late_result_without_committing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = PredictionArchive(str(Path(folder) / "ledger.sqlite"), self.annotation, self.plan)
            async def transport(request):
                lock = archive.worker.lock_path
                lock.rename(lock.with_suffix(".preserved"))
                lock.touch(mode=0o600)
                return Completion(json.dumps({"prediction": "clear", "rationale": "Synthetic response."}),
                    "offline", "fixed", "mock", digest(request), "stop")
            predictor = ModelPredictor(ModelBinding("offline", "fixed", "mock", .2, 2048), transport,
                predictor_id="synthetic-predictor", kind="synthetic")
            try:
                with self.assertRaisesRegex(ValueError, "lock identity"):
                    [r async for r in archive.run_missing(predictor)]
                self.assertEqual(archive.export()["results"]["attempts"], [])
                self.assertEqual(len(archive.export()["pending_indeterminate"]), 1)
            finally:
                archive.close()


class StorageTests(unittest.TestCase):
    def test_database_symlink_uses_same_lock_and_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "db"
            database.touch()
            alias = Path(folder) / "alias"
            alias.symlink_to(database)
            worker, competing = LocalWorker(database), LocalWorker(alias)
            with worker.claim():
                with self.assertRaises(ValueError):
                    with competing.claim(): pass
                database.rename(Path(folder) / "preserved-db")
                database.touch()
                with self.assertRaises(ValueError):
                    worker.check()

    def test_lock_persists_and_symlink_hardlink_and_permissive_lock_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "db"
            database.touch()
            worker = LocalWorker(database)
            with worker.claim():
                worker.check()
            inode = worker.lock_path.stat().st_ino
            with worker.claim():
                self.assertEqual(worker.lock_path.stat().st_ino, inode)
            worker.lock_path.chmod(0o644)
            with self.assertRaises(ValueError):
                with worker.claim(): pass
            worker.lock_path.chmod(0o600)
            os.link(database, Path(folder) / "alias")
            with self.assertRaises(ValueError):
                with worker.claim(): pass
            other = Path(folder) / "other"
            other.touch()
            linked = LocalWorker(other)
            linked.lock_path.symlink_to(worker.lock_path)
            with self.assertRaises(OSError):
                with linked.claim(): pass

    def test_memory_reentrance_and_inherited_identity_rejected(self):
        worker = LocalWorker(":memory:")
        with worker.claim():
            with self.assertRaises(ValueError):
                with worker.claim(): pass
        worker.pid = -1
        with self.assertRaises(ValueError):
            with worker.claim(): pass


if __name__ == "__main__":
    import argparse
    from app.g5.world import canonical
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    async def evidence():
        case = WorkerTests()
        try:
            await case.asyncSetUp()
            await case.test_real_process_lock_competition_and_death_before_or_after_commit()
            raw = {"schema": "g5-local-worker-recovery-evidence-v1", "real_model_calls": 0,
                "scope": "Cooperating processes, private local Unix storage only", "cases": case.process_evidence}
            raw["sha256"] = digest(raw)
            directory = Path(args.output_dir)
            directory.mkdir(mode=0o700, exist_ok=False)
            with os.fdopen(os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                stream.write(canonical(raw)); stream.flush(); os.fsync(stream.fileno())
            print(json.dumps({"sha256": raw["sha256"], "cases": len(raw["cases"])}))
        finally:
            case.doCleanups()
    asyncio.run(evidence())
