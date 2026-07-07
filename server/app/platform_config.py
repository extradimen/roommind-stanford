"""Unified platform configuration (ports, hosts) — editable from admin."""

import json
import os
import re
import socket
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from starlette.requests import Request

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "config" / "platform.json"
ENV_PATH = ROOT_DIR / ".env"

AUTO_PUBLIC_HOST = "auto"

load_dotenv(ENV_PATH)


def is_auto_public_host(value: str | None) -> bool:
    if value is None:
        return True
    v = value.strip().lower()
    return v in ("", AUTO_PUBLIC_HOST, "localhost", "127.0.0.1", "0.0.0.0")


def _detect_outbound_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.5)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    try:
        out = subprocess.check_output(
            ["ip", "-4", "route", "get", "1.1.1.1"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        parts = out.split()
        if "src" in parts:
            idx = parts.index("src")
            if idx + 1 < len(parts):
                ip = parts[idx + 1]
                if ip and not ip.startswith("127."):
                    return ip
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def _fetch_public_ip() -> str | None:
    import urllib.request

    for url in (
        "http://checkip.amazonaws.com",
        "https://api.ipify.org",
    ):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                ip = resp.read().decode().strip()
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            continue
    return None


def detect_public_host() -> str:
    """Detect public IP (cloud-friendly); fallback to outbound/private IP."""
    public = _fetch_public_ip()
    if public:
        return public
    private = _detect_outbound_ip()
    if private:
        return private
    return "localhost"


def resolve_public_host(cfg: "PlatformConfig", env_override: str | None = None) -> str:
    """Resolve public host: explicit domain/IP > auto-detect."""
    env_val = env_override if env_override is not None else os.getenv("PUBLIC_HOST")
    if env_val and env_val.strip() and not is_auto_public_host(env_val):
        return env_val.strip()
    if cfg.hosts.public_host and not is_auto_public_host(cfg.hosts.public_host):
        return cfg.hosts.public_host.strip()
    return detect_public_host()


class PortsConfig(BaseModel):
    api: int = Field(ge=1024, le=65535, default=8800)
    admin: int = Field(ge=1024, le=65535, default=5180)
    client: int = Field(ge=1024, le=65535, default=5181)
    postgres: int = Field(ge=1024, le=65535, default=5434)
    redis: int = Field(ge=1024, le=65535, default=6380)


class HostsConfig(BaseModel):
    api_bind: str = "0.0.0.0"
    public_host: str = AUTO_PUBLIC_HOST


class DatabaseConfig(BaseModel):
    user: str = "roommind"
    password: str = "roommind_dev"
    name: str = "roommind"


class PlatformConfig(BaseModel):
    ports: PortsConfig = Field(default_factory=PortsConfig)
    hosts: HostsConfig = Field(default_factory=HostsConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    def database_url(self) -> str:
        p = self.ports
        d = self.database
        # 数据库/Redis 始终走本机，与对外访问域名/IP 无关
        return f"postgresql+asyncpg://{d.user}:{d.password}@127.0.0.1:{p.postgres}/{d.name}"

    def urls(self) -> dict[str, str]:
        return urls_for_host(self, resolve_public_host(self))

    def redis_url(self) -> str:
        return f"redis://127.0.0.1:{self.ports.redis}/0"


def urls_for_host(cfg: PlatformConfig, host: str) -> dict[str, str]:
    p = cfg.ports
    return {
        "api": f"http://{host}:{p.api}",
        "admin": f"http://{host}:{p.admin}",
        "client": f"http://{host}:{p.client}",
        "health": f"http://{host}:{p.api}/health",
    }


def resolve_client_host(request: Request | None, cfg: PlatformConfig) -> str:
    """Prefer browser Origin/Referer host; else configured or auto-detected host."""
    if request is not None:
        for raw in (request.headers.get("origin"), request.headers.get("referer")):
            if not raw:
                continue
            try:
                hostname = urlparse(raw).hostname
                if hostname and hostname not in ("localhost", "127.0.0.1"):
                    return hostname
            except Exception:
                continue
    return resolve_public_host(cfg)


def load_platform_config() -> PlatformConfig:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return PlatformConfig.model_validate(data)
    return PlatformConfig()


def load_platform_json_raw() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def write_platform_json(data: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_platform_config(config: PlatformConfig) -> None:
    raw = load_platform_json_raw()
    raw.update(config.model_dump())
    write_platform_json(raw)
    _sync_env_file(config)


def _sync_env_file(config: PlatformConfig) -> None:
    """Write port-related keys into .env for docker-compose and startup scripts."""
    p = config.ports
    d = config.database
    lines_map = {
        "API_HOST": config.hosts.api_bind,
        "API_PORT": str(p.api),
        "ADMIN_PORT": str(p.admin),
        "CLIENT_PORT": str(p.client),
        "POSTGRES_PORT": str(p.postgres),
        "REDIS_PORT": str(p.redis),
        "PUBLIC_HOST": config.hosts.public_host if not is_auto_public_host(config.hosts.public_host) else AUTO_PUBLIC_HOST,
        "DATABASE_URL": config.database_url(),
        "REDIS_URL": config.redis_url(),
        "POSTGRES_USER": d.user,
        "POSTGRES_PASSWORD": d.password,
        "POSTGRES_DB": d.name,
    }

    existing: dict[str, str] = {}
    order: list[str] = []
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#"):
                order.append(line)
                continue
            m = re.match(r"^([A-Z_]+)=(.*)$", line)
            if m:
                existing[m.group(1)] = m.group(2)
            order.append(line)

    for key, val in lines_map.items():
        existing[key] = val

    # Preserve secrets and other keys; rewrite file in stable order
    priority_keys = [
        "API_HOST", "API_PORT", "ADMIN_PORT", "CLIENT_PORT",
        "POSTGRES_PORT", "REDIS_PORT", "PUBLIC_HOST",
        "DATABASE_URL", "REDIS_URL",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
        "OLLAMA_API_KEY", "OLLAMA_BASE_URL",
        "OLLAMA_CLOUD_API_KEY", "OLLAMA_CLOUD_BASE_URL",
        "SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL",
        "ADMIN_SECRET",
    ]
    written: set[str] = set()
    out_lines: list[str] = []
    for key in priority_keys:
        if key in existing:
            out_lines.append(f"{key}={existing[key]}")
            written.add(key)
    for key, val in existing.items():
        if key not in written:
            out_lines.append(f"{key}={val}")

    ENV_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def update_env_vars(updates: dict[str, str]) -> None:
    """Merge key/value pairs into .env (used by admin UI for API keys)."""
    existing: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            m = re.match(r"^([A-Z_]+)=(.*)$", line)
            if m:
                existing[m.group(1)] = m.group(2)

    for key, val in updates.items():
        existing[key] = val

    priority_keys = [
        "API_HOST", "API_PORT", "ADMIN_PORT", "CLIENT_PORT",
        "POSTGRES_PORT", "REDIS_PORT", "PUBLIC_HOST",
        "DATABASE_URL", "REDIS_URL",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
        "OLLAMA_API_KEY", "OLLAMA_BASE_URL",
        "OLLAMA_CLOUD_API_KEY", "OLLAMA_CLOUD_BASE_URL",
        "SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL",
        "ADMIN_SECRET",
    ]
    written: set[str] = set()
    out_lines: list[str] = []
    for key in priority_keys:
        if key in existing:
            out_lines.append(f"{key}={existing[key]}")
            written.add(key)
    for key, val in existing.items():
        if key not in written:
            out_lines.append(f"{key}={val}")

    ENV_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    load_dotenv(ENV_PATH, override=True)


def remove_env_vars(keys: list[str]) -> None:
    """Remove keys from .env (e.g. stale LLM overrides after admin save)."""
    if not ENV_PATH.exists():
        return
    existing: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^([A-Z_]+)=(.*)$", line)
        if m:
            existing[m.group(1)] = m.group(2)
    for key in keys:
        existing.pop(key, None)
    priority_keys = [
        "API_HOST", "API_PORT", "ADMIN_PORT", "CLIENT_PORT",
        "POSTGRES_PORT", "REDIS_PORT", "PUBLIC_HOST",
        "DATABASE_URL", "REDIS_URL",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
        "OLLAMA_API_KEY", "OLLAMA_BASE_URL",
        "OLLAMA_CLOUD_API_KEY", "OLLAMA_CLOUD_BASE_URL",
        "SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL",
        "ADMIN_SECRET",
    ]
    written: set[str] = set()
    out_lines: list[str] = []
    for key in priority_keys:
        if key in existing:
            out_lines.append(f"{key}={existing[key]}")
            written.add(key)
    for key, val in existing.items():
        if key not in written:
            out_lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    load_dotenv(ENV_PATH, override=True)


def apply_platform_to_settings_dict() -> dict[str, Any]:
    """Deprecated helper — kept for scripts importing this module."""
    cfg = load_platform_config()
    return {
        "api_host": cfg.hosts.api_bind,
        "api_port": cfg.ports.api,
        "admin_port": cfg.ports.admin,
        "client_port": cfg.ports.client,
        "postgres_port": cfg.ports.postgres,
        "redis_port": cfg.ports.redis,
        "public_host": resolve_public_host(cfg),
        "database_url": cfg.database_url(),
        "redis_url": cfg.redis_url(),
    }
