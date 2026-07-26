"""PostgreSQL smoke test for dual session modes and transcript exports."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory, init_db
from app.memory.service import memory_service
from app.models.db import GameSession, ScenarioTemplate, SessionMessage
from app.session_export import (
    build_public_session_export_bundle,
    build_session_export_bundle,
    transcript_csv,
    transcript_jsonl,
)


async def main() -> None:
    await init_db()
    async with async_session_factory() as db:
        scenario = ScenarioTemplate(
            slug="ci-dual-mode-smoke",
            title="CI dual-mode smoke",
            description="Integration fixture",
            business_goal="Reach a balanced agreement",
            player_side_goal="Reach a balanced agreement",
            opponent_side_goal="Protect supplier value",
            task_config={
                "task_type": "smoke_test",
                "terminology": {"task": "test"},
                "state_schema": {},
                "phases": [{"phase_id": "active", "description": "Test"}],
                "completion_conditions": {"all": []},
            },
            phases=["opening", "closing"],
            win_conditions=[],
            scene_config={
                "player_character": {
                    "character_name": "Alex Chen",
                    "job_title": "Procurement Director",
                }
            },
            orchestration_config={},
            is_published=True,
        )
        db.add(scenario)
        await db.flush()

        participation = await memory_service.create_session(
            db, scenario.id, session_mode="participation"
        )
        test_session = await memory_service.create_session(
            db,
            scenario.id,
            session_mode="test",
            run_config={"safety_max_turns": 50, "player_strategy": "balanced"},
        )
        await db.flush()

        db.add_all([
            SessionMessage(
                session_id=participation.id,
                speaker_id="user",
                speaker_type="user",
                speaker_source="human",
                turn_id=1,
                sequence_no=1,
                content="Human player move",
            ),
            SessionMessage(
                session_id=test_session.id,
                speaker_id="user",
                speaker_type="user",
                speaker_source="ai",
                turn_id=1,
                sequence_no=1,
                content="AI player move",
            ),
            SessionMessage(
                session_id=test_session.id,
                speaker_id="supplier",
                speaker_type="npc",
                speaker_source="ai",
                turn_id=1,
                sequence_no=2,
                content="AI opponent reply",
            ),
        ])
        await db.flush()

        bundle = await build_session_export_bundle(db, test_session)
        assert bundle["session"]["session_mode"] == "test"
        assert [row["sequence_no"] for row in bundle["messages"]] == [1, 2]
        assert bundle["messages"][0]["speaker_source"] == "ai"
        assert bundle["dialogue_turns"][0]["turn_id"] == 1
        assert "AI player move" in transcript_csv(bundle)
        assert '"speaker_source": "ai"' in transcript_jsonl(bundle)

        public_bundle = build_public_session_export_bundle(bundle)
        assert public_bundle["export_meta"]["format"] == "roommind-public-session-transcript"
        assert "agent_memories" not in public_bundle
        assert "last_debug" not in public_bundle
        assert "shared_state" not in public_bundle
        assert "orchestration_config" not in public_bundle
        assert "meta" not in public_bundle["messages"][0]
        assert public_bundle["messages"][0]["speaker_source"] == "ai"

        modes = set((await db.execute(select(GameSession.session_mode))).scalars().all())
        assert modes == {"participation", "test"}
        await db.rollback()

    print("dual-mode PostgreSQL smoke test: ok")


if __name__ == "__main__":
    asyncio.run(main())
