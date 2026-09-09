"""Freeze experiment inputs, including role cards and global dispatch rules."""
from sqlalchemy import select, or_
from app.models.db import ScenarioTemplate, CharacterTemplate, DispatchRule
from app.research_protocol import sha256_json


def payload(row):
    excluded = {"id", "scenario_id", "created_at", "updated_at"}
    return {column.name: getattr(row, column.name) for column in row.__table__.columns
            if column.name not in excluded}


async def capture_inputs(db, scenario_id):
    scenario = await db.get(ScenarioTemplate, scenario_id)
    if scenario is None:
        raise ValueError("Experiment scenario missing")
    roles = list((await db.scalars(select(CharacterTemplate).where(
        CharacterTemplate.scenario_id == scenario_id).order_by(CharacterTemplate.id))).all())
    rules = list((await db.scalars(select(DispatchRule).where(or_(
        DispatchRule.scenario_id == scenario_id, DispatchRule.scenario_id.is_(None)
    )).order_by(DispatchRule.id))).all())
    inputs = {"scenario": payload(scenario), "roles": [payload(r) for r in roles],
              "dispatch_rules": [payload(r) for r in rules]}
    return {"schema": "experiment-input-binding-v1", "inputs": inputs,
            "sha256": sha256_json(inputs)}


async def verify_inputs(db, bindings, scenario_id):
    if bindings is None:  # Old archived batches are not retroactively changed.
        return
    expected = bindings.get(str(scenario_id))
    if not expected or sha256_json(expected["inputs"]) != expected.get("sha256"):
        raise ValueError("Frozen input binding missing or corrupt")
    current = await capture_inputs(db, scenario_id)
    if current != expected:
        raise ValueError("Experiment scenario/role/world/dispatch inputs changed")


def verify_manifest_binding(manifest, bindings):
    if bindings is None:  # Historical batches predate input binding.
        return
    if not isinstance(manifest, dict) or manifest.get("frozen_inputs_sha256") != sha256_json(bindings):
        raise ValueError("Frozen inputs do not match research manifest")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("manifest_sha256") != sha256_json(unsigned):
        raise ValueError("Research manifest checksum mismatch")
