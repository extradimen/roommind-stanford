import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.debug_payload import build_session_agent_memories_payload
from app.session_export import build_session_export_bundle
from app.database import async_session_factory, get_db
from app.memory.service import memory_service
from app.models.db import AgentMemoryNode, ScenarioTemplate, SessionMessage
from app.orchestrator.defaults import ORCHESTRATION_MODE, merge_orchestration_config
from app.player_character import resolve_player_character
from app.scenario_side import resolve_player_side_goal
from app.schemas import (
    AgentMemoryNodeOut,
    AgentMemoryNodeUpdate,
    ChatMessageOut,
    ScenarioListItem,
    SessionAgentMemoriesOut,
    SessionCreate,
    SessionOut,
    UserMessageIn,
)

router = APIRouter(prefix="/api/game", tags=["game"])
DbDep = Annotated[AsyncSession, Depends(get_db)]
logger = logging.getLogger(__name__)


@router.get("/scenarios", response_model=list[ScenarioListItem])
async def list_published_scenarios(db: DbDep) -> list[ScenarioListItem]:
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.is_published.is_(True))
        .options(selectinload(ScenarioTemplate.characters))
        .order_by(ScenarioTemplate.id)
    )
    scenarios = list(result.scalars().all())
    items: list[ScenarioListItem] = []
    for s in scenarios:
        items.append(
            ScenarioListItem(
                id=s.id,
                slug=s.slug,
                title=s.title,
                description=s.description,
                is_published=s.is_published,
                character_count=len(s.characters),
            )
        )
    return items


@router.get("/scenarios/{scenario_id}")
async def get_published_scenario(scenario_id: int, db: DbDep) -> dict:
    result = await db.execute(
        select(ScenarioTemplate)
        .where(ScenarioTemplate.id == scenario_id, ScenarioTemplate.is_published.is_(True))
        .options(selectinload(ScenarioTemplate.characters))
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    cfg = merge_orchestration_config(scenario.orchestration_config)
    player = resolve_player_character(scenario)
    return {
        "id": scenario.id,
        "slug": scenario.slug,
        "title": scenario.title,
        "description": scenario.description,
        "player_side_goal": resolve_player_side_goal(scenario),
        "business_goal": resolve_player_side_goal(scenario),
        "phases": scenario.phases,
        "scene_config": scenario.scene_config,
        "player_character": player,
        "orchestration_mode": ORCHESTRATION_MODE,
        "agent_config": cfg.get("agent", {}),
        "characters": [
            {
                "character_id": c.character_id,
                "character_name": c.character_name,
                "job_title": c.job_title,
                "display_name": c.display_name,
                "side": c.side or "opponent",
                "spawn_point": c.spawn_point,
                "avatar_manifest": c.avatar_manifest,
            }
            for c in sorted(scenario.characters, key=lambda x: x.sort_order)
        ],
    }


@router.post("/sessions", response_model=SessionOut)
async def create_session(body: SessionCreate, db: DbDep) -> SessionOut:
    result = await db.execute(
        select(ScenarioTemplate).where(
            ScenarioTemplate.id == body.scenario_id,
            ScenarioTemplate.is_published.is_(True),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Scenario not found or not published")

    session = await memory_service.create_session(db, body.scenario_id, body.user_id)
    await db.flush()
    return SessionOut(
        session_uuid=session.session_uuid,
        scenario_id=session.scenario_id,
        current_phase=session.current_phase,
        orchestration_mode=session.orchestration_mode,
        shared_state=session.shared_state or {},
        status=session.status,
    )


@router.get("/sessions/{session_uuid}", response_model=SessionOut)
async def get_session(session_uuid: str, db: DbDep) -> SessionOut:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    return SessionOut(
        session_uuid=session.session_uuid,
        scenario_id=session.scenario_id,
        current_phase=session.current_phase,
        orchestration_mode=session.orchestration_mode,
        shared_state=session.shared_state or {},
        status=session.status,
    )


@router.get("/sessions/{session_uuid}/messages", response_model=list[ChatMessageOut])
async def get_messages(session_uuid: str, db: DbDep) -> list[ChatMessageOut]:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    result = await db.execute(
        select(SessionMessage).where(SessionMessage.session_id == session.id).order_by(SessionMessage.created_at)
    )
    return list(result.scalars().all())


@router.get("/sessions/{session_uuid}/agent-memories", response_model=SessionAgentMemoriesOut)
async def get_session_agent_memories(session_uuid: str, db: DbDep) -> SessionAgentMemoriesOut:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    payload = await build_session_agent_memories_payload(db, session)
    return SessionAgentMemoriesOut(**payload)


@router.get("/sessions/{session_uuid}/export")
async def export_session(session_uuid: str, db: DbDep) -> dict:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    return await build_session_export_bundle(db, session)


@router.patch("/sessions/{session_uuid}/agent-memories/{node_id}", response_model=AgentMemoryNodeOut)
async def update_agent_memory_node(
    session_uuid: str,
    node_id: int,
    body: AgentMemoryNodeUpdate,
    db: DbDep,
) -> AgentMemoryNodeOut:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")

    result = await db.execute(
        select(AgentMemoryNode).where(
            AgentMemoryNode.id == node_id,
            AgentMemoryNode.session_id == session.id,
        )
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Memory node not found")

    if body.content is not None:
        text = body.content.strip()
        if not text:
            raise HTTPException(400, "Content cannot be empty")
        node.content = text
    if body.importance is not None:
        node.importance = min(10.0, max(1.0, float(body.importance)))
    if body.is_active is not None and node.node_type == "plan":
        if body.is_active:
            others = await db.execute(
                select(AgentMemoryNode).where(
                    AgentMemoryNode.session_id == session.id,
                    AgentMemoryNode.character_id == node.character_id,
                    AgentMemoryNode.node_type == "plan",
                    AgentMemoryNode.is_active.is_(True),
                    AgentMemoryNode.id != node.id,
                )
            )
            for row in others.scalars().all():
                row.is_active = False
        node.is_active = body.is_active

    if node.meta is None:
        node.meta = {}
    node.meta["edited"] = True
    await db.flush()

    from app.agent.debug_payload import serialize_memory_node

    return AgentMemoryNodeOut(**serialize_memory_node(node))


@router.post("/sessions/{session_uuid}/message")
async def send_message(session_uuid: str, body: UserMessageIn, db: DbDep) -> dict:
    try:
        return await memory_service.process_user_message(
            db, session_uuid, body.content, ui_locale=body.locale
        )
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.websocket("/ws/{session_uuid}")
async def game_websocket(websocket: WebSocket, session_uuid: str) -> None:
    await websocket.accept()
    try:
        async with async_session_factory() as db:
            session = await memory_service.get_session(db, session_uuid)
            if not session:
                await websocket.send_json({"type": "error", "message": "Session not found"})
                await websocket.close()
                return

            await websocket.send_json(
                {
                    "type": "connected",
                    "session_uuid": session_uuid,
                    "phase": session.current_phase,
                    "orchestration_mode": session.orchestration_mode,
                    "shared_state": session.shared_state or {},
                }
            )

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "user_message":
                content = data.get("content", "").strip()
                ui_locale = data.get("locale")
                if not content:
                    continue
                await websocket.send_json(
                    {
                        "type": "debug",
                        "stage": "received",
                        "message": f"Received user message, length {len(content)}",
                        "content_preview": content[:80],
                    }
                )
                async with async_session_factory() as db:
                    try:
                        event_count = 0
                        async for event in memory_service.process_user_message_stream(
                            db, session_uuid, content, ui_locale=ui_locale
                        ):
                            event_count += 1
                            out = {k: v for k, v in event.items() if k != "_result"}
                            if event.get("type") == "turn_result":
                                out["debug_replies_count"] = len(event.get("replies") or [])
                            await websocket.send_json(out)
                        await db.commit()
                        await websocket.send_json(
                            {
                                "type": "debug",
                                "stage": "committed",
                                "message": f"处理完成，共推送 {event_count} 个事件",
                            }
                        )
                        logger.info(
                            "WS turn done session=%s events=%d",
                            session_uuid,
                            event_count,
                        )
                    except RuntimeError as e:
                        await db.rollback()
                        logger.exception("WS RuntimeError session=%s", session_uuid)
                        await websocket.send_json({"type": "error", "message": str(e)})
                    except Exception as e:
                        await db.rollback()
                        logger.exception("WS processing failed session=%s", session_uuid)
                        await websocket.send_json({"type": "error", "message": f"Processing failed: {e}"})
    except WebSocketDisconnect:
        pass
