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

    # Derive the player's public authority from the same configured
    # permissions used by task-state confirmation. Without this projection an
    # autonomous player is incorrectly treated as unauthorized when accepting
    # a term that explicitly lists ``player`` as a confirmer.
    configured_authority = raw.get("authority") if isinstance(raw.get("authority"), dict) else {}
    authority = dict(configured_authority)
    can_propose = set(authority.get("can_propose") or [])
    can_confirm = set(authority.get("can_confirm") or [])
    can_execute = set(authority.get("can_execute") or [])
    for field, field_schema in ((scenario.task_config or {}).get("state_schema") or {}).items():
        if not isinstance(field_schema, dict):
            continue
        proposers = {str(value) for value in (field_schema.get("propose_permissions") or [])}
        confirmers = {str(value) for value in (field_schema.get("confirm_permissions") or [])}
        executors = {str(value) for value in (field_schema.get("execute_permissions") or [])}
        if not proposers or proposers.intersection({"player", "user"}):
            can_propose.add(str(field))
        if confirmers.intersection({"player", "user"}):
            can_confirm.add(str(field))
        if executors.intersection({"player", "user"}):
            can_execute.add(str(field))
    authority["can_propose"] = sorted(can_propose)
    authority["can_confirm"] = sorted(can_confirm)
    authority["can_execute"] = sorted(can_execute)

    return {
        "character_id": "user",
        "character_name": name,
        "job_title": title,
        "display_name": display,
        "avatar_manifest": manifest,
        "authority": authority,
    }
