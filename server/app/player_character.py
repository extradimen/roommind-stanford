"""Resolve the human player's identity from scenario scene_config."""

from __future__ import annotations

from typing import Any

from app.character_display import compose_display_name, normalize_character_fields
from app.models.db import ScenarioTemplate

DEFAULT_PLAYER_AVATAR: dict[str, Any] = {
    "suit": "#1e5631",
    "accent": "#58a6ff",
    "skin": "#e8b896",
    "pattern": "global",
    "accessory": "none",
    "height": 1.72,
}

SLUG_PLAYER_DEFAULTS: dict[str, dict[str, str]] = {
    "global-smart-manufacturing-supply-chain-negotiation": {
        "character_name": "James Park",
        "job_title": "Director of Strategic Procurement",
    },
    "supply-chain-negotiation": {
        "character_name": "Alex Chen",
        "job_title": "Chief Procurement Officer",
    },
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
        slug_defaults = SLUG_PLAYER_DEFAULTS.get(scenario.slug or "", {})
        name = slug_defaults.get("character_name", "Alex Chen")
        title = slug_defaults.get("job_title", "Chief Procurement Officer")
        display = compose_display_name(name, title)

    manifest = dict(raw.get("avatar_manifest") or {})
    for key, value in DEFAULT_PLAYER_AVATAR.items():
        manifest.setdefault(key, value)

    return {
        "character_id": "user",
        "character_name": name,
        "job_title": title,
        "display_name": display,
        "avatar_manifest": manifest,
    }
