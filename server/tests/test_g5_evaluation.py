"""Blinded adapter tests use only synthetic completions, never a live judge."""
import copy
import json
import unittest
import tempfile
import sqlite3
import subprocess
import sys

from app.factorial_study import ARMS, digest, freeze_design
from app.g5.evaluation import ModelEvaluator, prepare_packet
from app.g5.evaluation_archive import EvaluationArchive
from app.g5.measurement import DIMENSIONS, freeze_analysis, index_scores
from app.g5.model_policy import ModelBinding, Completion
from app.g5.world import World, Decision, Conflict
from test_g5_composed_runtime import Harness
from test_g5_measurement import fixtures


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.world = World(":memory:")
        self.addCleanup(self.world.close)
        self.calls = []
        self.mode = "ok"
        async def transport(request):
            self.calls.append(copy.deepcopy(request))
            if self.mode == "timeout":
                raise TimeoutError("secret text must not enter failure rationale")
            data = json.loads(request["messages"][1]["content"])
            turn = data["turns"][0]
            value = {"status": "completed", "score": 4, "quotes": [{"turn_id": turn["id"],
                "start": 0, "end": len(turn["text"]), "text": turn["text"]}], "rationale": "Synthetic reference score."}
            if self.mode == "bad_quote":
                value["quotes"][0]["text"] = "invented"
            elif self.mode == "na":
                value.update(status="not_applicable", score=None, quotes=[], rationale="Synthetic N/A control.")
            return Completion(json.dumps(value), "other" if self.mode == "bad_receipt" else "offline",
                              "fixed", "mock", digest(request), "stop")
        self.rubric = {d: "Synthetic rubric: assess this dimension, not task completion." for d in DIMENSIONS}
        self.evaluator = ModelEvaluator(ModelBinding("offline", "fixed", "mock", .2, 2048), transport,
            rubric=self.rubric, judge_id="synthetic-independent", judge_kind="synthetic")
        self.harness = Harness()
        config = fixtures(1)[1]["config"]
        config.update(judge=self.evaluator.judge(), rubric_sha256=digest(self.rubric))
        self.plan = freeze_analysis(config)
        design = self.harness.frozen["design"]
        design["analysis_plan_sha256"] = self.plan["sha256"]
        design["sample_size_plan_sha256"] = config["sample_size_plan_sha256"]
        for profile in design["arms"].values():
            profile["shared"]["evaluator_plan_sha256"] = self.plan["sha256"]
        self.manifest = freeze_design(design)
        self.harness.frozen = self.manifest

    async def packet(self, arm="D"):
        runtime = self.harness.runtime(self.world, arm)
        for _ in range(4):
            await runtime.step()
        self.world.freeze(arm)
        return await prepare_packet(self.world, arm, self.manifest)

    async def test_four_arms_common_context_blinded_input_and_source_artifact(self):
        packets = [await self.packet(arm) for arm in ARMS]
        for packet in packets:
            self.assertEqual(packet["context"], packets[0]["context"])
            result = await self.evaluator.evaluate(self.manifest, self.plan, packet, DIMENSIONS[0], attempt_id=str(packet["transcript"]["ordinal"]))
            self.assertEqual(result["attempt"]["artifact_sha256"], digest(result["artifact"]))
            self.assertEqual(result["attempt"]["judge"]["kind"], "synthetic")
            data = json.loads(self.calls[-1]["messages"][1]["content"])
            self.assertEqual(set(data), {"context", "turns", "dimension", "rubric", "semantic_contract"})
            self.assertEqual(set(data["context"]), {"initial_world", "roles", "observation_policy"})
            for field in ("cognition_state", "revision_feedback", "manifest_sha256", "ordinal", "governance_called"):
                self.assertNotIn(field, canonical_data(data))
            index_scores(self.manifest, self.plan, [packet["transcript"]], [result["attempt"]])

    async def test_missing_stream_resume_skips_completed_and_keeps_artifacts(self):
        packet = await self.packet()
        self.mode = "timeout"
        failed = await self.evaluator.evaluate(self.manifest, self.plan, packet, DIMENSIONS[0], attempt_id="failure")
        self.assertEqual(failed["attempt"]["status"], "technical_failure")
        self.assertNotIn("secret text", failed["attempt"]["rationale"])
        self.mode = "ok"
        attempts = [failed["attempt"]]
        artifacts = [failed["artifact"]]
        stream = self.evaluator.missing_evaluations(self.manifest, self.plan, [packet], attempts)
        first = await anext(stream)
        attempts.append(first["attempt"])
        artifacts.append(first["artifact"])
        await stream.aclose()
        count = len(self.calls)
        async for item in self.evaluator.missing_evaluations(self.manifest, self.plan, [packet], attempts):
            attempts.append(item["attempt"])
            artifacts.append(item["artifact"])
        self.assertEqual(len(self.calls) - count, 5)
        _, indexed = index_scores(self.manifest, self.plan, [packet["transcript"]], attempts)
        self.assertEqual(len(indexed), 6)
        self.assertTrue(all(r["status"] == "completed" for r in indexed.values()))
        self.assertEqual(len(artifacts), 7)
        self.assertEqual([x async for x in self.evaluator.missing_evaluations(self.manifest, self.plan, [packet], attempts)], [])

    async def test_invalid_quotes_receipt_and_na_are_not_passes(self):
        packet = await self.packet()
        for mode in ("bad_quote", "bad_receipt", "na"):
            self.mode = mode
            result = await self.evaluator.evaluate(self.manifest, self.plan, packet, DIMENSIONS[0], attempt_id=mode)
            expected = "not_applicable" if mode == "na" else "technical_failure"
            self.assertEqual(result["attempt"]["status"], expected)
            self.assertIsNone(result["attempt"]["score"])
            self.assertIsNotNone(result["artifact"]["response"])

    async def test_context_forgery_and_judge_drift_rejected_before_call(self):
        packet = await self.packet()
        changed = copy.deepcopy(packet)
        changed["context"]["roles"]["sre"]["private"]["goals"] = ["forged goal"]
        changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
        with self.assertRaises(ValueError):
            await self.evaluator.evaluate(self.manifest, self.plan, changed, DIMENSIONS[0], attempt_id="bad")
        self.evaluator.rubric[DIMENSIONS[0]] = "Changed rubric"
        with self.assertRaises(ValueError):
            await self.evaluator.evaluate(self.manifest, self.plan, packet, DIMENSIONS[0], attempt_id="drift")
        self.assertEqual(self.calls, [])

    async def test_running_dialogue_and_changing_snapshot_rejected(self):
        runtime = self.harness.runtime(self.world, "D")
        await runtime.step()
        with self.assertRaises(ValueError):
            await prepare_packet(self.world, "D", self.manifest)
        for _ in range(3):
            await runtime.step()
        with self.assertRaises(ValueError):
            await prepare_packet(self.world, "D", self.manifest)
        self.world.freeze("D")
        before = self.world.events("D")
        with self.assertRaises(Conflict):
            self.world.commit("D", expected_version=4, request_id="injected-concurrent-event", actor="sre",
                              decision=Decision("wait"), audit={})
        self.assertEqual((await prepare_packet(self.world, "D", self.manifest))["source_events_sha256"], digest(before))

    async def test_archive_all_assignments_required_and_restart_preserves_failure_and_scores(self):
        packets = [await self.packet(arm) for arm in ARMS]
        with tempfile.TemporaryDirectory(prefix="g5_evaluation_") as directory:
            path = directory + "/evaluation.sqlite"
            with self.assertRaises(ValueError):
                EvaluationArchive(path, self.manifest, self.plan, packets[:1])
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            self.mode = "timeout"
            stream = archive.evaluate_missing(self.evaluator)
            failed = await anext(stream)
            await stream.aclose()
            self.assertEqual(failed["attempt"]["status"], "technical_failure")
            archive.close()
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            try:
                self.mode = "ok"
                stream = archive.evaluate_missing(self.evaluator)
                first = await anext(stream)
                await stream.aclose()
                self.assertEqual(archive.append(first), first)  # lost acknowledgement
                with self.assertRaises(sqlite3.IntegrityError):
                    archive.db.execute("DELETE FROM evaluation_results")
                remaining = [r async for r in archive.evaluate_missing(self.evaluator)]
                self.assertEqual(len(remaining), 23)
                self.assertEqual(len(archive.results()), 25)
                self.assertEqual(archive.results()[0], failed)
                calls = len(self.calls)
                self.assertEqual([r async for r in archive.evaluate_missing(self.evaluator)], [])
                self.assertEqual(len(self.calls), calls)
                export = archive.export()
                self.assertEqual(export["sha256"], digest({k: v for k, v in export.items() if k != "sha256"}))
                self.assertEqual(export["results"][1], first)
            finally:
                archive.close()

    async def test_archive_rejects_score_edit_and_conflicting_completed_writer(self):
        packets = [await self.packet(arm) for arm in ARMS]
        with tempfile.TemporaryDirectory(prefix="g5_evaluation_") as directory:
            path = directory + "/evaluation.sqlite"
            one = EvaluationArchive(path, self.manifest, self.plan, packets)
            two = EvaluationArchive(path, self.manifest, self.plan, packets)
            try:
                result = await self.evaluator.evaluate(self.manifest, self.plan, packets[0], DIMENSIONS[0], attempt_id="first")
                changed = copy.deepcopy(result)
                changed["attempt"]["score"] = 5
                with self.assertRaises(ValueError):
                    one.append(changed)
                one.append(result)
                changed = copy.deepcopy(result)
                changed["attempt"]["id"] = "second"
                with self.assertRaises(ValueError):
                    two.append(changed)
                self.assertEqual(two.results(), [result])
                self.assertEqual(two.append(result), result)
            finally:
                one.close()
                two.close()

    async def test_archive_transaction_failure_rolls_back_and_rehashed_source_change_rejected(self):
        packets = [await self.packet(arm) for arm in ARMS]
        with tempfile.TemporaryDirectory(prefix="g5_evaluation_") as directory:
            path = directory + "/evaluation.sqlite"
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            result = await self.evaluator.evaluate(self.manifest, self.plan, packets[0], DIMENSIONS[0], attempt_id="retry-save")
            try:
                archive.db.execute("CREATE TRIGGER injected_failure AFTER INSERT ON evaluation_results BEGIN SELECT RAISE(ABORT,'synthetic storage failure'); END")
                with self.assertRaises(sqlite3.IntegrityError):
                    archive.append(result)
                self.assertEqual(archive.results(), [])
                archive.db.execute("DROP TRIGGER injected_failure")
                archive.append(result)
                changed = copy.deepcopy(packets)
                changed[0]["seal"]["world_id"] = "another-instance"
                changed[0]["seal"]["sha256"] = digest({k: v for k, v in changed[0]["seal"].items() if k != "sha256"})
                changed[0]["sha256"] = digest({k: v for k, v in changed[0].items() if k != "sha256"})
                with self.assertRaises(ValueError):
                    EvaluationArchive(path, self.manifest, self.plan, changed)
                self.assertEqual(archive.results(), [result])
            finally:
                archive.close()

    async def test_archive_real_process_exit_before_and_after_commit(self):
        packets = [await self.packet(arm) for arm in ARMS]
        with tempfile.TemporaryDirectory(prefix="g5_evaluation_") as directory:
            path = directory + "/evaluation.sqlite"
            archive = EvaluationArchive(path, self.manifest, self.plan, packets)
            archive.close()
            result = await self.evaluator.evaluate(self.manifest, self.plan, packets[0], DIMENSIONS[0], attempt_id="process-save")
            child = '''import json, os, sqlite3, sys
from app.g5.evaluation_archive import EvaluationArchive
from app.factorial_study import digest
from app.g5.world import canonical
path, mode = sys.argv[1:]
data = json.load(sys.stdin)
a = EvaluationArchive(path, data["manifest"], data["plan"], data["packets"])
if mode == "before":
    a.db.execute("BEGIN IMMEDIATE")
    value = data["result"]
    chain = digest({"previous": digest(a.header), "seq": 1, "result": value})
    a.db.execute("INSERT INTO evaluation_results VALUES(?,?,?,?)", (1,value["attempt"]["id"],canonical(value),chain))
else:
    a.append(data["result"])
os._exit(29)
'''
            for mode, expected in (("before", []), ("after", [result])):
                process = subprocess.run([sys.executable, "-c", child, path, mode], input=json.dumps({
                    "manifest": self.manifest, "plan": self.plan, "packets": packets, "result": result}),
                    text=True, capture_output=True, timeout=15)
                self.assertEqual(process.returncode, 29, process.stderr)
                archive = EvaluationArchive(path, self.manifest, self.plan, packets)
                try:
                    self.assertEqual(archive.results(), expected)
                    if mode == "after":
                        self.assertEqual(archive.append(result), result)
                        self.assertEqual(len(archive.results()), 1)
                finally:
                    archive.close()

    async def test_release_cross_checks_all_sources_and_reports_incomplete_then_terminal(self):
        from app.g5.release import evidence_bundle, verify_evidence, write_evidence
        from pathlib import Path
        packets = [await self.packet(arm) for arm in ARMS]
        sources = [self.world.export_source(arm) for arm in ARMS]
        archive = EvaluationArchive(":memory:", self.manifest, self.plan, packets)
        try:
            initial = evidence_bundle(sources, archive.export())
            self.assertEqual(verify_evidence(initial)["dimension_outcomes"]["missing"], 24)
            self.assertFalse(verify_evidence(initial)["evaluation_terminal"])
            self.mode = "na"
            first = archive.evaluate_missing(self.evaluator)
            await anext(first)
            await first.aclose()
            self.mode = "ok"
            rows = [r async for r in archive.evaluate_missing(self.evaluator)]
            self.assertEqual(len(rows), 23)
            bundle = evidence_bundle(sources, archive.export())
            summary = verify_evidence(bundle)
            self.assertEqual(summary["dimension_outcomes"], {"completed": 23, "not_applicable": 1, "technical_failure": 0, "missing": 0})
            self.assertTrue(summary["evaluation_terminal"])
            self.assertEqual(summary["qualification"], "not_inferred")
            with tempfile.TemporaryDirectory(prefix="g5_release_") as directory:
                path = Path(directory) / "evidence.json"
                write_evidence(path, bundle)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    write_evidence(path, bundle)
                process = subprocess.run([sys.executable, "-m", "app.g5.release", str(path)], text=True, capture_output=True, timeout=15)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout), summary)
                self.assertEqual(json.loads(path.read_text()), bundle)
        finally:
            archive.close()

    async def test_release_rejects_rehashed_source_or_evaluator_substitution(self):
        from app.g5.release import evidence_bundle, verify_evidence
        packets = [await self.packet(arm) for arm in ARMS]
        sources = [self.world.export_source(arm) for arm in ARMS]
        archive = EvaluationArchive(":memory:", self.manifest, self.plan, packets)
        try:
            bundle = evidence_bundle(sources, archive.export())
            for mutation in ("missing", "duplicate", "source_hash", "packet_substitution"):
                changed = copy.deepcopy(bundle)
                if mutation == "missing":
                    changed["sources"].pop()
                elif mutation == "duplicate":
                    changed["sources"][1] = copy.deepcopy(changed["sources"][0])
                elif mutation == "source_hash":
                    changed["sources"][0]["events"][0]["payload"]["decision"]["content"] = "Altered text"
                else:
                    changed["evaluation"]["packets"][0]["transcript"]["turns"][0]["text"] = "Wrong transcript"
                changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
                with self.assertRaises(ValueError):
                    verify_evidence(changed)
        finally:
            archive.close()

    async def test_source_rejects_rehashed_invented_simulation_receipt(self):
        from app.g5.artifacts import verify_source
        from app.g5.freezing import make_freeze
        from app.g5.world import Snapshot
        await self.packet("D")
        source = self.world.export_source("D")
        source["events"][0]["payload"]["receipt"] = {"status": "success", "effects": {"invented": True}}
        previous = digest([source["world_id"], source["spec"], source["binding"]])
        for event in source["events"]:
            event["event_id"] = digest([source["world_id"], event["seq"], event["request_id"], event["request_hash"], previous, event["payload"]])
            previous = event["event_id"]
        source["seal"] = make_freeze(Snapshot(source["world_id"], source["spec"], source["binding"], source["events"]))
        source["sha256"] = digest({k: v for k, v in source.items() if k != "sha256"})
        with self.assertRaisesRegex(ValueError, "Receipt/effects/visibility"):
            verify_source(source, self.manifest)


def canonical_data(value):
    return json.dumps(value, sort_keys=True)
