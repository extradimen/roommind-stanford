"""Export/import scenario content (characters, dispatch rules) without Agent orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.character_display import normalize_character_fields
from app.models.db import CharacterTemplate, DispatchRule, ScenarioTemplate
from app.scenario_side import sync_legacy_business_goal

BUNDLE_FORMAT = "roommind-scenario-bundle"
BUNDLE_VERSION = 1

CHARACTER_EXPORT_FIELDS = (
    "character_id",
    "side",
    "character_name",
    "job_title",
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

RULE_EXPORT_FIELDS = (
    "name",
    "description",
    "trigger_keywords",
    "priority_character_ids",
    "min_speakers",
    "max_speakers",
    "weights",
    "is_active",
)


def validate_scenario_bundle(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Import body must be a JSON object")
    slug = data.get("slug")
    title = data.get("title")
    if not slug or not isinstance(slug, str):
        raise ValueError("Missing or invalid required field: slug")
    if not title or not isinstance(title, str):
        raise ValueError("Missing or invalid required field: title")
    if "characters" in data and not isinstance(data["characters"], list):
        raise ValueError("characters must be an array")
    if "dispatch_rules" in data and not isinstance(data["dispatch_rules"], list):
        raise ValueError("dispatch_rules must be an array")
    return data


def export_scenario_bundle(
    scenario: ScenarioTemplate,
    characters: list[CharacterTemplate],
    dispatch_rules: list[DispatchRule],
) -> dict[str, Any]:
    chars = sorted(characters, key=lambda c: (c.sort_order, c.id))
    rules = sorted(dispatch_rules, key=lambda r: r.id)
    return {
        "export_meta": {
            "format": BUNDLE_FORMAT,
            "version": BUNDLE_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "scenario_id": scenario.id,
            "note": "Scenario content only. Agent orchestration_config is stored separately.",
        },
        "slug": scenario.slug,
        "title": scenario.title,
        "description": scenario.description,
        "player_side_goal": scenario.player_side_goal or scenario.business_goal or "",
        "opponent_side_goal": scenario.opponent_side_goal or "",
        "phases": scenario.phases or [],
        "win_conditions": scenario.win_conditions or [],
        "scene_config": scenario.scene_config or {},
        "director_prompt": scenario.director_prompt,
        "router_rules": scenario.router_rules or {},
        "is_published": scenario.is_published,
        "characters": [
            {
                field: getattr(char, field)
                for field in CHARACTER_EXPORT_FIELDS
                if getattr(char, field, None) is not None
                or field in ("tendency", "private_state", "avatar_manifest", "llm_config")
            }
            for char in chars
        ],
        "dispatch_rules": [
            {field: getattr(rule, field) for field in RULE_EXPORT_FIELDS}
            for rule in rules
        ],
    }


async def apply_scenario_bundle(
    db: AsyncSession,
    scenario: ScenarioTemplate,
    data: dict[str, Any],
    *,
    update_slug: bool = True,
) -> ScenarioTemplate:
    """Replace scenario content from bundle. Does not touch orchestration_config."""
    payload = validate_scenario_bundle(data)
    player_goal = payload.get("player_side_goal") or payload.get("business_goal") or ""

    if update_slug and payload.get("slug"):
        scenario.slug = payload["slug"]
    scenario.title = payload["title"]
    scenario.description = payload.get("description")
    scenario.business_goal = player_goal
    scenario.player_side_goal = player_goal
    scenario.opponent_side_goal = payload.get("opponent_side_goal") or ""
    scenario.phases = payload.get("phases") or ["opening", "discovery", "bargaining", "closing"]
    scenario.win_conditions = payload.get("win_conditions") or []
    scenario.scene_config = payload.get("scene_config") or {}
    if "director_prompt" in payload:
        scenario.director_prompt = payload.get("director_prompt")
    if "router_rules" in payload:
        scenario.router_rules = payload.get("router_rules") or {}
    if "is_published" in payload:
        scenario.is_published = bool(payload.get("is_published"))
    sync_legacy_business_goal(scenario)

    chars_result = await db.execute(
        select(CharacterTemplate).where(CharacterTemplate.scenario_id == scenario.id)
    )
    for char in chars_result.scalars().all():
        await db.delete(char)
    await db.flush()

    for idx, raw in enumerate(payload.get("characters") or []):
        if not isinstance(raw, dict) or not raw.get("character_id"):
            continue
        fields = {field: raw.get(field) for field in CHARACTER_EXPORT_FIELDS if field in raw}
        fields.setdefault("character_id", raw["character_id"])
        if not fields.get("side"):
            fields["side"] = "opponent"
        name, title, display = normalize_character_fields(
            character_name=fields.get("character_name"),
            job_title=fields.get("job_title"),
            display_name=raw.get("display_name"),
        )
        fields["character_name"] = name
        fields["job_title"] = title
        fields["display_name"] = display
        fields.setdefault("persona", "")
        fields.setdefault("responsibility", "")
        fields.setdefault("tendency", {})
        fields.setdefault("private_state", {})
        fields.setdefault("avatar_manifest", {})
        fields.setdefault("llm_config", {})
        fields["sort_order"] = fields.get("sort_order", idx)
        db.add(CharacterTemplate(scenario_id=scenario.id, **fields))

    rules_result = await db.execute(select(DispatchRule).where(DispatchRule.scenario_id == scenario.id))
    for rule in rules_result.scalars().all():
        await db.delete(rule)

    for raw in payload.get("dispatch_rules") or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        rule_payload = {field: raw.get(field) for field in RULE_EXPORT_FIELDS if field in raw}
        rule_payload.setdefault("name", raw["name"])
        rule_payload.setdefault("trigger_keywords", [])
        rule_payload.setdefault("priority_character_ids", [])
        rule_payload.setdefault("weights", {})
        rule_payload.setdefault("is_active", True)
        rule_payload.setdefault("min_speakers", 1)
        rule_payload.setdefault("max_speakers", 2)
        db.add(DispatchRule(scenario_id=scenario.id, **rule_payload))

    await db.flush()
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario.id)
        .options(selectinload(ScenarioTemplate.characters))
    )
    return result.scalar_one()
