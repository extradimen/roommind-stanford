import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.game import router as game_router
from app.avatar_assets import AVATAR_DIR, ensure_avatar_dir
from app.config import get_settings, reload_settings
from app.database import init_db
from app.platform_llm import ensure_platform_llm_defaults
from app.seed import (
    ensure_scenario_templates,
    seed_if_empty,
    sync_character_name_fields,
    sync_dispatch_rule_keywords,
    sync_llm_config_with_platform,
    sync_scenario_orchestration_config,
    sync_scenario_side_goals,
    sync_scenario_player_characters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="RoomMind API",
    description="Multi-agent business negotiation platform — Phase 1 Web3D Text",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(game_router)

ensure_avatar_dir()
app.mount("/static/avatars", StaticFiles(directory=str(AVATAR_DIR)), name="avatar_assets")


@app.on_event("startup")
async def startup() -> None:
    reload_settings()
    ensure_platform_llm_defaults()
    await init_db()
    await seed_if_empty()
    await ensure_scenario_templates()
    await sync_character_name_fields()
    await sync_scenario_side_goals()
    await sync_scenario_player_characters()
    await sync_scenario_orchestration_config()
    await sync_dispatch_rule_keywords()
    await sync_llm_config_with_platform()
    reload_settings()
    logger.info("RoomMind API started on port %s", settings.api_port)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "phase": "1-web3d-text"}


@app.get("/api/info")
async def info() -> dict:
    s = get_settings()
    from app.platform_config import load_platform_config

    cfg = load_platform_config()
    return {
        "name": "RoomMind",
        "phases": {
            "1": "Web3D + Text (current)",
            "2": "Web3D + Voice",
            "3": "UE5 + Voice",
        },
        "ports": cfg.ports.model_dump(),
        "urls": cfg.urls(),
        "public_host": s.public_host,
    }


@app.get("/api/platform/ports")
async def public_ports(request: Request) -> dict:
    """Public port info for frontends (no auth)."""
    from app.platform_config import load_platform_config, resolve_client_host, urls_for_host

    cfg = load_platform_config()
    host = resolve_client_host(request, cfg)
    return {
        "ports": cfg.ports.model_dump(),
        "urls": urls_for_host(cfg, host),
        "public_host": host,
    }
