"""Seed default LLM config and scenario templates from JSON files."""

from sqlalchemy import select

from app.database import async_session_factory
from app.models.db import CharacterTemplate, LLMConfig, ScenarioTemplate
from app.orchestrator.defaults import merge_orchestration_config
from app.scenario_side import sync_legacy_business_goal
from app.scenario_template_loader import seed_scenarios_from_templates

from app.platform_llm import resolve_active_model, save_platform_llm_settings


async def seed_if_empty() -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(LLMConfig).limit(1))
        if not result.scalar_one_or_none():
            db.add(
                LLMConfig(
                    name="default",
                    provider="siliconflow",
                    model="moonshotai/Kimi-K2.5",
                    temperature=0.7,
                    max_tokens=2048,
                    is_active=True,
                )
            )
        await seed_scenarios_from_templates(db)
        await db.commit()


async def ensure_scenario_templates() -> None:
    """Import JSON templates whose slug is not yet in the database."""
    async with async_session_factory() as db:
        added = await seed_scenarios_from_templates(db)
        if added:
            await db.commit()


async def sync_character_name_fields() -> None:
    """Backfill character_name / job_title from legacy display_name."""
    from app.character_display import split_display_name

    async with async_session_factory() as db:
        result = await db.execute(select(CharacterTemplate))
        changed = False
        for char in result.scalars().all():
            if (not char.character_name or not char.job_title) and char.display_name:
                name, title = split_display_name(char.display_name)
                if name and not char.character_name:
                    char.character_name = name
                    changed = True
                if title and not char.job_title:
                    char.job_title = title
                    changed = True
        if changed:
            await db.commit()


async def sync_scenario_side_goals() -> None:
    """Backfill dual goals for scenarios created before player/opponent split."""
    async with async_session_factory() as db:
        result = await db.execute(select(ScenarioTemplate))
        changed = False
        for scenario in result.scalars().all():
            if not scenario.player_side_goal and scenario.business_goal:
                scenario.player_side_goal = scenario.business_goal
                changed = True
            sync_legacy_business_goal(scenario)
        if changed:
            await db.commit()


async def sync_scenario_player_characters() -> None:
    """Ensure each scenario has a player_character block in scene_config."""
    from app.player_character import resolve_player_character

    async with async_session_factory() as db:
        result = await db.execute(select(ScenarioTemplate))
        changed = False
        for scenario in result.scalars().all():
            scene = dict(scenario.scene_config or {})
            raw = scene.get("player_character")
            if isinstance(raw, dict) and raw.get("character_name") and raw.get("job_title"):
                continue
            player = resolve_player_character(scenario)
            scene["player_character"] = {
                "character_name": player["character_name"],
                "job_title": player["job_title"],
                "avatar_manifest": player["avatar_manifest"],
            }
            scenario.scene_config = scene
            changed = True
        if changed:
            await db.commit()


async def sync_scenario_orchestration_config() -> None:
    """Ensure existing scenarios have default orchestration config."""
    from app.orchestrator.defaults import sanitize_llm_roles_storage

    async with async_session_factory() as db:
        result = await db.execute(select(ScenarioTemplate))
        changed = False
        for scenario in result.scalars().all():
            raw = dict(scenario.orchestration_config or {})
            if isinstance(raw.get("llm_roles"), dict):
                cleaned_roles = sanitize_llm_roles_storage(raw["llm_roles"])
                if cleaned_roles != raw["llm_roles"]:
                    raw["llm_roles"] = cleaned_roles
                    changed = True
            merged = merge_orchestration_config(raw)
            if scenario.orchestration_config != merged:
                scenario.orchestration_config = merged
                changed = True
        if changed:
            await db.commit()


async def sync_dispatch_rule_keywords() -> None:
    """Patch seed dispatch rules when keywords are extended."""
    from app.models.db import DispatchRule

    async with async_session_factory() as db:
        result = await db.execute(select(DispatchRule).where(DispatchRule.name == "合同条款"))
        rule = result.scalar_one_or_none()
        if not rule:
            return
        desired = ["合同", "条款", "法律", "律师", "李律师", "违约", "赔偿", "协议"]
        if rule.trigger_keywords != desired:
            rule.trigger_keywords = desired
            await db.commit()


async def sync_llm_config_with_platform() -> None:
    """Align DB LLM row with platform.json defaults."""
    async with async_session_factory() as db:
        result = await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1))
        cfg = result.scalar_one_or_none()
        if not cfg:
            return
        if cfg.provider == "ollama_cloud":
            cfg.provider = "ollama"
        provider, model = resolve_active_model(cfg.provider, cfg.model)
        cfg.provider = provider
        cfg.model = model
        save_platform_llm_settings(provider=provider, model_id=model)
        await db.commit()
