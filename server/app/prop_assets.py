"""Scene prop (furniture / environment) asset storage."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.avatar_assets import ALLOWED_AVATAR_EXTENSIONS, optimize_glb_for_web

PROPS_DIR = Path(__file__).resolve().parent.parent / "data" / "props"


def ensure_props_dir() -> Path:
    PROPS_DIR.mkdir(parents=True, exist_ok=True)
    return PROPS_DIR


def sanitize_prop_filename(name: str) -> str:
    base = Path(name).name
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(base).stem).strip("-._") or "prop"
    ext = Path(base).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or '(none)'}")
    return f"{stem}-{uuid.uuid4().hex[:8]}{ext}"


def public_prop_url(filename: str) -> str:
    return f"/static/props/{filename}"


def store_prop_upload(filename: str, data: bytes) -> dict[str, str]:
    target = ensure_props_dir() / filename
    target.write_bytes(data)
    served_name = filename
    optimized = False
    if filename.lower().endswith(".glb"):
        web_target = optimize_glb_for_web(target)
        if web_target:
            served_name = web_target.name
            optimized = True
    payload: dict[str, str] = {
        "url": public_prop_url(served_name),
        "filename": served_name,
    }
    if optimized:
        payload["optimized"] = "true"
        payload["original_filename"] = filename
    return payload
