"""Internal source-bound independent labels and explicit disagreement adjudication.

Identity/kind are declared provenance, not authentication or proof of independent
human work. No annotators are contacted and no old labels are rewritten.
"""
from copy import deepcopy
import json
import sqlite3

from app.factorial_study import digest
from app.g5.evaluation import packet_from_source
from app.g5.measurement import DIMENSIONS, require, validate_quotes, freeze_labels
from app.g5.world import canonical


LABELS = {"violation", "clear", "uncertain", "not_applicable"}


def identity(value):
    require(isinstance(value, dict) and set(value) == {"id", "kind"}
            and isinstance(value["id"], str) and value["id"].strip()
            and value["kind"] in {"synthetic", "assistant", "human"}, "Explicit annotator provenance required")


def freeze_plan(plan):
    require(isinstance(plan, dict) and set(plan) == {"schema", "raters", "adjudicator", "cases"}
            and plan["schema"] == "g5-independent-annotation-plan-v1", "Invalid annotation plan")
    require(isinstance(plan["raters"], list) and len(plan["raters"]) >= 2, "At least two declared raters required")
    people = plan["raters"] + [plan["adjudicator"]]
    for person in people:
        identity(person)
    require(len({p["id"] for p in people}) == len(people), "Raters and adjudicator must have distinct identities")
    require(isinstance(plan["cases"], list) and plan["cases"], "Frozen cases required")
    seen = set()
    for case in plan["cases"]:
        require(isinstance(case, dict) and set(case) == {"id", "ordinal", "dimension", "category", "rubric"}, "Invalid annotation case")
        require(all(isinstance(case[k], str) and case[k].strip() for k in ("id", "category", "rubric"))
                and type(case["ordinal"]) is int and case["ordinal"] > 0 and case["dimension"] in DIMENSIONS,
                "Invalid annotation case values")
        require(case["id"] not in seen, "Duplicate annotation case")
        seen.add(case["id"])
    return {"plan": deepcopy(plan), "sha256": digest(plan)}


class AnnotationArchive:
    def __init__(self, path, manifest, sources, frozen_plan):
        require(freeze_plan(frozen_plan["plan"]) == frozen_plan, "Annotation plan checksum mismatch")
        packets = [packet_from_source(source, manifest) for source in sources]
        ordinals = [p["transcript"]["ordinal"] for p in packets]
        require(len(set(ordinals)) == len(ordinals) and set(ordinals) == {c["ordinal"] for c in frozen_plan["plan"]["cases"]},
                "Source assignments must match frozen annotation cases exactly")
        self.header = deepcopy({"schema": "g5-independent-annotation-archive-v1", "classification": "internal-audit-only",
            "manifest": manifest, "sources": sources, "plan": frozen_plan})
        self.packets = {p["transcript"]["ordinal"]: p for p in packets}
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require(not tables or tables == {"annotation_header", "annotation_rows"}, "Unrelated database")
            self.db.execute("CREATE TABLE IF NOT EXISTS annotation_header (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS annotation_rows (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, checksum TEXT NOT NULL)")
            row = self.db.execute("SELECT payload FROM annotation_header WHERE id=1").fetchone()
            if row is None:
                self.db.execute("INSERT INTO annotation_header VALUES(1,?)", (canonical(self.header),))
            else:
                require(row[0] == canonical(self.header), "Annotation archive frozen inputs differ")
            for table in ("annotation_header", "annotation_rows"):
                for action in ("UPDATE", "DELETE"):
                    self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable annotation history'); END")
            self._read()
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def task(self, case_id):
        case = next((c for c in self.header["plan"]["plan"]["cases"] if c["id"] == case_id), None)
        require(case is not None, "Unknown annotation case")
        packet = self.packets[case["ordinal"]]
        raw = {"schema": "g5-blinded-annotation-task-v1", "classification": "internal-annotator-only",
            "case_id": case_id, "dimension": case["dimension"], "rubric": case["rubric"],
            "context": packet["context"], "turns": packet["transcript"]["turns"]}
        return deepcopy({**raw, "sha256": digest(raw)})

    def _validate(self, row, previous):
        require(isinstance(row, dict) and set(row) == {"id", "case_id", "phase", "annotator", "task_sha256",
            "label", "quotes", "rationale", "artifact", "based_on"}, "Invalid annotation record")
        require(isinstance(row["id"], str) and row["id"].strip() and row["label"] in LABELS
            and isinstance(row["rationale"], str) and row["rationale"].strip()
            and isinstance(row["artifact"], dict) and row["artifact"], "Annotation explanation and raw artifact required")
        task = self.task(row["case_id"])
        require(row["task_sha256"] == task["sha256"], "Annotation source task changed")
        if task["turns"]:
            validate_quotes(row["quotes"], {"turns": task["turns"]})
        else:
            require(row["label"] in {"uncertain", "not_applicable"} and row["quotes"] == [],
                    "Empty transcript needs explicit uncertain/N-A absence, not invented quotes")
        plan = self.header["plan"]["plan"]
        case_rows = [r for r in previous if r["case_id"] == row["case_id"]]
        if row["phase"] == "independent":
            require(row["annotator"] in plan["raters"] and row["based_on"] == [], "Independent rater mismatch")
            require(not any(r["annotator"] == row["annotator"] for r in case_rows), "Independent label already submitted")
        else:
            require(row["phase"] == "adjudication" and row["annotator"] == plan["adjudicator"], "Invalid adjudicator")
            require(len(case_rows) == len(plan["raters"]) and all(r["phase"] == "independent" for r in case_rows)
                and len({r["label"] for r in case_rows}) > 1, "Only complete unresolved disagreements may be adjudicated")
            require(row["based_on"] == sorted(digest(r) for r in case_rows), "Adjudication must bind all original labels")

    def adjudication_task(self, case_id):
        task = self.task(case_id)
        rows = [r for r in self.export()["rows"] if r["case_id"] == case_id]
        require(len(rows) == len(self.header["plan"]["plan"]["raters"])
                and all(r["phase"] == "independent" for r in rows)
                and len({r["label"] for r in rows}) > 1, "No complete unresolved disagreement")
        return {"task": task, "based_on": sorted(digest(r) for r in rows),
                "original_labels": deepcopy(rows)}

    def _read(self):
        require(self.db.execute("SELECT payload FROM annotation_header WHERE id=1").fetchone()[0] == canonical(self.header), "Annotation header changed")
        rows, chain = [], digest(self.header)
        for seq, key, payload, checksum in self.db.execute("SELECT seq,id,payload,checksum FROM annotation_rows ORDER BY seq"):
            row = json.loads(payload)
            require(seq == len(rows) + 1 and key == row["id"], "Annotation sequence mismatch")
            self._validate(row, rows)
            chain = digest([chain, seq, row])
            require(chain == checksum, "Annotation chain mismatch")
            rows.append(row)
        return rows, chain

    def append(self, row):
        row = deepcopy(row)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows, chain = self._read()
            for old in rows:
                if old["id"] == row["id"]:
                    require(canonical(old) == canonical(row), "Annotation ID reused with changes")
                    self.db.execute("COMMIT")
                    return old
            self._validate(row, rows)
            self.db.execute("INSERT INTO annotation_rows VALUES(?,?,?,?)", (len(rows) + 1, row["id"], canonical(row), digest([chain, len(rows) + 1, row])))
            self.db.execute("COMMIT")
            return row
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def export(self):
        self.db.execute("BEGIN")
        try:
            rows, chain = self._read()
            raw = {**deepcopy(self.header), "rows": rows, "chain_sha256": chain}
            return {**raw, "sha256": digest(raw)}
        finally:
            self.db.execute("ROLLBACK")

    def report(self):
        exported = self.export()
        summaries, labels, omissions = [], [], []
        plan = self.header["plan"]["plan"]
        for case in plan["cases"]:
            rows = [r for r in exported["rows"] if r["case_id"] == case["id"]]
            independent = [r for r in rows if r["phase"] == "independent"]
            adjudicated = next((r for r in rows if r["phase"] == "adjudication"), None)
            complete = len(independent) == len(plan["raters"])
            agreement = complete and len({r["label"] for r in independent}) == 1
            status = "adjudicated" if adjudicated else "agreed" if agreement else "disputed" if complete else "awaiting_annotations"
            resolved = adjudicated["label"] if adjudicated else independent[0]["label"] if agreement else None
            summaries.append({"case_id": case["id"], "status": status, "label": resolved,
                "missing_raters": [p["id"] for p in plan["raters"] if not any(r["annotator"] == p for r in independent)],
                "independent_disagreement": complete and not agreement,
                "declared_sources": sorted({r["annotator"]["kind"] for r in rows})})
            # Export only an explicit adjudicator's label or each agreeing rater's
            # original label; never fabricate a consensus annotator or human kind.
            chosen = [adjudicated] if adjudicated else independent if agreement else []
            for r in chosen:
                if not r["quotes"]:
                    omissions.append({"record_id": r["id"], "case_id": case["id"], "reason": "legacy-label-schema-requires-quotes"})
                    continue
                tx = self.packets[case["ordinal"]]["transcript"]
                labels.append({"id": digest([self.header["plan"]["sha256"], r["id"]]),
                    "family": self.header["manifest"]["assignments"][case["ordinal"] - 1]["family"],
                    "category": case["category"], "transcript": tx, "label": r["label"],
                    "label_source": r["annotator"]["kind"], "annotator_id": r["annotator"]["id"],
                    "annotation_artifact_sha256": digest(r), "quotes": r["quotes"], "rationale": r["rationale"]})
        raw = {"schema": "g5-independent-annotation-report-v1", "archive_sha256": exported["sha256"], "cases": summaries,
            "resolved_label_records": freeze_labels(self.header["manifest"], labels) if labels else None,
            "legacy_export_omissions": omissions,
            "all_resolved": all(s["label"] is not None for s in summaries),
            "unit": "case-not-label-record", "human_authentication": "not_established", "qualification": "not_inferred"}
        return {**raw, "sha256": digest(raw)}


def verify_export(exported):
    archive = AnnotationArchive(":memory:", exported["manifest"], exported["sources"], exported["plan"])
    try:
        for row in exported["rows"]:
            archive.append(row)
        require(archive.export() == exported, "Annotation export does not reproduce")
        return archive.report()
    finally:
        archive.close()
