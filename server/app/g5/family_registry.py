"""Append-only declared lineage/exposure registry, not a semantic novelty oracle."""
from copy import deepcopy
import json
import sqlite3

from app.factorial_study import digest
from app.g5.annotation_archive import identity
from app.g5.measurement import require, sha
from app.g5.world import canonical


def _name(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def project(events):
    families, materials, exposures, ids = {}, [], [], set()
    for event in events:
        require(isinstance(event, dict) and _name(event.get("id")) and event["id"] not in ids, "Invalid or duplicate registry event")
        kind = event.get("kind")
        if kind == "family":
            require(set(event) == {"id", "kind", "family_id", "parents", "provenance"}, "Invalid family registration")
            require(_name(event["family_id"]) and event["family_id"] not in families, "Family already registered")
            parents = event["parents"]
            require(isinstance(parents, list) and all(_name(p) and p in families for p in parents)
                and len(set(parents)) == len(parents), "Parents must be distinct previously registered families")
            provenance = event["provenance"]
            require(isinstance(provenance, dict) and set(provenance) == {"author", "artifact_sha256"}
                and sha(provenance["artifact_sha256"]), "Family provenance required")
            identity(provenance["author"])
            families[event["family_id"]] = event
        elif kind == "material":
            require(set(event) == {"id", "kind", "family_id", "snapshot_sha256", "provenance_sha256"}
                and _name(event["family_id"]) and event["family_id"] in families and sha(event["snapshot_sha256"])
                and sha(event["provenance_sha256"]), "Invalid material registration")
            materials.append(event)
        else:
            require(kind == "exposure" and set(event) == {"id", "kind", "families", "purpose", "observer", "artifact_sha256"}, "Invalid exposure record")
            members = event["families"]
            require(isinstance(members, list) and members and all(_name(f) and f in families for f in members)
                and len(set(members)) == len(members), "Exposure families must already exist")
            require(event["purpose"] in {"development", "calibration", "pilot", "screening", "confirmation"}
                and sha(event["artifact_sha256"]), "Exposure purpose/evidence required")
            identity(event["observer"])
            exposures.append(event)
        ids.add(event["id"])
    roots = {f: f for f in families}
    def root(f):
        while roots[f] != f:
            f = roots[f]
        return f
    def union(a, b):
        a, b = root(a), root(b)
        roots[max(a, b)] = min(a, b)
    for family, record in families.items():
        for parent in record["parents"]:
            union(family, parent)
    snapshots = {}
    for item in materials:
        key = item["snapshot_sha256"]
        if key in snapshots:
            union(item["family_id"], snapshots[key])
        snapshots[key] = item["family_id"]
    groups = {f: sorted(g for g in families if root(g) == root(f)) for f in families}
    return {"families": families, "materials": materials, "exposures": exposures, "groups": groups}


class FamilyRegistry:
    def __init__(self, path, registry_id):
        require(_name(registry_id), "Stable registry ID required")
        self.header = {"schema": "g5-family-registry-v1", "registry_id": registry_id}
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require(not tables or tables == {"family_header", "family_events"}, "Unrelated registry database")
            self.db.execute("CREATE TABLE IF NOT EXISTS family_header(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS family_events(seq INTEGER PRIMARY KEY,payload TEXT NOT NULL,checksum TEXT NOT NULL)")
            old = self.db.execute("SELECT payload FROM family_header WHERE id=1").fetchone()
            if old is None:
                self.db.execute("INSERT INTO family_header VALUES(1,?)", (canonical(self.header),))
            else:
                require(old[0] == canonical(self.header), "Registry identity changed")
            for table in ("family_header", "family_events"):
                for action in ("UPDATE", "DELETE"):
                    self.db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable family registry'); END")
            events, _ = self._read()
            project(events)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK"); self.db.close()
            raise

    def close(self):
        self.db.close()

    def _read(self):
        require(self.db.execute("SELECT payload FROM family_header WHERE id=1").fetchone()[0] == canonical(self.header), "Registry header drift")
        events, chain = [], digest(self.header)
        for seq, raw, checksum in self.db.execute("SELECT seq,payload,checksum FROM family_events ORDER BY seq"):
            event = json.loads(raw)
            require(seq == len(events) + 1, "Registry sequence changed")
            chain = digest([chain, seq, event])
            require(chain == checksum, "Registry checksum changed")
            events.append(event)
        return events, chain

    def append(self, event):
        event = deepcopy(event)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            events, chain = self._read()
            if event in events:
                project(events)
            else:
                project(events + [event])
                self.db.execute("INSERT INTO family_events VALUES(?,?,?)", (len(events) + 1, canonical(event), digest([chain, len(events) + 1, event])))
            self.db.execute("COMMIT")
            return event
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def export(self):
        self.db.execute("BEGIN")
        try:
            events, chain = self._read()
            project(events)
            raw = {**self.header, "events": events, "chain_sha256": chain}
            return {**raw, "sha256": digest(raw)}
        finally:
            self.db.execute("ROLLBACK")


def verify_export(exported):
    require(isinstance(exported, dict) and set(exported) == {"schema", "registry_id", "events", "chain_sha256", "sha256"}
        and exported["schema"] == "g5-family-registry-v1" and _name(exported["registry_id"])
        and isinstance(exported["events"], list), "Invalid registry export")
    require(exported["sha256"] == digest({k: v for k, v in exported.items() if k != "sha256"}), "Registry export changed")
    chain = digest({"schema": exported["schema"], "registry_id": exported["registry_id"]})
    for seq, event in enumerate(exported["events"], 1):
        chain = digest([chain, seq, event])
    require(chain == exported["chain_sha256"], "Registry chain changed")
    return project(exported["events"])


def holdout_audit(exported, families, *, expected_snapshot_sha256=None):
    state = verify_export(exported)
    require(isinstance(families, list) and families and all(_name(f) and f in state["families"] for f in families)
        and len(set(families)) == len(families), "Unknown or duplicate selected family")
    if expected_snapshot_sha256 is not None:
        require(exported["sha256"] == expected_snapshot_sha256, "Registry snapshot changed; re-audit selection")
    rows = []
    for family in families:
        group = state["groups"][family]
        seen = [e["id"] for e in state["exposures"] if set(e["families"]) & set(group)]
        rows.append({"family": family, "linked_families": group, "exposure_event_ids": seen})
    raw = {"schema": "g5-registered-holdout-audit-v1", "registry_sha256": exported["sha256"], "families": rows,
        "registered_exposure_free": not any(r["exposure_event_ids"] for r in rows),
        "semantic_novelty": "not_established", "identity_authentication": "not_established", "launch_authorized": False}
    return {**raw, "sha256": digest(raw)}
