"""Avatar asset storage helpers."""

from __future__ import annotations

import logging
import re
import subprocess
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".glb", ".gltf"}
WEB_GLB_SUFFIX = "-web"

AVATAR_DIR = Path(__file__).resolve().parent.parent / "data" / "avatars"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NATIVE_GLTFPACK = REPO_ROOT / "scripts" / "bin" / "gltfpack"


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


def resolve_model_url_for_client(url: str | None) -> str | None:
    """Map stored GLB URLs to lighter -web.glb builds when available."""
    trimmed = (url or "").strip()
    if not trimmed:
        return None
    prefix = "/static/avatars/"
    if not trimmed.startswith(prefix):
        return trimmed
    filename = trimmed[len(prefix) :]
    served = resolve_served_glb_path(filename)
    if served != filename:
        return public_avatar_url(served)
    return trimmed


def web_glb_filename(filename: str) -> str:
    path = Path(filename)
    return f"{path.stem}{WEB_GLB_SUFFIX}{path.suffix}"


def _gltfpack_command(source: Path, target: Path) -> list[str]:
    if NATIVE_GLTFPACK.exists():
        return [
            str(NATIVE_GLTFPACK),
            "-i",
            str(source),
            "-o",
            str(target),
            "-tc",
            "-si",
            "0.35",
        ]
    return [
        "npx",
        "--yes",
        "gltfpack",
        "-i",
        str(source),
        "-o",
        str(target),
        "-cc",
        "-si",
        "0.5",
    ]


def optimize_glb_for_web(source: Path) -> Path | None:
    """Create a lighter GLB for browser rendering via gltfpack."""
    if source.suffix.lower() != ".glb" or not source.exists():
        return None

    target = source.with_name(web_glb_filename(source.name))
    try:
        result = subprocess.run(
            _gltfpack_command(source, target),
            check=False,
            timeout=300,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("gltfpack failed for %s: %s", source.name, result.stderr[-500:])
            return None
        if target.exists() and target.stat().st_size > 0:
            return target
    except Exception as exc:
        logger.warning("gltfpack skipped for %s: %s", source.name, exc)
    return None


def resolve_served_glb_path(filename: str) -> str:
    """Prefer optimized -web.glb when present."""
    web_name = web_glb_filename(filename)
    if (AVATAR_DIR / web_name).exists():
        return web_name
    return filename

