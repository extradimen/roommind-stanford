"""Load scenario templates from JSON files under templates/scenarios/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.character_display import compose_display_name, normalize_character_fields
from app.models.db import CharacterTemplate, DispatchRule, ScenarioTemplate
from app.orchestrator.defaults import default_orchestration_config, merge_orchestration_config
from app.scenario_bundle import apply_scenario_bundle
from app.scenario_side import sync_legacy_business_goal

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "scenarios"

CHARACTER_FIELDS = (
    "character_id",
    "side",
    "character_name",
    "job_title",
    "display_name",
    "persona",
    "responsibility",
    "tendency",
    "private_state",
    "system_prompt",
    "voice_id",
    "spawn_point",
    "avatar_manifest",
    "llm_config",
    "sort_order",
)

RULE_FIELDS = (
    "name",
    "description",
    "trigger_keywords",
    "priority_character_ids",
    "min_speakers",
    "max_speakers",
    "weights",
    "is_active",
)


def list_scenario_template_files() -> list[Path]:
    if not TEMPLATES_DIR.is_dir():
        return []
    return sorted(TEMPLATES_DIR.glob("*.json"))


def load_scenario_template_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _player_goal(data: dict[str, Any]) -> str:
    return data.get("player_side_goal") or data.get("business_goal") or ""


async def import_scenario_template(db: AsyncSession, data: dict[str, Any]) -> ScenarioTemplate:
    player_goal = _player_goal(data)
    meta = data.get("template_meta") or {}
    orchestration = merge_orchestration_config(data.get("orchestration_config") or default_orchestration_config())
    router_rules = dict(data.get("router_rules") or {})
    if meta:
        router_rules["_template"] = meta

    scenario = ScenarioTemplate(
        slug=data["slug"],
        title=data["title"],
        description=data.get("description"),
        business_goal=player_goal,
        player_side_goal=player_goal,
        opponent_side_goal=data.get("opponent_side_goal") or "",
        phases=data.get("phases") or ["opening", "discovery", "bargaining", "closing"],
        win_conditions=data.get("win_conditions") or [],
        scene_config=data.get("scene_config") or {},
        director_prompt=data.get("director_prompt"),
        router_rules=router_rules,
        orchestration_config=orchestration,
        is_published=bool(data.get("is_published", False)),
    )
    sync_legacy_business_goal(scenario)
    db.add(scenario)
    await db.flush()

    for idx, raw in enumerate(data.get("characters") or []):
        payload = {field: raw.get(field) for field in CHARACTER_FIELDS if field in raw}
        if not payload.get("side"):
            payload["side"] = "opponent"
        name, title, display = normalize_character_fields(
            character_name=payload.get("character_name"),
            job_title=payload.get("job_title"),
            display_name=payload.get("display_name"),
        )
        payload["character_name"] = name
        payload["job_title"] = title
        payload["display_name"] = display
        payload.setdefault("tendency", {})
        payload.setdefault("private_state", {})
        payload.setdefault("avatar_manifest", {})
        payload.setdefault("llm_config", {})
        payload["sort_order"] = payload.get("sort_order", idx)
        db.add(CharacterTemplate(scenario_id=scenario.id, **payload))

    for raw in data.get("dispatch_rules") or []:
        payload = {field: raw.get(field) for field in RULE_FIELDS if field in raw}
        payload.setdefault("weights", {})
        payload.setdefault("is_active", True)
        db.add(DispatchRule(scenario_id=scenario.id, **payload))

    return scenario


async def seed_scenarios_from_templates(db: AsyncSession) -> int:
    count = 0
    for path in list_scenario_template_files():
        data = load_scenario_template_file(path)
        slug = data.get("slug")
        if not slug:
            continue
        existing = await db.execute(select(ScenarioTemplate.id).where(ScenarioTemplate.slug == slug))
        if existing.scalar_one_or_none():
            continue
        await import_scenario_template(db, data)
        count += 1
    return count


def find_scenario_template_by_slug(slug: str) -> dict[str, Any] | None:
    for path in list_scenario_template_files():
        data = load_scenario_template_file(path)
        if data.get("slug") == slug:
            return data
    return None


async def reimport_scenario_from_template(
    db: AsyncSession,
    slug: str,
    *,
    overwrite_orchestration: bool = False,
) -> ScenarioTemplate | None:
    """Replace an existing scenario's content from its JSON template file (keeps scenario id)."""
    data = find_scenario_template_by_slug(slug)
    if not data:
        return None

    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.slug == slug)
        .options(selectinload(ScenarioTemplate.characters))
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        return None

    meta = data.get("template_meta") or {}
    router_rules = dict(data.get("router_rules") or {})
    if meta:
        router_rules["_template"] = meta
    import_data = {**data, "router_rules": router_rules}

    if overwrite_orchestration or data.get("orchestration_config"):
        scenario.orchestration_config = merge_orchestration_config(
            data.get("orchestration_config") or default_orchestration_config()
        )

    await apply_scenario_bundle(db, scenario, import_data, update_slug=False)
    await db.flush()
    return scenario
