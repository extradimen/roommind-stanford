"""Resolve the human player's identity from scenario scene_config."""

from __future__ import annotations

from typing import Any

from app.avatar_manifest import sanitize_avatar_manifest
from app.avatar_assets import resolve_model_url_for_client
from app.character_display import compose_display_name, normalize_character_fields
from app.models.db import ScenarioTemplate

DEFAULT_PLAYER_AVATAR: dict[str, Any] = {
    "avatar_style": "gltf",
}

def resolve_player_character(scenario: ScenarioTemplate) -> dict[str, Any]:
    """Return normalized player identity for UI and agent prompts."""
    scene = scenario.scene_config if isinstance(scenario.scene_config, dict) else {}
    raw = scene.get("player_character") if isinstance(scene.get("player_character"), dict) else {}

    name, title, display = normalize_character_fields(
        character_name=str(raw.get("character_name") or ""),
        job_title=str(raw.get("job_title") or ""),
        display_name=str(raw.get("display_name") or ""),
    )

    if not name and not title:
        terminology = (scenario.task_config or {}).get("terminology") or {}
        name = str(terminology.get("player_name") or "Player")
        title = str(terminology.get("player_role") or "Participant")
        display = compose_display_name(name, title)

    manifest = sanitize_avatar_manifest(raw.get("avatar_manifest"))
    model_url = resolve_model_url_for_client(manifest.get("model_url"))
    if model_url:
        manifest["model_url"] = model_url
    elif "model_url" in manifest:
        manifest.pop("model_url", None)
    manifest.setdefault("avatar_style", "gltf")

    return {
        "character_id": "user",
        "character_name": name,
        "job_title": title,
        "display_name": display,
        "avatar_manifest": manifest,
    }
