"""Local prediction ledger: pending calls remain indeterminate, never invented failures."""
from copy import deepcopy
import json
import sqlite3
import uuid

from app.factorial_study import digest
from app.g5.annotation_archive import AnnotationArchive
from app.g5.calibration_bridge import freeze_results
from app.g5.calibration_predictor import validate_plan, request_for
from app.g5.measurement import require
from app.g5.world import canonical
from app.g5.local_worker import LocalWorker


class PredictionArchive:
    def __init__(self, path, annotation, plan):
        validate_plan(plan)
        freeze_results(annotation, plan, [])
        self.header = deepcopy({"schema": "g5-prediction-ledger-v1", "annotation": annotation, "plan": plan})
        self.tasks = AnnotationArchive(":memory:", annotation["manifest"], annotation["sources"], annotation["plan"])
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.worker = LocalWorker(path)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require(not tables or tables == {"prediction_header", "prediction_events"}, "Unrelated prediction database")
            self.db.execute("CREATE TABLE IF NOT EXISTS prediction_header(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS prediction_events(seq INTEGER PRIMARY KEY,payload TEXT NOT NULL,checksum TEXT NOT NULL)")
            row = self.db.execute("SELECT payload FROM prediction_header WHERE id=1").fetchone()
            if row is None:
                self.db.execute("INSERT INTO prediction_header VALUES(1,?)", (canonical(self.header),))
            else:
                require(row[0] == canonical(self.header), "Prediction frozen inputs differ")
            for table in ("prediction_header", "prediction_events"):
                for action in ("UPDATE", "DELETE"):
                    self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable prediction ledger'); END")
            events, _ = self._read()
            self._project(events)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            self.close()
            raise

    def close(self):
        require(not self.worker.active, "Close the active prediction stream before closing its archive")
        self.db.close()
        self.tasks.close()

    def _project(self, events):
        starts, results, latest = {}, [], {}
        for event in events:
            require(isinstance(event, dict) and set(event) == {"phase", "value"}, "Invalid prediction journal event")
            value = event["value"]
            if event["phase"] == "started":
                require(set(value) == {"id", "case_id", "previous_attempt_sha256", "request_sha256"}
                    and isinstance(value["id"], str) and value["id"] and value["id"] not in starts, "Invalid prediction start")
                task = self.tasks.task(value["case_id"])
                old = latest.get(value["case_id"])
                require(not any(s["case_id"] == value["case_id"] and not any(r["id"] == s["id"] for r in results) for s in starts.values()), "Prediction already pending")
                require(old is None or old["artifact"]["output"]["status"] == "technical_failure", "Prediction already completed")
                require(value["previous_attempt_sha256"] == (digest(old) if old else None)
                    and value["request_sha256"] == digest(request_for(task, self.header["plan"]["model_spec"])), "Prediction start source drift")
                starts[value["id"]] = value
            else:
                require(event["phase"] == "finished" and value["id"] in starts
                    and not any(r["id"] == value["id"] for r in results), "Prediction result without unique start")
                start = starts[value["id"]]
                require(value["case_id"] == start["case_id"] and value["previous_attempt_sha256"] == start["previous_attempt_sha256"], "Prediction completion identity mismatch")
                results.append(value)
                latest[value["case_id"]] = value
        frozen = freeze_results(self.header["annotation"], self.header["plan"], results)
        pending = [s for key, s in starts.items() if not any(r["id"] == key for r in results)]
        return frozen, pending

    def _read(self):
        require(self.db.execute("SELECT payload FROM prediction_header WHERE id=1").fetchone()[0] == canonical(self.header), "Prediction header changed")
        events, chain = [], digest(self.header)
        for seq, raw, checksum in self.db.execute("SELECT seq,payload,checksum FROM prediction_events ORDER BY seq"):
            event = json.loads(raw)
            require(seq == len(events) + 1, "Prediction sequence mismatch")
            chain = digest([chain, seq, event])
            require(chain == checksum, "Prediction chain mismatch")
            events.append(event)
        # Hash/sequence verification only. Each public operation must project
        # its complete snapshot once, inside the same transaction. Do not cache
        # trusted source/results across transactions or expose a skip flag.
        return events, chain

    def append(self, event):
        with self.worker.operation():
            return self._append(event)

    def _append(self, event):
        event = deepcopy(event)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            events, chain = self._read()
            if event in events:
                self._project(events)
                self.db.execute("COMMIT")
                return event
            self._project(events + [event])
            self.db.execute("INSERT INTO prediction_events VALUES(?,?,?)", (len(events) + 1, canonical(event), digest([chain, len(events) + 1, event])))
            self.db.execute("COMMIT")
            return event
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def export(self):
        self.db.execute("BEGIN")
        try:
            events, chain = self._read()
            results, pending = self._project(events)
            raw = {**deepcopy(self.header), "events": events, "chain_sha256": chain,
                   "results": results, "pending_indeterminate": pending}
            return {**raw, "sha256": digest(raw)}
        finally:
            self.db.execute("ROLLBACK")

    async def run_missing(self, predictor, *, resume_pending=False):
        """Exclusive cooperating local worker; close the stream to release ownership.

        Explicit resume still requires legacy/unmanaged callers to be quiescent.
        Interrupted remote inference can repeat, not persisted completed results.
        This is a local kernel lock, not a distributed lease or remote cancellation.
        """
        require(type(resume_pending) is bool, "Explicit boolean recovery decision required")
        with self.worker.claim():
            stream = self._run_missing(predictor, resume_pending=resume_pending)
            try:
                async for result in stream:
                    yield result
            finally:
                await stream.aclose()

    async def _run_missing(self, predictor, *, resume_pending):
        require(predictor.plan() == self.header["plan"], "Predictor drift before inference")
        state = self.export()
        require(resume_pending or not state["pending_indeterminate"], "Indeterminate prediction requires explicit quiescent recovery")
        for case in self.header["annotation"]["plan"]["plan"]["cases"]:
            state = self.export()
            previous = next((r for r in reversed(state["results"]["attempts"]) if r["case_id"] == case["id"]), None)
            if previous and previous["artifact"]["output"]["status"] == "completed":
                continue
            task = self.tasks.task(case["id"])
            start = next((s for s in state["pending_indeterminate"] if s["case_id"] == case["id"]), None)
            require(start is None or resume_pending, "Indeterminate prediction requires explicit quiescent recovery")
            if start is None:
                start = {"id": uuid.uuid4().hex, "case_id": case["id"], "previous_attempt_sha256": digest(previous) if previous else None,
                         "request_sha256": digest(request_for(task, self.header["plan"]["model_spec"]))}
                self.append({"phase": "started", "value": start})
            result = await predictor.predict(task, self.header["plan"], attempt_id=start["id"], previous=previous)
            self.worker.check()
            self.append({"phase": "finished", "value": result})
            yield result


def verify_export(exported):
    archive = PredictionArchive(":memory:", exported["annotation"], exported["plan"])
    try:
        for event in exported["events"]:
            archive.append(event)
        require(archive.export() == exported, "Prediction export does not reproduce")
        return {"results_sha256": exported["results"]["sha256"], "pending_indeterminate": len(exported["pending_indeterminate"])}
    finally:
        archive.close()
