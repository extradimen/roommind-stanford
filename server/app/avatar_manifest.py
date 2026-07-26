"""Normalize avatar_manifest JSON for storage and API responses."""

from __future__ import annotations

from typing import Any

from app.avatar_assets import resolve_model_url_for_client


def sanitize_avatar_manifest(raw: Any) -> dict[str, Any]:
    """Drop empty import URLs; enforce GLB-only style for 3D avatars."""
    if not isinstance(raw, dict):
        return {}
    manifest = dict(raw)
    for key in ("model_url", "image_url"):
        value = manifest.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            manifest.pop(key, None)
    # 3D meeting avatars are GLB-only; strip legacy image imports.
    manifest.pop("image_url", None)
    if manifest.get("model_url"):
        manifest["avatar_style"] = "gltf"
    return manifest


def client_avatar_manifest(raw: Any) -> dict[str, Any]:
    """Manifest fields safe to send to the game client."""
    manifest = sanitize_avatar_manifest(raw)
    model_url = resolve_model_url_for_client(manifest.get("model_url"))
    if model_url:
        manifest["model_url"] = model_url
    else:
        manifest.pop("model_url", None)
    return manifest
