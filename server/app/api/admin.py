from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings, reload_settings
from app.database import get_db
from app.ollama_catalog import fetch_ollama_cloud_catalog
from app.platform_llm import (
    get_llm_keys_status,
    llm_status_dict,
    load_siliconflow_catalog,
    save_llm_api_keys,
    save_platform_llm_settings,
)
from app.memory.service import memory_service
from app.agent.debug_payload import load_agent_memories_grouped, load_character_names
from app.models.db import (
    CharacterTemplate,
    DispatchRule,
    GameSession,
    LLMConfig,
    ScenarioTemplate,
    SessionMessage,
)
from app.orchestrator.defaults import ORCHESTRATION_MODE, merge_orchestration_config
from app.platform_config import CONFIG_PATH, ENV_PATH, PlatformConfig, load_platform_config, resolve_client_host, resolve_public_host, save_platform_config, urls_for_host
from app.schemas import (
    CharacterTemplateIn,
    CharacterTemplateOut,
    DispatchRuleIn,
    DispatchRuleOut,
    LLMConfigOut,
    LLMConfigUpdate,
    LLMKeysOut,
    LLMKeysUpdate,
    LLMProvidersOut,
    OrchestrationConfigIn,
    PlatformConfigIn,
    PlatformConfigOut,
    ScenarioListItem,
    ScenarioTemplateIn,
    ScenarioTemplateOut,
    SessionDebugOut,
    SessionListItem,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def verify_admin(x_admin_secret: Annotated[str | None, Header()] = None) -> None:
    if x_admin_secret != get_settings().admin_secret:
        raise HTTPException(status_code=401, detail="Invalid admin secret")


AdminDep = Annotated[None, Depends(verify_admin)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/llm/status")
async def llm_status(db: DbDep, _: AdminDep) -> dict:
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1))
    active = result.scalar_one_or_none()
    db_prov = active.provider if active else None
    if db_prov == "ollama_cloud":
        db_prov = "ollama"
    status = llm_status_dict(db_prov, active.model if active else None)
    status["env_file"] = str(ENV_PATH)
    status["config_file"] = str(CONFIG_PATH)
    return status


@router.get("/llm/providers", response_model=LLMProvidersOut)
async def list_llm_providers(db: DbDep, _: AdminDep, response: Response) -> LLMProvidersOut:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1))
    active = result.scalar_one_or_none()
    extra: list[str] = []
    if active and active.model:
        extra.append(active.model)
    ollama_catalog, ollama_meta = await fetch_ollama_cloud_catalog(extra_model_ids=extra)
    sf_catalog = load_siliconflow_catalog()
    return LLMProvidersOut(
        providers={
            "ollama": [m["id"] for m in ollama_catalog],
            "siliconflow": [m["id"] for m in sf_catalog],
        },
        catalogs={
            "ollama": ollama_catalog,
            "siliconflow": sf_catalog,
        },
        meta={"ollama": ollama_meta},
    )


@router.get("/llm/config", response_model=LLMConfigOut | None)
async def get_llm_config(db: DbDep, _: AdminDep) -> LLMConfig | None:
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_active.is_(True)).limit(1))
    return result.scalar_one_or_none()


@router.put("/llm/config/{config_id}", response_model=LLMConfigOut)
async def update_llm_config(config_id: int, body: LLMConfigUpdate, db: DbDep, _: AdminDep) -> LLMConfig:
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Config not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "provider" and isinstance(v, str):
            v = "ollama" if v in ("ollama", "ollama_cloud") else "siliconflow"
        setattr(cfg, k, v)
    save_platform_llm_settings(provider=cfg.provider, model_id=cfg.model)
    reload_settings()
    await db.flush()
    await db.refresh(cfg)
    return cfg


@router.get("/llm/keys", response_model=LLMKeysOut)
async def get_llm_keys(_: AdminDep) -> LLMKeysOut:
    data = get_llm_keys_status()
    return LLMKeysOut(**data)


@router.put("/llm/keys", response_model=LLMKeysOut)
async def update_llm_keys(body: LLMKeysUpdate, _: AdminDep) -> LLMKeysOut:
    data = save_llm_api_keys(
        siliconflow_api_key=body.siliconflow_api_key,
        ollama_api_key=body.ollama_api_key,
    )
    reload_settings()
    return LLMKeysOut(**data)


@router.get("/scenarios", response_model=list[ScenarioListItem])
async def list_scenarios(db: DbDep, _: AdminDep) -> list[ScenarioListItem]:
    result = await db.execute(
        select(
            ScenarioTemplate.id,
            ScenarioTemplate.slug,
            ScenarioTemplate.title,
            ScenarioTemplate.description,
            ScenarioTemplate.is_published,
            func.count(CharacterTemplate.id).label("character_count"),
        )
        .outerjoin(CharacterTemplate, CharacterTemplate.scenario_id == ScenarioTemplate.id)
        .group_by(ScenarioTemplate.id)
        .order_by(ScenarioTemplate.id.desc())
    )
    rows = result.all()

    return [
        ScenarioListItem(
            id=r.id,
            slug=r.slug,
            title=r.title,
            description=r.description,
            is_published=r.is_published,
            character_count=r.character_count,
        )
        for r in rows
    ]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioTemplateOut)
async def get_scenario(scenario_id: int, db: DbDep, _: AdminDep) -> ScenarioTemplate:
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario_id)
        .options(selectinload(ScenarioTemplate.characters))
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    return scenario


@router.post("/scenarios", response_model=ScenarioTemplateOut)
async def create_scenario(body: ScenarioTemplateIn, db: DbDep, _: AdminDep) -> ScenarioTemplate:
    scenario = ScenarioTemplate(
        slug=body.slug,
        title=body.title,
        description=body.description,
        business_goal=body.business_goal,
        phases=body.phases,
        win_conditions=body.win_conditions,
        scene_config=body.scene_config,
        orchestration_config=body.orchestration_config,
        is_published=body.is_published,
    )
    db.add(scenario)
    await db.flush()

    for idx, c in enumerate(body.characters):
        char = CharacterTemplate(scenario_id=scenario.id, sort_order=c.sort_order or idx, **c.model_dump())
        db.add(char)

    await db.flush()
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario.id)
        .options(selectinload(ScenarioTemplate.characters))
    )
    return result.scalar_one()


@router.put("/scenarios/{scenario_id}", response_model=ScenarioTemplateOut)
async def update_scenario(scenario_id: int, body: ScenarioTemplateIn, db: DbDep, _: AdminDep) -> ScenarioTemplate:
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario_id)
        .options(selectinload(ScenarioTemplate.characters))
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    for field in (
        "slug",
        "title",
        "description",
        "business_goal",
        "phases",
        "win_conditions",
        "scene_config",
        "orchestration_config",
        "is_published",
    ):
        setattr(scenario, field, getattr(body, field))

    existing_ids = {c.character_id: c for c in scenario.characters}
    incoming_ids = {c.character_id for c in body.characters}

    for c in list(scenario.characters):
        if c.character_id not in incoming_ids:
            await db.delete(c)

    for idx, c in enumerate(body.characters):
        if c.character_id in existing_ids:
            char = existing_ids[c.character_id]
            for k, v in c.model_dump().items():
                setattr(char, k, v)
            char.sort_order = c.sort_order or idx
        else:
            db.add(CharacterTemplate(scenario_id=scenario.id, sort_order=c.sort_order or idx, **c.model_dump()))

    await db.flush()
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario.id)
        .options(selectinload(ScenarioTemplate.characters))
    )
    return result.scalar_one()


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: int, db: DbDep, _: AdminDep) -> dict[str, str]:
    result = await db.execute(select(ScenarioTemplate).where(ScenarioTemplate.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    await db.delete(scenario)
    return {"status": "deleted"}


@router.get("/dispatch-rules", response_model=list[DispatchRuleOut])
async def list_dispatch_rules(db: DbDep, _: AdminDep, scenario_id: int | None = None) -> list[DispatchRule]:
    q = select(DispatchRule).order_by(DispatchRule.id.desc())
    if scenario_id is not None:
        q = q.where((DispatchRule.scenario_id == scenario_id) | (DispatchRule.scenario_id.is_(None)))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/dispatch-rules", response_model=DispatchRuleOut)
async def create_dispatch_rule(body: DispatchRuleIn, db: DbDep, _: AdminDep) -> DispatchRule:
    rule = DispatchRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.put("/dispatch-rules/{rule_id}", response_model=DispatchRuleOut)
async def update_dispatch_rule(rule_id: int, body: DispatchRuleIn, db: DbDep, _: AdminDep) -> DispatchRule:
    result = await db.execute(select(DispatchRule).where(DispatchRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump().items():
        setattr(rule, k, v)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/dispatch-rules/{rule_id}")
async def delete_dispatch_rule(rule_id: int, db: DbDep, _: AdminDep) -> dict[str, str]:
    result = await db.execute(select(DispatchRule).where(DispatchRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    await db.delete(rule)
    return {"status": "deleted"}


@router.get("/scenarios/{scenario_id}/orchestration")
async def get_scenario_orchestration(scenario_id: int, db: DbDep, _: AdminDep) -> dict:
    result = await db.execute(select(ScenarioTemplate).where(ScenarioTemplate.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    cfg = merge_orchestration_config(scenario.orchestration_config)
    return {
        "scenario_id": scenario.id,
        "orchestration_config": cfg,
        "orchestration_mode": ORCHESTRATION_MODE,
    }


@router.put("/scenarios/{scenario_id}/orchestration")
async def update_scenario_orchestration(
    scenario_id: int, body: OrchestrationConfigIn, db: DbDep, _: AdminDep
) -> dict:
    result = await db.execute(select(ScenarioTemplate).where(ScenarioTemplate.id == scenario_id))
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    scenario.orchestration_config = merge_orchestration_config(body.orchestration_config)
    await db.flush()
    cfg = scenario.orchestration_config
    return {
        "scenario_id": scenario.id,
        "orchestration_config": cfg,
        "orchestration_mode": ORCHESTRATION_MODE,
    }


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    db: DbDep,
    _: AdminDep,
    scenario_id: int | None = None,
    limit: int = 40,
) -> list[GameSession]:
    q = select(GameSession).order_by(GameSession.id.desc()).limit(min(limit, 100))
    if scenario_id is not None:
        q = q.where(GameSession.scenario_id == scenario_id)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/sessions/{session_uuid}/debug", response_model=SessionDebugOut)
async def get_session_debug(session_uuid: str, db: DbDep, _: AdminDep) -> SessionDebugOut:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")

    scenario_result = await db.execute(
        select(ScenarioTemplate).where(ScenarioTemplate.id == session.scenario_id)
    )
    scenario = scenario_result.scalar_one_or_none()
    orch_cfg = merge_orchestration_config(scenario.orchestration_config if scenario else None)

    msg_result = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.created_at)
    )
    messages = list(msg_result.scalars().all())

    shared = session.shared_state or {}
    last_debug = shared.get("_last_debug", {}) if isinstance(shared, dict) else {}

    agent_memories = await load_agent_memories_grouped(
        db, session.id, shared.get("world_timeline", []) if isinstance(shared, dict) else []
    )
    character_names = await load_character_names(db, session.scenario_id)

    return SessionDebugOut(
        session_uuid=session.session_uuid,
        scenario_id=session.scenario_id,
        orchestration_mode=session.orchestration_mode,
        current_phase=session.current_phase,
        shared_state=shared,
        orchestration_config=orch_cfg,
        last_debug=last_debug if isinstance(last_debug, dict) else {},
        messages=messages,
        agent_memories=agent_memories,
        character_names=character_names,
    )


RESTART_NOTE = (
    "端口已写入 config/platform.json 与 .env。"
    "API / 管理后台 / 学员端 / Docker 需重启后完全生效。"
    "若改了 PostgreSQL/Redis 端口，还需执行: docker compose down && docker compose up -d"
)


@router.get("/platform-config", response_model=PlatformConfigOut)
async def get_platform_config(request: Request, _: AdminDep) -> PlatformConfigOut:
    cfg = load_platform_config()
    host = resolve_client_host(request, cfg)
    return PlatformConfigOut(
        ports=cfg.ports.model_dump(),
        hosts=cfg.hosts.model_dump(),
        database=cfg.database.model_dump(),
        urls=urls_for_host(cfg, host),
        detected_public_host=resolve_public_host(cfg),
        config_path=str(CONFIG_PATH),
        restart_note=RESTART_NOTE,
    )


@router.put("/platform-config", response_model=PlatformConfigOut)
async def update_platform_config(body: PlatformConfigIn, request: Request, _: AdminDep) -> PlatformConfigOut:
    cfg = PlatformConfig.model_validate(body.model_dump())
    save_platform_config(cfg)
    reload_settings()
    host = resolve_client_host(request, cfg)
    return PlatformConfigOut(
        ports=cfg.ports.model_dump(),
        hosts=cfg.hosts.model_dump(),
        database=cfg.database.model_dump(),
        urls=urls_for_host(cfg, host),
        detected_public_host=resolve_public_host(cfg),
        config_path=str(CONFIG_PATH),
        restart_note=RESTART_NOTE,
    )
