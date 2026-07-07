"""LLM configuration — provider/model in platform.json; API keys via admin UI → .env."""

from __future__ import annotations

import os
from typing import Any, Literal

from dotenv import load_dotenv

from app.platform_config import ENV_PATH, load_platform_json_raw, remove_env_vars, update_env_vars, write_platform_json

LlmProvider = Literal["ollama", "siliconflow"]

DEFAULT_OLLAMA_MODEL_ID = "kimi-k2.5:cloud"
DEFAULT_SILICONFLOW_MODEL_ID = "moonshotai/Kimi-K2.5"
DEFAULT_OLLAMA_BASE_URL = "https://ollama.com"
DEFAULT_SILICONFLOW_BASE_URL = "https://api.siliconflow.com/v1"

DEFAULT_OLLAMA_CATALOG = [
    {"id": "kimi-k2.5:cloud", "name": "Kimi K2.5 Cloud"},
    {"id": "gpt-oss:120b:cloud", "name": "GPT-OSS 120B Cloud"},
    {"id": "deepseek-v3.2:cloud", "name": "DeepSeek V3.2 Cloud"},
]

DEFAULT_SILICONFLOW_CATALOG = [
    {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen2.5 7B（最小/速度测试）"},
    {"id": "Qwen/Qwen3-8B", "name": "Qwen3 8B"},
    {"id": "deepseek-ai/DeepSeek-V4-Flash", "name": "DeepSeek V4 Flash"},
    {"id": "moonshotai/Kimi-K2.5", "name": "Kimi K2.5"},
]


def _pick_admin_config(env_key: str, json_val: str | None, fallback: str) -> str:
    """Admin / platform.json wins over .env for provider & model."""
    if json_val is not None and str(json_val).strip():
        return str(json_val).strip()
    env_val = os.getenv(env_key)
    if env_val is not None and str(env_val).strip():
        return str(env_val).strip()
    return fallback


def _pick_str(env_key: str, json_val: str | None, fallback: str) -> str:
    env_val = os.getenv(env_key)
    if env_val is not None and str(env_val).strip():
        return str(env_val).strip()
    if json_val is not None and str(json_val).strip():
        return str(json_val).strip()
    return fallback


def _normalize_provider(value: str) -> LlmProvider:
    v = value.strip().lower()
    if v in ("ollama", "ollama_cloud"):
        return "ollama"
    return "siliconflow"


def load_ollama_catalog() -> list[dict[str, str]]:
    """Sync fallback catalog (live list: see ollama_catalog.fetch_ollama_cloud_catalog)."""
    from app.ollama_catalog import load_ollama_catalog_fallback

    return load_ollama_catalog_fallback()


def load_siliconflow_catalog() -> list[dict[str, str]]:
    pj = load_platform_json_raw()
    raw = pj.get("siliconflow", {}).get("models")
    if isinstance(raw, list) and raw:
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id", "")).strip()
            if mid:
                out.append({"id": mid, "name": str(item.get("name") or mid)})
        if out:
            return out
    return DEFAULT_SILICONFLOW_CATALOG.copy()


def available_models() -> dict[str, list[str]]:
    return {
        "ollama": [m["id"] for m in load_ollama_catalog()],
        "siliconflow": [m["id"] for m in load_siliconflow_catalog()],
    }


def resolve_llm_provider(db_provider: str | None = None) -> LlmProvider:
    pj = load_platform_json_raw()
    from_json = pj.get("llm", {}).get("provider")
    legacy = os.getenv("DEFAULT_LLM_PROVIDER")
    fallback = db_provider or (legacy.strip() if legacy and legacy.strip() else None) or "siliconflow"
    raw = _pick_admin_config("LLM_PROVIDER", str(from_json) if from_json else None, fallback)
    return _normalize_provider(raw)


def mask_api_key(key: str) -> str:
    key = key.strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}…{key[-4:]}"


def get_llm_keys_status() -> dict[str, Any]:
    sf = resolve_siliconflow_api_key()
    ol = resolve_ollama_api_key()
    return {
        "siliconflow": {"configured": bool(sf), "masked": mask_api_key(sf)},
        "ollama": {"configured": bool(ol), "masked": mask_api_key(ol)},
        "storage": ".env（通过管理后台保存）",
    }


def save_llm_api_keys(
    *,
    siliconflow_api_key: str | None = None,
    ollama_api_key: str | None = None,
) -> dict[str, Any]:
    """Persist API keys from admin UI into .env (+ mirror flags in platform.json)."""
    updates: dict[str, str] = {}
    raw = load_platform_json_raw()

    if siliconflow_api_key is not None:
        updates["SILICONFLOW_API_KEY"] = siliconflow_api_key.strip()
        raw.setdefault("siliconflow", {})["apiKeyConfigured"] = bool(siliconflow_api_key.strip())

    if ollama_api_key is not None:
        key = ollama_api_key.strip()
        updates["OLLAMA_API_KEY"] = key
        updates["OLLAMA_CLOUD_API_KEY"] = key
        raw.setdefault("ollama", {})["apiKeyConfigured"] = bool(key)

    if updates:
        update_env_vars(updates)
        write_platform_json(raw)

    load_dotenv(ENV_PATH, override=True)
    return get_llm_keys_status()


def resolve_ollama_api_key() -> str:
    pj = load_platform_json_raw()
    from_json = pj.get("ollama", {}).get("apiKey")
    key = os.getenv("OLLAMA_API_KEY")
    if key and key.strip():
        return key.strip()
    legacy = os.getenv("OLLAMA_CLOUD_API_KEY")
    if legacy and legacy.strip():
        return legacy.strip()
    if from_json and str(from_json).strip():
        return str(from_json).strip()
    return ""


def resolve_siliconflow_api_key() -> str:
    pj = load_platform_json_raw()
    from_json = pj.get("siliconflow", {}).get("apiKey")
    return _pick_str("SILICONFLOW_API_KEY", str(from_json) if from_json else None, "")


def resolve_ollama_base_url() -> str:
    pj = load_platform_json_raw()
    from_json = pj.get("ollama", {}).get("baseUrl")
    url = _pick_str("OLLAMA_BASE_URL", str(from_json) if from_json else None, DEFAULT_OLLAMA_BASE_URL)
    legacy = os.getenv("OLLAMA_CLOUD_BASE_URL")
    if legacy and legacy.strip() and not os.getenv("OLLAMA_BASE_URL"):
        url = legacy.strip()
    return url.rstrip("/")


def resolve_siliconflow_base_url() -> str:
    pj = load_platform_json_raw()
    from_json = pj.get("siliconflow", {}).get("baseUrl")
    return _pick_str(
        "SILICONFLOW_BASE_URL",
        str(from_json) if from_json else None,
        DEFAULT_SILICONFLOW_BASE_URL,
    ).rstrip("/")


def resolve_ollama_model_id(db_model: str | None = None) -> str:
    pj = load_platform_json_raw()
    from_json = pj.get("ollama", {}).get("modelId")
    preferred = _pick_admin_config(
        "OLLAMA_MODEL_ID",
        str(from_json) if from_json else None,
        db_model or DEFAULT_OLLAMA_MODEL_ID,
    )
    if preferred:
        return preferred
    catalog = load_ollama_catalog()
    return catalog[0]["id"] if catalog else DEFAULT_OLLAMA_MODEL_ID


def resolve_siliconflow_model_id(db_model: str | None = None) -> str:
    pj = load_platform_json_raw()
    from_json = pj.get("siliconflow", {}).get("modelId")
    catalog = load_siliconflow_catalog()
    preferred = _pick_admin_config(
        "SILICONFLOW_MODEL_ID",
        str(from_json) if from_json else None,
        db_model or DEFAULT_SILICONFLOW_MODEL_ID,
    )
    if any(m["id"] == preferred for m in catalog):
        return preferred
    return catalog[0]["id"]


def resolve_active_model(db_provider: str | None = None, db_model: str | None = None) -> tuple[LlmProvider, str]:
    if db_provider == "ollama_cloud":
        db_provider = "ollama"

    explicit_provider = str(db_provider).strip() if db_provider and str(db_provider).strip() else None
    explicit_model = str(db_model).strip() if db_model and str(db_model).strip() else None

    # Per-scenario orchestration / DB llm_config overrides win over platform.json defaults.
    if explicit_provider:
        provider = _normalize_provider(explicit_provider)
    else:
        provider = resolve_llm_provider(None)

    if provider == "ollama":
        if explicit_model:
            return provider, explicit_model
        return provider, resolve_ollama_model_id(None)
    if explicit_model:
        return provider, explicit_model
    return provider, resolve_siliconflow_model_id(None)


def llm_status_dict(db_provider: str | None = None, db_model: str | None = None) -> dict[str, Any]:
    provider, model = resolve_active_model(db_provider, db_model)
    pj = load_platform_json_raw()
    json_provider = str(pj.get("llm", {}).get("provider") or "").strip()
    warnings: list[str] = []
    if json_provider:
        warnings.append("提供商与模型由管理后台 (platform.json) 控制")
    else:
        env_provider = os.getenv("LLM_PROVIDER", "").strip()
        if env_provider:
            warnings.append(f"LLM_PROVIDER={env_provider} 来自 .env（建议在管理后台保存）")

    return {
        "provider": provider,
        "model": model,
        "ollama_key_configured": bool(resolve_ollama_api_key()),
        "siliconflow_key_configured": bool(resolve_siliconflow_api_key()),
        "ollama_base_url": resolve_ollama_base_url(),
        "siliconflow_base_url": resolve_siliconflow_base_url(),
        "env_overrides": warnings,
        "keys_storage": ".env（管理后台保存）",
        "key_env_vars": {
            "ollama": "OLLAMA_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
        },
    }


def save_platform_llm_settings(*, provider: str, model_id: str) -> None:
    """Persist provider/model to platform.json."""
    provider = _normalize_provider(provider)
    raw = load_platform_json_raw()
    raw["llm"] = {"provider": provider}
    if provider == "ollama":
        ollama = raw.setdefault("ollama", {})
        ollama["modelId"] = model_id
        ollama.setdefault("baseUrl", DEFAULT_OLLAMA_BASE_URL)
        ollama.pop("models", None)
    else:
        sf = raw.setdefault("siliconflow", {})
        sf["modelId"] = model_id
        sf.setdefault("baseUrl", DEFAULT_SILICONFLOW_BASE_URL)
        sf.setdefault("models", DEFAULT_SILICONFLOW_CATALOG)
    write_platform_json(raw)
    remove_env_vars([
        "LLM_PROVIDER",
        "OLLAMA_MODEL_ID",
        "SILICONFLOW_MODEL_ID",
        "DEFAULT_LLM_PROVIDER",
        "DEFAULT_LLM_MODEL",
    ])
    load_dotenv(ENV_PATH, override=True)


def _merge_model_catalog(
    existing: list[Any] | None, defaults: list[dict[str, str]]
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id", "")).strip()
            if mid and mid not in seen:
                merged.append({"id": mid, "name": str(item.get("name") or mid)})
                seen.add(mid)
    for item in defaults:
        if item["id"] not in seen:
            merged.append(item)
            seen.add(item["id"])
    return merged or defaults.copy()


def ensure_platform_llm_defaults() -> None:
    raw = load_platform_json_raw()
    defaults = default_platform_llm_json()
    changed = False
    for key, val in defaults.items():
        if key not in raw:
            raw[key] = val
            changed = True
    ollama = raw.setdefault("ollama", {})
    sf = raw.setdefault("siliconflow", {})
    merged_sf = _merge_model_catalog(sf.get("models"), DEFAULT_SILICONFLOW_CATALOG)
    if sf.get("models") != merged_sf:
        sf["models"] = merged_sf
        changed = True
    if ollama.pop("models", None) is not None:
        changed = True
    if changed:
        write_platform_json(raw)


def default_platform_llm_json() -> dict[str, Any]:
    return {
        "llm": {"provider": "siliconflow"},
        "ollama": {
            "apiKey": "",
            "baseUrl": DEFAULT_OLLAMA_BASE_URL,
            "modelId": DEFAULT_OLLAMA_MODEL_ID,
        },
        "siliconflow": {
            "apiKey": "",
            "baseUrl": DEFAULT_SILICONFLOW_BASE_URL,
            "modelId": DEFAULT_SILICONFLOW_MODEL_ID,
            "models": DEFAULT_SILICONFLOW_CATALOG,
        },
    }
