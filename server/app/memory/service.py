import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.db import GameSession, SessionMessage
from app.orchestrator.common import orch_support
from app.orchestrator.defaults import ORCHESTRATION_MODE
from app.orchestrator.generative import generative_orchestrator

settings = get_settings()


class MemoryService:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _session_key(self, session_uuid: str) -> str:
        return f"roommind:session:{session_uuid}:working"

    async def cache_working_memory(self, session_uuid: str, messages: list[dict[str, Any]]) -> None:
        r = await self.get_redis()
        await r.set(self._session_key(session_uuid), json.dumps(messages[-50:], ensure_ascii=False), ex=86400)

    async def get_working_memory(self, session_uuid: str) -> list[dict[str, Any]]:
        r = await self.get_redis()
        raw = await r.get(self._session_key(session_uuid))
        if raw:
            return json.loads(raw)
        return []

    async def create_session(
        self,
        db: AsyncSession,
        scenario_id: int,
        user_id: str | None = None,
    ) -> GameSession:
        session = GameSession(
            session_uuid=str(uuid.uuid4()),
            scenario_id=scenario_id,
            user_id=user_id,
            current_phase="opening",
            orchestration_mode=ORCHESTRATION_MODE,
            shared_state={},
            status="active",
        )
        db.add(session)
        await db.flush()
        return session

    async def get_session(self, db: AsyncSession, session_uuid: str) -> GameSession | None:
        result = await db.execute(
            select(GameSession)
            .where(GameSession.session_uuid == session_uuid)
            .options(selectinload(GameSession.messages))
        )
        return result.scalar_one_or_none()

    async def get_session_messages_dict(self, session: GameSession) -> list[dict[str, Any]]:
        return [
            {
                "speaker_id": m.speaker_id,
                "speaker_type": m.speaker_type,
                "content": m.content,
                "emotion": m.emotion,
                "gesture": m.gesture,
            }
            for m in sorted(session.messages, key=lambda x: x.created_at)
        ]

    async def process_user_message(
        self, db: AsyncSession, session_uuid: str, user_input: str, ui_locale: str | None = None
    ) -> dict[str, Any]:
        result_payload: dict[str, Any] | None = None
        async for event in self.process_user_message_stream(
            db, session_uuid, user_input, ui_locale=ui_locale
        ):
            if event.get("type") == "turn_result":
                result_payload = event
        if not result_payload:
            raise RuntimeError("Processing failed: no turn_result")
        return result_payload

    async def process_user_message_stream(
        self, db: AsyncSession, session_uuid: str, user_input: str, ui_locale: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        from app.i18n.reply_language import detect_reply_language

        session = await self.get_session(db, session_uuid)
        if not session:
            raise ValueError("Session not found")

        scenario = await orch_support.load_scenario(db, session.scenario_id)
        dispatch_rules = await orch_support.load_dispatch_rules(db, session.scenario_id)
        messages = await self.get_session_messages_dict(session)

        user_msg = SessionMessage(
            session_id=session.id,
            speaker_id="user",
            speaker_type="user",
            content=user_input,
        )
        db.add(user_msg)
        messages.append({"speaker_id": "user", "speaker_type": "user", "content": user_input})

        user_turn_count = sum(1 for m in messages if m.get("speaker_type") == "user")
        orch_cfg = scenario.orchestration_config or {}
        reply_language = detect_reply_language(user_input, ui_locale)
        shared_state = dict(session.shared_state or {})
        shared_state["_reply_language"] = reply_language

        result: Any = None
        async for event in generative_orchestrator.process_turn_stream(
            db,
            session_id=session.id,
            scenario=scenario,
            characters=scenario.characters,
            dispatch_rules=dispatch_rules,
            user_input=user_input,
            messages=messages,
            current_phase=session.current_phase,
            shared_state=shared_state,
            orchestration_config=orch_cfg,
            user_turn_count=user_turn_count,
            reply_language=reply_language,
        ):
            if event.get("type") == "turn_result":
                result = event.pop("_result", None)
                yield event
            else:
                yield event

        if result is None:
            raise RuntimeError("Stream ended without turn_result")

        session.current_phase = result.phase
        session.shared_state = result.shared_state
        session.orchestration_mode = ORCHESTRATION_MODE

        npc_records = []
        for reply in result.replies:
            msg = SessionMessage(
                session_id=session.id,
                speaker_id=reply.character_id,
                speaker_type="npc",
                content=reply.content,
                emotion=reply.emotion,
                gesture=reply.gesture,
                meta={"reasoning": reply.reasoning},
            )
            db.add(msg)
            npc_records.append(reply)

        await db.flush()
        await self.cache_working_memory(
            session_uuid,
            messages + [{"speaker_id": r.character_id, "content": r.content} for r in npc_records],
        )


memory_service = MemoryService()
