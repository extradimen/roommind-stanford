"""Fixed classifier and interrupted-ledger fixtures; no external calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_g5_annotation_archive as fixtures
from app.factorial_study import digest
from app.g5.annotation_archive import AnnotationArchive, freeze_plan
from app.g5.calibration_predictor import ModelPredictor
from app.g5.prediction_archive import PredictionArchive, verify_export
from app.g5.calibration_bridge import report
from app.g5.model_policy import ModelBinding, Completion


class PredictionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.AnnotationTests.asyncSetUp(self)
        plan = copy.deepcopy(self.frozen["plan"])
        plan["cases"] = plan["cases"][::6]
        reference = AnnotationArchive(":memory:", self.manifest, self.sources, freeze_plan(plan))
        for case in plan["cases"]:
            for who in range(2):
                reference.append(fixtures.AnnotationTests.row(self, case["id"], who))
        self.annotation = reference.export()
        reference.close()
        self.mode, self.requests = "ok", []
        async def transport(request):
            self.requests.append(copy.deepcopy(request))
            if self.mode == "timeout":
                raise TimeoutError("private transport failure text")
            if self.mode == "cancel":
                raise KeyboardInterrupt()
            content = json.dumps({"prediction": "abstain" if self.mode == "abstain" else "clear", "rationale": "Synthetic response."})
            if self.mode == "malformed":
                content = '{"prediction":"clear","prediction":"violation","rationale":"x"}'
            return Completion(content, "wrong" if self.mode == "wrong" else "offline", "fixed", "mock", digest(request), "stop")
        self.predictor = ModelPredictor(ModelBinding("offline", "fixed", "mock", .2, 2048), transport,
            predictor_id="synthetic-predictor", kind="synthetic")
        self.plan = self.predictor.plan()

    async def test_full_panel_raw_receipts_bridge_and_no_labels_in_input(self):
        archive = PredictionArchive(":memory:", self.annotation, self.plan)
        self.addCleanup(archive.close)
        self.assertEqual(len([r async for r in archive.run_missing(self.predictor)]), 4)
        self.assertEqual([r async for r in archive.run_missing(self.predictor)], [])
        self.assertEqual(len(self.requests), 4)
        for request in self.requests:
            body = json.loads(request["messages"][1]["content"])
            self.assertEqual(set(body), {"dimension", "rubric", "context", "turns"})
            self.assertNotIn("case_id", body)
            self.assertNotIn("label", body)
        self.exported = archive.export()
        self.assertEqual(verify_export(self.exported)["pending_indeterminate"], 0)
        self.assertEqual(report(self.annotation, self.exported["results"])["overall"]["tn"], 4)

    async def test_failure_retry_preserves_raw_and_abstention_is_terminal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "prediction.sqlite")
            archive = PredictionArchive(path, self.annotation, self.plan)
            self.mode = "timeout"
            stream = archive.run_missing(self.predictor)
            first = await anext(stream)
            await stream.aclose()
            self.assertNotIn("private transport", json.dumps(first))
            archive.close()
            archive = PredictionArchive(path, self.annotation, self.plan)
            try:
                self.mode = "abstain"
                self.assertEqual(len([r async for r in archive.run_missing(self.predictor)]), 4)
                result = archive.export()
                self.assertEqual(len(result["results"]["attempts"]), 5)
                self.assertEqual(result["results"]["attempts"][1]["previous_attempt_sha256"], digest(first))
                self.assertEqual([r async for r in archive.run_missing(self.predictor)], [])
                self.assertEqual(report(self.annotation, result["results"])["overall"]["prediction_abstain"], 4)
            finally:
                archive.close()

    async def test_invalid_receipt_and_malformed_response_are_not_semantic_labels(self):
        task = self.archive.task(self.frozen["plan"]["cases"][0]["id"])
        for mode in ("wrong", "malformed"):
            self.mode = mode
            result = await self.predictor.predict(task, self.plan, attempt_id=mode)
            self.assertEqual(result["artifact"]["output"]["status"], "technical_failure")
            self.assertIsNotNone(result["artifact"]["raw_record"]["response"])
        self.mode = "ok"
        result = await self.predictor.predict(task, self.plan, attempt_id="ok")
        from app.g5.calibration_predictor import validate_receipt
        result["artifact"]["output"]["prediction"] = "violation"
        with self.assertRaises(ValueError):
            validate_receipt(result, self.plan)
        count = len(self.requests)
        self.predictor.predictor_id = "changed"
        with self.assertRaises(ValueError):
            await self.predictor.predict(task, self.plan, attempt_id="drift")
        self.assertEqual(len(self.requests), count)

    async def test_cancellation_preserves_indeterminate_requires_explicit_recovery(self):
        archive = PredictionArchive(":memory:", self.annotation, self.plan)
        self.addCleanup(archive.close)
        self.mode = "cancel"
        stream = archive.run_missing(self.predictor)
        with self.assertRaises(KeyboardInterrupt):
            await anext(stream)
        await stream.aclose()
        saved = archive.export()
        self.assertEqual(len(saved["pending_indeterminate"]), 1)
        self.assertEqual(saved["results"]["attempts"], [])
        self.mode = "ok"
        calls = len(self.requests)
        for invalid in ("false", "true", 1, 0, None):
            with self.subTest(resume_pending=invalid), self.assertRaises(ValueError):
                [r async for r in archive.run_missing(self.predictor, resume_pending=invalid)]
        self.assertEqual(len(self.requests), calls)
        with self.assertRaises(ValueError):
            [r async for r in archive.run_missing(self.predictor)]
        self.assertEqual(len([r async for r in archive.run_missing(self.predictor, resume_pending=True)]), 4)
        self.assertEqual(archive.export()["results"]["attempts"][0]["id"], saved["pending_indeterminate"][0]["id"])

    async def test_one_full_validation_per_snapshot_and_idempotent_append(self):
        from app.g5 import prediction_archive as module
        archive = PredictionArchive(":memory:", self.annotation, self.plan)
        self.addCleanup(archive.close)
        stream = archive.run_missing(self.predictor)
        await anext(stream)
        await stream.aclose()
        saved = archive.export()
        for operation in (archive.export, lambda: archive.append(saved["events"][0])):
            with patch.object(module, "freeze_results", wraps=module.freeze_results) as verify:
                operation()
            self.assertEqual(verify.call_count, 1)
        self.assertEqual(archive.export(), saved)
        self.assertEqual(verify_export(saved)["pending_indeterminate"], 0)

    async def test_rehashed_invalid_history_rejected_on_export_and_both_append_paths(self):
        from app.g5.world import canonical
        archive = PredictionArchive(":memory:", self.annotation, self.plan)
        self.addCleanup(archive.close)
        case = self.annotation["plan"]["plan"]["cases"][0]
        invalid = {"phase": "started", "value": {"id": "forged", "case_id": case["id"],
            "previous_attempt_sha256": None, "request_sha256": "0" * 64}}
        # Even a syntactically valid, rehashed INSERT cannot bypass semantics.
        archive.db.execute("INSERT INTO prediction_events VALUES(1,?,?)", (
            canonical(invalid), digest([digest(archive.header), 1, invalid])))
        different = copy.deepcopy(invalid)
        different["value"]["id"] = "another"
        for operation in (archive.export, lambda: archive.append(invalid), lambda: archive.append(different)):
            with self.assertRaises(ValueError):
                operation()
            self.assertFalse(archive.db.in_transaction)
            self.assertEqual(archive.db.execute("SELECT COUNT(*) FROM prediction_events").fetchone()[0], 1)

    async def test_real_process_death_inside_result_commit_and_after_ack(self):
        case = self.annotation["plan"]["plan"]["cases"][0]
        task = self.archive.task(case["id"])
        result = await self.predictor.predict(task, self.plan, attempt_id="crash-attempt")
        from app.g5.calibration_predictor import request_for
        start = {"id": result["id"], "case_id": case["id"], "previous_attempt_sha256": None,
                 "request_sha256": digest(request_for(task, self.plan["model_spec"]))}
        child = '''
import json,os,sys
from app.g5.prediction_archive import PredictionArchive
d=json.load(open(sys.argv[1]))
a=PredictionArchive(sys.argv[2],d['annotation'],d['plan'])
a.append({'phase':'started','value':d['start']})
if sys.argv[3]=='inside':
 a.db.set_trace_callback(lambda sql: os._exit(75) if sql=='COMMIT' else None)
a.append({'phase':'finished','value':d['result']})
os._exit(74)
'''
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.json"
            source.write_text(json.dumps({"annotation": self.annotation, "plan": self.plan, "start": start, "result": result}))
            for mode in ("inside", "after"):
                path = str(Path(folder) / (mode + ".sqlite"))
                completed = subprocess.run([sys.executable, "-c", child, str(source), path, mode], capture_output=True, timeout=20)
                self.assertEqual(completed.returncode, 75 if mode == "inside" else 74, completed.stderr.decode())
                archive = PredictionArchive(path, self.annotation, self.plan)
                try:
                    self.assertEqual(len(archive.export()["pending_indeterminate"]), 1 if mode == "inside" else 0)
                    self.assertEqual(len([r async for r in archive.run_missing(self.predictor, resume_pending=True)]), 4 if mode == "inside" else 3)
                    self.assertEqual(len(archive.export()["results"]["attempts"]), 4)
                finally:
                    archive.close()


if __name__ == "__main__":
    import argparse, asyncio, os
    from app.g5.world import canonical
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700, exist_ok=False)
    async def run():
        case = PredictionTests()
        try:
            await case.asyncSetUp()
            await case.test_full_panel_raw_receipts_bridge_and_no_labels_in_input()
            raw = {"schema": "g5-synthetic-prediction-panel-v1", "real_model_calls": 0, "ledger": case.exported,
                   "report": report(case.annotation, case.exported["results"])}
            raw["sha256"] = digest(raw)
            fd = os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical(raw)); stream.flush(); os.fsync(stream.fileno())
            print({"sha256": raw["sha256"], "predictions": len(case.exported["results"]["attempts"])})
        finally:
            case.doCleanups()
    asyncio.run(run())
