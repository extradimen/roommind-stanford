"""Local append-only evaluation archive, separate from source-world databases.

All assigned dialogues must be sealed before opening this study archive. Model
calls stay outside transactions. Concurrent/ack-lost saves are idempotent by
attempt ID; completed dimensions cannot be overwritten. This is not a worker
lease or an exactly-once external inference guarantee. Files contain private
evaluator ground truth and must not be published as public transcripts.
"""
from copy import deepcopy
import json
import sqlite3

from app.factorial_study import digest
from app.g5.evaluation import PROMPT, validate_packet
from app.g5.measurement import index_scores, require
from app.g5.model_policy import _unique_object
from app.g5.world import canonical


class EvaluationArchive:
    def __init__(self, path, manifest, plan, packets, *, control=None):
        from app.g5.evaluation_controls import validate_cell
        validate_cell(plan, control)
        for packet in packets:
            validate_packet(manifest, packet)
        ordinals = [p["transcript"]["ordinal"] for p in packets]
        require(sorted(ordinals) == list(range(1, len(manifest["assignments"]) + 1)),
                "All assigned dialogues must be sealed exactly once")
        packets = sorted(deepcopy(packets), key=lambda p: p["transcript"]["ordinal"])
        index_scores(manifest, plan, [p["transcript"] for p in packets], [])
        self.header = deepcopy({"schema": "g5-local-evaluation-archive-v1",
            "classification": "internal-evaluator-only", "manifest": manifest,
            "plan": plan, "packets": packets})
        if control is not None:
            self.header["control"] = deepcopy(control)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require(not tables or tables == {"evaluation_header", "evaluation_results"},
                    "Refusing to initialize an unrelated database")
            self.db.execute("CREATE TABLE IF NOT EXISTS evaluation_header (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS evaluation_results (seq INTEGER PRIMARY KEY, attempt_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, chain_sha256 TEXT NOT NULL)")
            row = self.db.execute("SELECT payload FROM evaluation_header WHERE id=1").fetchone()
            if row is None:
                self.db.execute("INSERT INTO evaluation_header VALUES(1,?)", (canonical(self.header),))
            else:
                require(json.loads(row[0]) == self.header, "Archive belongs to another frozen input")
            for table in ("evaluation_header", "evaluation_results"):
                for action in ("UPDATE", "DELETE"):
                    self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable evaluation archive'); END")
            self._read()
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _validate_result(self, result):
        require(isinstance(result, dict) and set(result) == {"attempt", "artifact"}, "Invalid archived result")
        attempt, artifact = result["attempt"], result["artifact"]
        require(attempt["artifact_sha256"] == digest(artifact), "Raw artifact checksum mismatch")
        packet = next((p for p in self.header["packets"] if p["transcript"]["ordinal"] == attempt["ordinal"]), None)
        require(packet is not None and artifact["packet_sha256"] == packet["sha256"], "Artifact source mismatch")
        spec, rubric = artifact["evaluator_spec"], artifact["rubric"]
        require(artifact["classification"] == "internal-evaluator-only"
            and digest(spec) == attempt["judge"]["spec_sha256"]
            and digest(rubric) == self.header["plan"]["config"]["rubric_sha256"]
            and spec["prompt_sha256"] == digest(PROMPT), "Evaluator provenance mismatch")
        from app.g5.evaluation_controls import request_for
        require(artifact.get("control") == self.header.get("control"), "Evaluation control mismatch")
        expected_request = request_for(spec, packet, attempt["dimension"], rubric, self.header.get("control"))
        require(artifact["request"] == expected_request, "Evaluation request was altered")
        if attempt["status"] != "technical_failure":
            response = artifact["response"]
            binding = spec["binding"]
            require(artifact["error_code"] is None and response is not None
                and response["request_sha256"] == digest(expected_request)
                and response["finish_reason"] == "stop"
                and all(response[k] == binding[k] for k in ("provider", "model", "endpoint_id")),
                "Invalid completed model receipt")
            parsed = json.loads(response["content"], object_pairs_hook=_unique_object)
            require(parsed == {k: attempt[k] for k in ("status", "score", "quotes", "rationale")},
                    "Score differs from raw model response")
        else:
            require(artifact["error_code"] in {"timeout", "connection", "transport_failure", "invalid_response"}
                and attempt["rationale"] == "Evaluation failed: " + artifact["error_code"], "Invalid technical failure")

    def _read(self):
        require(json.loads(self.db.execute("SELECT payload FROM evaluation_header WHERE id=1").fetchone()[0]) == self.header,
                "Archive header changed")
        previous, results = digest(self.header), []
        for seq, attempt_id, payload, checksum in self.db.execute("SELECT seq,attempt_id,payload,chain_sha256 FROM evaluation_results ORDER BY seq"):
            result = json.loads(payload)
            require(seq == len(results) + 1 and attempt_id == result["attempt"]["id"], "Archive sequence mismatch")
            self._validate_result(result)
            previous = digest({"previous": previous, "seq": seq, "result": result})
            require(previous == checksum, "Archive chain mismatch")
            results.append(result)
        index_scores(self.header["manifest"], self.header["plan"],
                     [p["transcript"] for p in self.header["packets"]], [r["attempt"] for r in results])
        from app.g5.evaluation_controls import validate_order
        validate_order(self.header["plan"], self.header["packets"], self.header.get("control"), results)
        return results, previous

    def results(self):
        self.db.execute("BEGIN")
        try:
            return deepcopy(self._read()[0])
        finally:
            self.db.execute("ROLLBACK")

    def append(self, result):
        result = deepcopy(result)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows, previous = self._read()
            for existing in rows:
                if existing["attempt"]["id"] == result["attempt"]["id"]:
                    require(existing == result, "Attempt identity reused with different data")
                    self.db.execute("COMMIT")
                    return existing
            self._validate_result(result)
            from app.g5.evaluation_controls import validate_order
            validate_order(self.header["plan"], self.header["packets"], self.header.get("control"), rows + [result])
            index_scores(self.header["manifest"], self.header["plan"],
                [p["transcript"] for p in self.header["packets"]], [r["attempt"] for r in rows] + [result["attempt"]])
            seq = len(rows) + 1
            checksum = digest({"previous": previous, "seq": seq, "result": result})
            self.db.execute("INSERT INTO evaluation_results VALUES(?,?,?,?)",
                            (seq, result["attempt"]["id"], canonical(result), checksum))
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def export(self):
        self.db.execute("BEGIN")
        try:
            results, chain = self._read()
            raw = {**deepcopy(self.header), "results": results, "chain_sha256": chain}
            return {**raw, "sha256": digest(raw)}
        finally:
            self.db.execute("ROLLBACK")

    async def evaluate_missing(self, evaluator):
        """Persist before yielding acknowledgement; caller chooses further retries."""
        attempts = [r["attempt"] for r in self.results()]
        async for result in evaluator.missing_evaluations(self.header["manifest"], self.header["plan"],
                                                         self.header["packets"], attempts, control=self.header.get("control")):
            yield self.append(result)
