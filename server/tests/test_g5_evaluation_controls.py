"""Frozen scoring controls, using synthetic completions only."""
import copy
import json
import tempfile
import unittest
from dataclasses import replace

import test_g5_evaluation as fixtures
from app.factorial_study import ARMS, digest, freeze_design
from app.g5.evaluation_archive import EvaluationArchive
from app.g5.evaluation_controls import cells, schedule, request_for, diagnostic_report
from app.g5.measurement import freeze_analysis, DIMENSIONS


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.EvaluationTests.asyncSetUp(self)
        config = copy.deepcopy(self.plan["config"])
        config["evaluation_controls"] = {"schema": "g5-evaluation-controls-v1",
            "presentations": ["compact-json", "indented-json"], "orders": ["forward", "reverse"],
            "repetitions": 2, "seed": 20260911}
        self.plan = freeze_analysis(config)
        design = self.manifest["design"]
        design["analysis_plan_sha256"] = self.plan["sha256"]
        for profile in design["arms"].values():
            profile["shared"]["evaluator_plan_sha256"] = self.plan["sha256"]
        self.manifest = freeze_design(design)
        self.harness.frozen = self.manifest
        self.packets = [await fixtures.EvaluationTests.packet(self, arm) for arm in ARMS]
        self.cells = cells(config["evaluation_controls"])

    async def test_whole_panel_interruption_resume_and_foreign_input_rejection(self):
        from app.g5.evaluation_controls import evaluate_panel
        with tempfile.TemporaryDirectory() as directory:
            stream = evaluate_panel(directory, self.evaluator, self.manifest, self.plan, self.packets)
            first = await anext(stream)
            await stream.aclose()
            self.assertEqual(len(self.calls), 1)
            results = [r async for r in evaluate_panel(directory, self.evaluator, self.manifest, self.plan, self.packets)]
            self.assertEqual(len(results), 191)
            self.assertNotIn(first["result"]["attempt"]["id"], [r["result"]["attempt"]["id"] for r in results])
            self.assertEqual([r async for r in evaluate_panel(directory, self.evaluator, self.manifest, self.plan, self.packets)], [])
            changed = copy.deepcopy(self.plan["config"])
            changed["evaluation_controls"]["seed"] += 1
            with self.assertRaises(ValueError):
                [r async for r in evaluate_panel(directory, self.evaluator, self.manifest, freeze_analysis(changed), self.packets)]
            self.assertEqual(len(self.calls), 192)

    async def test_lossless_format_and_reverse_order_without_condition_metadata(self):
        for cell in self.cells:
            jobs = schedule(self.plan, self.packets, cell)
            self.assertEqual(len(jobs), 24)
            other = {**cell, "order": "reverse" if cell["order"] == "forward" else "forward"}
            self.assertEqual(jobs, list(reversed(schedule(self.plan, self.packets, other))))
            packet, dimension = jobs[0]
            request = request_for(self.evaluator.runtime_specification(), packet, dimension, self.rubric, cell)
            content = json.loads(request["messages"][1]["content"])
            self.assertEqual(content["turns"], packet["transcript"]["turns"])
            self.assertEqual(
                set(content),
                {"context", "turns", "dimension", "rubric", "semantic_contract"},
            )
            self.assertNotIn("control", content)
            self.assertNotIn("ordinal", content)
            self.assertEqual(len(request["messages"]), 2)

    async def test_complete_panel_detects_injected_format_bias_and_no_repeat_pseudoreplication(self):
        original = self.evaluator.transport
        async def synthetic_bias(request):
            response = await original(request)
            value = json.loads(response.content)
            value["score"] = 5 if "\n" in request["messages"][1]["content"] else 4
            return replace(response, content=json.dumps(value))
        self.evaluator.transport = synthetic_bias
        exports = []
        for cell in self.cells:
            archive = EvaluationArchive(":memory:", self.manifest, self.plan, self.packets, control=cell)
            try:
                self.assertEqual(len([r async for r in archive.evaluate_missing(self.evaluator)]), 24)
                self.assertEqual([r async for r in archive.evaluate_missing(self.evaluator)], [])
                exports.append(archive.export())
            finally:
                archive.close()
        report = diagnostic_report(self.manifest, self.plan, self.packets, exports)
        self.assertTrue(report["all_terminal"])
        self.assertEqual(len(self.calls), 192)
        for comparison in report["comparisons"]:
            self.assertEqual(comparison["paired_completed"], 4)
            self.assertEqual(comparison["unpaired"], 0)
            self.assertEqual(comparison["mean_absolute_difference"], 1 if comparison["factor"] == "presentation" else 0)
        sources = [self.world.export_source(arm) for arm in ARMS]
        from app.g5.release import evidence_bundle, verify_evidence
        self.assertTrue(verify_evidence(evidence_bundle(sources, exports[0]))["evaluation_terminal"])
        self.panel = {"manifest": self.manifest, "plan": self.plan, "packets": self.packets, "sources": sources,
                      "exports": exports, "diagnostics": report}

    async def test_restart_missing_dimensions_technical_failure_and_cell_isolation(self):
        cell = self.cells[0]
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/control.sqlite"
            archive = EvaluationArchive(path, self.manifest, self.plan, self.packets, control=cell)
            self.mode = "timeout"
            stream = archive.evaluate_missing(self.evaluator)
            failed = await anext(stream)
            await stream.aclose()
            self.assertEqual(failed["attempt"]["status"], "technical_failure")
            archive.close()
            with self.assertRaises(ValueError):
                EvaluationArchive(path, self.manifest, self.plan, self.packets, control=self.cells[1])
            archive = EvaluationArchive(path, self.manifest, self.plan, self.packets, control=cell)
            try:
                self.mode = "ok"
                stream = archive.evaluate_missing(self.evaluator)
                first = await anext(stream)
                await stream.aclose()
                self.assertEqual(archive.append(first), first)
                self.assertEqual(len([r async for r in archive.evaluate_missing(self.evaluator)]), 23)
                self.assertEqual(len(archive.results()), 25)
                report = diagnostic_report(self.manifest, self.plan, self.packets, [archive.export()])
                self.assertFalse(report["all_terminal"])
                self.assertEqual(sum(c["outcomes"]["missing"] for c in report["cells"]), 168)
                self.assertEqual(sum(c["technical_failure_attempts"] for c in report["cells"]), 1)
            finally:
                archive.close()

    async def test_reject_unfrozen_cell_wrong_order_and_rehashed_cross_cell_result(self):
        with self.assertRaises(ValueError):
            EvaluationArchive(":memory:", self.manifest, self.plan, self.packets)
        config = copy.deepcopy(self.plan["config"])
        config["evaluation_controls"]["repetitions"] = True
        with self.assertRaises(ValueError):
            freeze_analysis(config)
        cell = self.cells[0]
        archive = EvaluationArchive(":memory:", self.manifest, self.plan, self.packets, control=cell)
        self.addCleanup(archive.close)
        jobs = schedule(self.plan, self.packets, cell)
        packet, dimension = jobs[1]
        wrong = await self.evaluator.evaluate(self.manifest, self.plan, packet, dimension, attempt_id="wrong-order", control=cell)
        with self.assertRaisesRegex(ValueError, "order"):
            archive.append(wrong)
        packet, dimension = jobs[0]
        foreign = await self.evaluator.evaluate(self.manifest, self.plan, packet, dimension, attempt_id="other", control=self.cells[-1])
        with self.assertRaisesRegex(ValueError, "control mismatch"):
            archive.append(foreign)
        foreign["artifact"]["control"] = cell
        foreign["attempt"]["artifact_sha256"] = digest(foreign["artifact"])
        with self.assertRaisesRegex(ValueError, "request was altered"):
            archive.append(foreign)
        self.assertEqual(archive.results(), [])


if __name__ == "__main__":
    import argparse
    import asyncio
    import os
    from pathlib import Path
    from app.g5.world import canonical
    parser = argparse.ArgumentParser(description="Synthetic scoring-control evidence; no external calls")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700, exist_ok=False)
    async def run():
        case = ControlTests()
        try:
            await case.asyncSetUp()
            await case.test_complete_panel_detects_injected_format_bias_and_no_repeat_pseudoreplication()
            raw = {"schema": "g5-synthetic-evaluation-control-panel-v1", "real_model_calls": 0,
                   "injected_bias": "indented=5,compact=4", **case.panel}
            raw["sha256"] = digest(raw)
            fd = os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical(raw))
                stream.flush()
                os.fsync(stream.fileno())
            print({"sha256": raw["sha256"], "calls": len(case.calls), "all_terminal": raw["diagnostics"]["all_terminal"]})
        finally:
            case.doCleanups()
    asyncio.run(run())
