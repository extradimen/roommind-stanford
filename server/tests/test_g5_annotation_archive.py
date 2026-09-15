"""Synthetic independent-label/adjudication audit, not human calibration."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import test_g5_evaluation as fixtures
from app.factorial_study import ARMS, digest
from app.g5.annotation_archive import AnnotationArchive, freeze_plan, verify_export
from app.g5.measurement import DIMENSIONS


class AnnotationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.EvaluationTests.asyncSetUp(self)
        for arm in ARMS:
            await fixtures.EvaluationTests.packet(self, arm)
        self.sources = [self.world.export_source(arm) for arm in ARMS]
        self.raters = [{"id": "rater-1", "kind": "synthetic"}, {"id": "rater-2", "kind": "synthetic"}]
        self.adjudicator = {"id": "referee", "kind": "synthetic"}
        self.frozen = freeze_plan({"schema": "g5-independent-annotation-plan-v1", "raters": self.raters,
            "adjudicator": self.adjudicator, "cases": [{"id": f"case-{i}-{j}", "ordinal": i,
            "dimension": dim, "category": "synthetic-positive-control", "rubric": "Synthetic label control, not a scientific gold standard."}
            for i in range(1, 5) for j, dim in enumerate(DIMENSIONS)]})
        self.archive = AnnotationArchive(":memory:", self.manifest, self.sources, self.frozen)
        self.addCleanup(self.archive.close)

    def row(self, case="case-1-0", who=0, label="clear", phase="independent", based_on=None):
        task = self.archive.task(case)
        turn = task["turns"][0]
        person = self.raters[who] if phase == "independent" else self.adjudicator
        return {"id": case + "-" + person["id"], "case_id": case, "phase": phase,
            "annotator": person, "task_sha256": task["sha256"], "label": label,
            "quotes": [{"turn_id": turn["id"], "start": 0, "end": len(turn["text"]), "text": turn["text"]}],
            "rationale": "Synthetic annotation for audit validation.", "artifact": {"fixture": "scripted-label"},
            "based_on": based_on or []}

    async def test_full_six_dimension_four_source_panel_preserves_disagreement_and_provenance(self):
        for index, case in enumerate(self.frozen["plan"]["cases"]):
            first = self.row(case["id"])
            second = self.row(case["id"], 1, "violation" if index % 3 == 0 else "clear")
            self.archive.append(first)
            self.archive.append(second)
            if index % 3 == 0:
                report = self.archive.report()
                self.assertEqual(next(c for c in report["cases"] if c["case_id"] == case["id"])["status"], "disputed")
                prepared = self.archive.adjudication_task(case["id"])
                self.assertEqual(prepared["original_labels"], [first, second])
                self.archive.append(self.row(case["id"], label="uncertain", phase="adjudication",
                    based_on=prepared["based_on"]))
        self.exported = self.archive.export()
        report = verify_export(self.exported)
        self.assertTrue(report["all_resolved"])
        self.assertEqual(len(report["cases"]), 24)
        self.assertEqual(sum(c["independent_disagreement"] for c in report["cases"]), 8)
        self.assertEqual(len(self.exported["rows"]), 56)
        self.assertEqual({r["label_source"] for r in report["resolved_label_records"]["labels"]}, {"synthetic"})
        self.assertEqual(report["human_authentication"], "not_established")

    async def test_blind_task_missing_raters_and_no_implicit_consensus(self):
        before = self.archive.task("case-1-0")
        self.assertEqual(set(before), {"schema", "classification", "case_id", "dimension", "rubric", "context", "turns", "sha256"})
        self.archive.append(self.row())
        self.assertEqual(self.archive.task("case-1-0"), before)
        result = self.archive.report()
        self.assertFalse(result["all_resolved"])
        self.assertIsNone(result["resolved_label_records"])
        first = result["cases"][0]
        self.assertEqual(first["status"], "awaiting_annotations")
        self.assertEqual(first["missing_raters"], ["rater-2"])

    async def test_empty_transcript_has_explicit_absence_and_legacy_omission(self):
        from app.g5.world import World, Decision
        source = self.sources[0]
        world = World(":memory:")
        self.addCleanup(world.close)
        world.create("empty-fixture", source["spec"], source["binding"])
        for version in range(source["binding"]["stopping_policy"]["max_steps"]):
            world.commit("empty-fixture", expected_version=version, request_id=str(version),
                actor=source["spec"]["roles"][version % 2], decision=Decision("wait"), audit={})
        world.freeze("empty-fixture")
        plan = copy.deepcopy(self.frozen["plan"])
        plan["cases"] = [next(c for c in plan["cases"] if c["ordinal"] == source["binding"]["assignment"]["ordinal"])]
        archive = AnnotationArchive(":memory:", self.manifest, [world.export_source("empty-fixture")], freeze_plan(plan))
        self.addCleanup(archive.close)
        task = archive.task(plan["cases"][0]["id"])
        self.assertEqual(task["turns"], [])
        for who in range(2):
            row = self.row(plan["cases"][0]["id"], who, "not_applicable")
            row.update(task_sha256=task["sha256"], quotes=[])
            with self.assertRaises(ValueError):
                archive.append({**row, "label": "clear"})
            archive.append(row)
        report = archive.report()
        self.assertTrue(report["all_resolved"])
        self.assertIsNone(report["resolved_label_records"])
        self.assertEqual(len(report["legacy_export_omissions"]), 2)

    async def test_wrong_quote_rater_duplicate_adjudication_and_tamper_rejected(self):
        for key, value in (("task_sha256", "0" * 64), ("annotator", self.adjudicator),
                           ("quotes", [{"turn_id": "missing", "start": 0, "end": 1, "text": "x"}])):
            wrong = self.row()
            wrong[key] = value
            with self.assertRaises(ValueError):
                self.archive.append(wrong)
        with self.assertRaises(ValueError):
            self.archive.append(self.row(phase="adjudication"))
        first, second = self.row(), self.row(who=1, label="violation")
        self.archive.append(first)
        self.assertEqual(self.archive.append(first), first)
        with self.assertRaises(ValueError):
            self.archive.append({**first, "id": "replacement"})
        self.archive.append(second)
        with self.assertRaises(ValueError):
            self.archive.append(self.row(phase="adjudication", based_on=[digest(first)]))
        chosen = self.row(phase="adjudication", based_on=sorted([digest(first), digest(second)]))
        self.archive.append(chosen)
        with self.assertRaises(ValueError):
            self.archive.append({**chosen, "id": "second-adjudication"})
        bad = self.archive.export()
        bad["rows"][0]["label"] = "uncertain"
        bad["sha256"] = digest({k: v for k, v in bad.items() if k != "sha256"})
        with self.assertRaises(ValueError):
            verify_export(bad)
        with self.assertRaises(sqlite3.IntegrityError):
            self.archive.db.execute("DELETE FROM annotation_rows")

    async def test_reconnect_changed_plan_and_unrelated_database_are_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "annotation.sqlite")
            archive = AnnotationArchive(path, self.manifest, self.sources, self.frozen)
            archive.append(self.row())
            before = archive.export()
            archive.close()
            archive = AnnotationArchive(path, self.manifest, self.sources, self.frozen)
            self.assertEqual(archive.export(), before)
            archive.close()
            changed = copy.deepcopy(self.frozen["plan"])
            changed["raters"][0]["kind"] = "human"
            with self.assertRaises(ValueError):
                AnnotationArchive(path, self.manifest, self.sources, freeze_plan(changed))
            unrelated = str(Path(directory) / "unrelated.sqlite")
            db = sqlite3.connect(unrelated)
            db.execute("CREATE TABLE user_data(value TEXT)")
            db.commit()
            with self.assertRaises(ValueError):
                AnnotationArchive(unrelated, self.manifest, self.sources, self.frozen)
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("user_data",)])
            db.close()

    async def test_real_process_exit_rollback_and_acknowledgement_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps({"manifest": self.manifest, "sources": self.sources,
                "plan": self.frozen, "row": self.row()}))
            child = '''
import json, os, sys
from app.g5.annotation_archive import AnnotationArchive
d=json.load(open(sys.argv[1]))
a=AnnotationArchive(sys.argv[2],d['manifest'],d['sources'],d['plan'])
if sys.argv[3]=='inside':
    a.db.set_trace_callback(lambda sql: os._exit(75) if sql=='COMMIT' else None)
a.append(d['row'])
os._exit(74)
'''
            for mode in ("inside", "after"):
                path = str(Path(directory) / (mode + ".sqlite"))
                result = subprocess.run([sys.executable, "-c", child, str(input_path), path, mode], capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 75 if mode == "inside" else 74, result.stderr.decode())
                archive = AnnotationArchive(path, self.manifest, self.sources, self.frozen)
                try:
                    self.assertEqual(len(archive.export()["rows"]), 0 if mode == "inside" else 1)
                    archive.append(self.row())
                    self.assertEqual(len(archive.export()["rows"]), 1)
                finally:
                    archive.close()


if __name__ == "__main__":
    import argparse
    import asyncio
    import os
    from app.g5.world import canonical
    parser = argparse.ArgumentParser(description="Synthetic annotation audit fixture; no human contact")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.output_dir)
    directory.mkdir(mode=0o700, exist_ok=False)
    async def run():
        case = AnnotationTests()
        try:
            await case.asyncSetUp()
            await case.test_full_six_dimension_four_source_panel_preserves_disagreement_and_provenance()
            raw = {"schema": "g5-synthetic-annotation-panel-v1", "real_model_calls": 0, "human_annotations": 0,
                   "archive": case.exported, "report": case.archive.report()}
            raw["sha256"] = digest(raw)
            fd = os.open(directory / "panel.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(canonical(raw))
                stream.flush()
                os.fsync(stream.fileno())
            print({"sha256": raw["sha256"], "cases": len(raw["report"]["cases"]), "rows": len(case.exported["rows"])})
        finally:
            case.doCleanups()
    asyncio.run(run())
