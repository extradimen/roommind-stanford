"""Export/import 3D scene visual config separately from scenario content bundle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.avatar_manifest import sanitize_avatar_manifest
from app.models.db import CharacterTemplate, ScenarioTemplate
from app.scene_graph import sanitize_plot_cast_binding, sanitize_scene_graph

VISUAL_SCENE_KEYS = (
    "environment",
    "lighting",
    "camera",
    "spawn",
    "seat_layout",
    "scene_graph",
    "plot_cast_binding",
)

VISUAL_BUNDLE_FORMAT = "roommind-scene-visual-bundle"
VISUAL_BUNDLE_VERSION = 1


def empty_gltf_manifest() -> dict[str, Any]:
    return {"avatar_style": "gltf"}


def pick_visual_scene_config(scene_config: Any) -> dict[str, Any]:
    if not isinstance(scene_config, dict):
        return {}
    out = {key: scene_config[key] for key in VISUAL_SCENE_KEYS if key in scene_config}
    if "scene_graph" in scene_config:
        out["scene_graph"] = sanitize_scene_graph(scene_config.get("scene_graph"))
    if "plot_cast_binding" in scene_config:
        out["plot_cast_binding"] = sanitize_plot_cast_binding(scene_config.get("plot_cast_binding"))
    return out


def strip_content_scene_config(scene_config: Any) -> dict[str, Any]:
    """Remove visual-only keys and player avatar from scenario content export."""
    if not isinstance(scene_config, dict):
        return {}
    out = dict(scene_config)
    for key in VISUAL_SCENE_KEYS:
        out.pop(key, None)
    pc = out.get("player_character")
    if isinstance(pc, dict):
        pc = dict(pc)
        pc.pop("avatar_manifest", None)
        if pc:
            out["player_character"] = pc
        else:
            out.pop("player_character", None)
    return out


def merge_content_scene_config(incoming: Any, existing: Any) -> dict[str, Any]:
    """Apply scenario content import without overwriting scene visual state."""
    incoming_dict = incoming if isinstance(incoming, dict) else {}
    existing_dict = existing if isinstance(existing, dict) else {}
    out = dict(incoming_dict)

    in_pc = incoming_dict.get("player_character")
    ex_pc = existing_dict.get("player_character")
    in_pc = dict(in_pc) if isinstance(in_pc, dict) else {}
    ex_pc = dict(ex_pc) if isinstance(ex_pc, dict) else {}
    merged_pc = {**ex_pc, **{k: v for k, v in in_pc.items() if k != "avatar_manifest"}}
    merged_pc["avatar_manifest"] = sanitize_avatar_manifest(ex_pc.get("avatar_manifest")) or empty_gltf_manifest()
    out["player_character"] = merged_pc

    for key in VISUAL_SCENE_KEYS:
        if key in existing_dict:
            out[key] = existing_dict[key]
    return out


def export_scene_visual_bundle(
    scenario: ScenarioTemplate,
    characters: list[CharacterTemplate],
) -> dict[str, Any]:
    scene = scenario.scene_config if isinstance(scenario.scene_config, dict) else {}
    pc = scene.get("player_character") if isinstance(scene.get("player_character"), dict) else {}
    chars = sorted(characters, key=lambda c: (c.sort_order, c.id))
    return {
        "export_meta": {
            "format": VISUAL_BUNDLE_FORMAT,
            "version": VISUAL_BUNDLE_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "scenario_id": scenario.id,
            "scenario_slug": scenario.slug,
            "note": "3D avatars and meeting-room visual config only. Import on Scene visual / Web3D Studio page.",
        },
        "visual_scene_config": pick_visual_scene_config(scene),
        "player_avatar_manifest": sanitize_avatar_manifest(pc.get("avatar_manifest")) or empty_gltf_manifest(),
        "character_avatars": [
            {
                "character_id": char.character_id,
                "avatar_manifest": sanitize_avatar_manifest(char.avatar_manifest) or empty_gltf_manifest(),
            }
            for char in chars
            if char.character_id
        ],
    }


def validate_scene_visual_bundle(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Import body must be a JSON object")
    if data.get("character_avatars") is not None and not isinstance(data["character_avatars"], list):
        raise ValueError("character_avatars must be an array")
    if data.get("visual_scene_config") is not None and not isinstance(data["visual_scene_config"], dict):
        raise ValueError("visual_scene_config must be an object")
    return data


async def apply_scene_visual_bundle(
    db: AsyncSession,
    scenario: ScenarioTemplate,
    data: dict[str, Any],
) -> ScenarioTemplate:
    payload = validate_scene_visual_bundle(data)
    scene = dict(scenario.scene_config) if isinstance(scenario.scene_config, dict) else {}

    visual = payload.get("visual_scene_config")
    if isinstance(visual, dict):
        for key in VISUAL_SCENE_KEYS:
            if key in visual:
                scene[key] = visual[key]
        if "scene_graph" in visual:
            scene["scene_graph"] = sanitize_scene_graph(visual.get("scene_graph"))
        if "plot_cast_binding" in visual:
            scene["plot_cast_binding"] = sanitize_plot_cast_binding(visual.get("plot_cast_binding"))

    pc = scene.get("player_character")
    pc = dict(pc) if isinstance(pc, dict) else {}
    player_manifest = sanitize_avatar_manifest(payload.get("player_avatar_manifest"))
    if player_manifest.get("model_url"):
        pc["avatar_manifest"] = player_manifest
    else:
        pc.setdefault("avatar_manifest", empty_gltf_manifest())
    scene["player_character"] = pc
    scenario.scene_config = scene

    avatar_by_id: dict[str, dict[str, Any]] = {}
    for raw in payload.get("character_avatars") or []:
        if not isinstance(raw, dict) or not raw.get("character_id"):
            continue
        manifest = sanitize_avatar_manifest(raw.get("avatar_manifest"))
        if manifest.get("model_url"):
            avatar_by_id[str(raw["character_id"])] = manifest

    result = await db.execute(
        select(CharacterTemplate).where(CharacterTemplate.scenario_id == scenario.id)
    )
    for char in result.scalars().all():
        manifest = avatar_by_id.get(char.character_id)
        if manifest:
            char.avatar_manifest = manifest

    await db.flush()
    refreshed = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario.id)
        .options(selectinload(ScenarioTemplate.characters))
    )
    return refreshed.scalar_one()
