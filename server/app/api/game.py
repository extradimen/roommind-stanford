import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.debug_payload import build_session_agent_memories_payload
from app.session_export import (
    build_public_session_export_bundle,
    build_session_export_bundle,
    transcript_csv,
    transcript_jsonl,
)
from app.database import async_session_factory, get_db
from app.memory.service import memory_service
from app.models.db import AgentMemoryNode, ScenarioTemplate, SessionMessage
from app.orchestrator.defaults import ORCHESTRATION_MODE, merge_orchestration_config
from app.orchestrator.common import orch_support
from app.avatar_manifest import client_avatar_manifest
from app.player_character import resolve_player_character
from app.player_agent import generate_player_move
from app.scenario_side import resolve_player_side_goal
from app.schemas import (
    AgentMemoryNodeOut,
    AgentMemoryNodeUpdate,
    ChatMessageOut,
    ScenarioListItem,
    SessionAgentMemoriesOut,
    SessionCreate,
    SessionOut,
    TestRunIn,
    UserMessageIn,
)

router = APIRouter(prefix="/api/game", tags=["game"])
DbDep = Annotated[AsyncSession, Depends(get_db)]
logger = logging.getLogger(__name__)


async def _run_test_step(db: AsyncSession, session_uuid: str, locale: str | None = None) -> dict:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.session_mode != "test":
        raise HTTPException(409, "This operation requires a test session")
    if session.status not in {"active", "paused"}:
        raise HTTPException(409, f"Session is {session.status}")

    scenario = await orch_support.load_scenario(db, session.scenario_id)
    result = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.sequence_no, SessionMessage.id)
    )
    rows = list(result.scalars().all())
    messages = [
        {"speaker_id": m.speaker_id, "speaker_type": m.speaker_type, "content": m.content}
        for m in rows
    ]
    move = await generate_player_move(db, session, scenario, messages)
    turn_result: dict = {}
    async for event in memory_service.process_player_message_stream(
        db,
        session_uuid,
        move.content,
        ui_locale=locale,
        speaker_source="ai",
        message_meta={
            "intent": move.intent,
            "generation_model": move.model_label,
            "requested_end": move.requested_end,
        },
    ):
        if event.get("type") == "turn_result":
            turn_result = {k: v for k, v in event.items() if k != "_result"}

    completed_turns = sum(1 for m in rows if m.speaker_type == "user") + 1
    max_turns = max(1, min(int((session.run_config or {}).get("max_turns", 20)), 100))
    stop_reason = None
    agreement_reached = bool((session.shared_state or {}).get("_agreement_reached"))
    if agreement_reached:
        stop_reason = "mutual_agreement"
    elif move.requested_end:
        stop_reason = "player_requested_end"
    elif completed_turns >= max_turns:
        stop_reason = "max_turns_reached"
    if stop_reason:
        session.status = "completed"
    shared = dict(session.shared_state or {})
    shared["_test_state"] = {
        "completed_turns": completed_turns,
        "max_turns": max_turns,
        "stop_reason": stop_reason,
        "last_player_intent": move.intent,
    }
    session.shared_state = shared
    await db.flush()
    return {
        "player_move": {
            "content": move.content,
            "intent": move.intent,
            "requested_end": move.requested_end,
            "model": move.model_label,
        },
        "turn_result": turn_result,
        "status": session.status,
        "test_state": shared["_test_state"],
    }


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
                "avatar_manifest": client_avatar_manifest(c.avatar_manifest),
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

    try:
        session = await memory_service.create_session(
            db,
            body.scenario_id,
            body.user_id,
            session_mode=body.session_mode,
            run_config=body.run_config,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.flush()
    return SessionOut(
        session_uuid=session.session_uuid,
        scenario_id=session.scenario_id,
        current_phase=session.current_phase,
        orchestration_mode=session.orchestration_mode,
        session_mode=session.session_mode,
        run_config=session.run_config or {},
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
        session_mode=session.session_mode,
        run_config=session.run_config or {},
        shared_state=session.shared_state or {},
        status=session.status,
    )


@router.get("/sessions/{session_uuid}/messages", response_model=list[ChatMessageOut])
async def get_messages(session_uuid: str, db: DbDep) -> list[ChatMessageOut]:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    result = await db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.sequence_no, SessionMessage.id)
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
    full = await build_session_export_bundle(db, session)
    return build_public_session_export_bundle(full)


@router.get("/sessions/{session_uuid}/export.csv", response_class=PlainTextResponse)
async def export_session_csv(session_uuid: str, db: DbDep) -> PlainTextResponse:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    bundle = build_public_session_export_bundle(await build_session_export_bundle(db, session))
    return PlainTextResponse(
        transcript_csv(bundle),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="session-{session_uuid}.csv"'},
    )


@router.get("/sessions/{session_uuid}/export.jsonl", response_class=PlainTextResponse)
async def export_session_jsonl(session_uuid: str, db: DbDep) -> PlainTextResponse:
    session = await memory_service.get_session(db, session_uuid)
    if not session:
        raise HTTPException(404, "Session not found")
    bundle = build_public_session_export_bundle(await build_session_export_bundle(db, session))
    return PlainTextResponse(
        transcript_jsonl(bundle),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="session-{session_uuid}.jsonl"'},
    )


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


@router.post("/sessions/{session_uuid}/test/step")
async def run_test_step(session_uuid: str, body: TestRunIn, db: DbDep) -> dict:
    """Generate exactly one AI-player move and the corresponding NPC turn."""
    try:
        return await _run_test_step(db, session_uuid, body.locale)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/sessions/{session_uuid}/test/run")
async def run_test_session(session_uuid: str, body: TestRunIn, db: DbDep) -> dict:
    """Run a bounded number of autonomous turns; callers may invoke again to resume."""
    steps: list[dict] = []
    for _ in range(body.max_steps):
        step = await _run_test_step(db, session_uuid, body.locale)
        steps.append(step)
        if step["status"] != "active":
            break
    return {"steps": steps, "step_count": len(steps), "status": steps[-1]["status"]}


@router.post("/sessions/{session_uuid}/test/pause")
async def pause_test_session(session_uuid: str, db: DbDep) -> dict:
    session = await memory_service.get_session(db, session_uuid)
    if not session or session.session_mode != "test":
        raise HTTPException(404, "Test session not found")
    session.status = "paused"
    await db.flush()
    return {"status": session.status}


@router.post("/sessions/{session_uuid}/test/resume")
async def resume_test_session(session_uuid: str, db: DbDep) -> dict:
    session = await memory_service.get_session(db, session_uuid)
    if not session or session.session_mode != "test":
        raise HTTPException(404, "Test session not found")
    if session.status == "completed":
        raise HTTPException(409, "Completed sessions cannot be resumed")
    session.status = "active"
    await db.flush()
    return {"status": session.status}


@router.post("/sessions/{session_uuid}/test/stop")
async def stop_test_session(session_uuid: str, db: DbDep) -> dict:
    session = await memory_service.get_session(db, session_uuid)
    if not session or session.session_mode != "test":
        raise HTTPException(404, "Test session not found")
    session.status = "stopped"
    shared = dict(session.shared_state or {})
    test_state = dict(shared.get("_test_state") or {})
    test_state["stop_reason"] = "manually_stopped"
    shared["_test_state"] = test_state
    session.shared_state = shared
    await db.flush()
    return {"status": session.status, "test_state": test_state}


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
