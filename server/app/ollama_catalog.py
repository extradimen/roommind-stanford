"""Live Ollama Cloud model catalog — fetched from ollama.com on each admin request."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from app.platform_llm import (
    DEFAULT_OLLAMA_CATALOG,
    DEFAULT_OLLAMA_MODEL_ID,
    load_platform_json_raw,
    resolve_ollama_api_key,
    resolve_ollama_base_url,
)


def _format_display_name(model_id: str, raw: dict[str, Any] | None = None) -> str:
    if raw:
        details = raw.get("details")
        if isinstance(details, dict):
            param_size = details.get("parameter_size")
            if param_size:
                return f"{model_id} ({param_size})"
    return model_id


def load_ollama_catalog_fallback() -> list[dict[str, str]]:
    """Static fallback when live fetch fails (includes saved modelId)."""
    pj = load_platform_json_raw()
    current = str(pj.get("ollama", {}).get("modelId") or "").strip()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    if current:
        out.append({"id": current, "name": _format_display_name(current)})
        seen.add(current)
    for item in DEFAULT_OLLAMA_CATALOG:
        mid = item["id"]
        if mid not in seen:
            out.append({"id": mid, "name": str(item.get("name") or mid)})
            seen.add(mid)
    if not out:
        out.append({"id": DEFAULT_OLLAMA_MODEL_ID, "name": DEFAULT_OLLAMA_MODEL_ID})
    return out


def _merge_extra_models(
    catalog: list[dict[str, str]],
    extra_ids: list[str],
) -> list[dict[str, str]]:
    seen = {m["id"] for m in catalog}
    merged = list(catalog)
    for mid in extra_ids:
        mid = mid.strip()
        if mid and mid not in seen:
            merged.insert(0, {"id": mid, "name": _format_display_name(mid)})
            seen.add(mid)
    return merged


def _parse_tags_payload(data: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in data.get("models") or []:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("name") or item.get("model") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append({"id": mid, "name": _format_display_name(mid, item)})
    out.sort(key=lambda m: m["id"].lower())
    return out


def _parse_openai_models_payload(data: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in data.get("data") or []:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append({"id": mid, "name": _format_display_name(mid, item)})
    out.sort(key=lambda m: m["id"].lower())
    return out


def _merge_catalogs(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for group in groups:
        for item in group:
            mid = str(item.get("id") or "").strip()
            if not mid:
                continue
            name = str(item.get("name") or mid).strip() or mid
            if mid not in merged or len(name) > len(merged[mid]["name"]):
                merged[mid] = {"id": mid, "name": name}
    return sorted(merged.values(), key=lambda m: m["id"].lower())


async def _fetch_ollama_website_cloud_catalog(client: httpx.AsyncClient) -> list[dict[str, str]]:
    """Parse ollama.com/search?c=cloud — public cloud model library page."""
    try:
        resp = await client.get("https://ollama.com/search?c=cloud", follow_redirects=True)
        if resp.status_code >= 400:
            return []
        names = re.findall(r'href="/library/([^"/?#]+)"', resp.text)
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in names:
            mid = raw.strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            out.append({"id": mid, "name": mid})
        return sorted(out, key=lambda m: m["id"].lower())
    except Exception:
        return []


async def fetch_ollama_cloud_catalog(
    *,
    extra_model_ids: list[str] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Fetch latest cloud models from ollama.com (live, not cached)."""
    base = resolve_ollama_base_url().rstrip("/")
    key = resolve_ollama_api_key()
    meta: dict[str, Any] = {
        "source": f"{base}/api/tags + ollama.com/search?c=cloud",
        "fetched_at": datetime.now(UTC).isoformat(),
        "live": True,
        "error": None,
        "count": 0,
        "website_count": 0,
        "api_count": 0,
    }
    fallback = load_ollama_catalog_fallback()
    extras = extra_model_ids or []

    headers = {"Authorization": f"Bearer {key}"} if key else {}
    tags_catalog: list[dict[str, str]] = []
    v1_catalog: list[dict[str, str]] = []
    website_catalog: list[dict[str, str]] = []
    last_error: str | None = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        website_catalog = await _fetch_ollama_website_cloud_catalog(client)
        meta["website_count"] = len(website_catalog)

        if not key:
            if website_catalog:
                catalog = _merge_catalogs(website_catalog)
                meta["source"] = "https://ollama.com/search?c=cloud"
                meta["count"] = len(_merge_extra_models(catalog, extras))
                meta["error"] = "Ollama API Key 未配置，当前仅显示官网 Cloud 模型目录"
                return _merge_extra_models(catalog, extras), meta
            meta["live"] = False
            meta["error"] = "Ollama API Key 未配置，无法从 ollama.com 拉取模型列表"
            return _merge_extra_models(fallback, extras), meta

        tags_url = f"{base}/api/tags"
        try:
            resp = await client.get(tags_url, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            tags_catalog = _parse_tags_payload(resp.json())
            meta["api_count"] = len(tags_catalog)
        except Exception as exc:
            last_error = f"/api/tags: {exc}"

        v1_url = f"{base}/v1/models"
        try:
            resp = await client.get(v1_url, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            v1_catalog = _parse_openai_models_payload(resp.json())
            if not tags_catalog:
                meta["api_count"] = len(v1_catalog)
        except Exception as exc:
            if not tags_catalog:
                last_error = f"{last_error}; /v1/models: {exc}" if last_error else f"/v1/models: {exc}"

    catalog = _merge_catalogs(website_catalog, tags_catalog, v1_catalog)
    if not catalog:
        meta["live"] = False
        meta["error"] = last_error or "Ollama 未返回任何模型"
        return _merge_extra_models(fallback, extras), meta

    if last_error and website_catalog:
        meta["error"] = f"API 拉取部分失败（已合并官网目录）: {last_error}"

    catalog = _merge_extra_models(catalog, extras)
    meta["count"] = len(catalog)
    return catalog, meta
