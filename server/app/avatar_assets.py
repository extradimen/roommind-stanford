"""Avatar asset storage helpers."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".glb", ".gltf"}

AVATAR_DIR = Path(__file__).resolve().parent.parent / "data" / "avatars"


def ensure_avatar_dir() -> Path:
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    return AVATAR_DIR


def sanitize_upload_filename(name: str) -> str:
    base = Path(name).name
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(base).stem).strip("-._") or "avatar"
    ext = Path(base).suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or '(none)'}")
    return f"{stem}-{uuid.uuid4().hex[:8]}{ext}"


def public_avatar_url(filename: str) -> str:
    return f"/static/avatars/{filename}"
