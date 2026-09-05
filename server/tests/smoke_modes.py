"""PostgreSQL smoke test for dual session modes and transcript exports."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import async_session_factory, init_db
from app.memory.service import memory_service
from app.models.db import (
    BatchExperiment,
    BatchExperimentRun,
    GameSession,
    ScenarioTemplate,
    SessionMessage,
)
from app.session_export import (
    build_public_session_export_bundle,
    build_session_export_bundle,
    transcript_csv,
    transcript_jsonl,
)
from app.scenario_template_loader import list_scenario_template_files, load_scenario_template_file


async def main() -> None:
    bundled = [load_scenario_template_file(path) for path in list_scenario_template_files()]
    preferred_ids = {
        row["slug"]: (row.get("template_meta") or {}).get("preferred_id")
        for row in bundled
    }
    assert preferred_ids["supply-chain-negotiation"] == 1
    assert preferred_ids["market-launch-go-no-go"] == 2
    assert preferred_ids["candidate-panel-interview"] == 3
    assert preferred_ids["incident-response-command"] == 4
    launch = next(row for row in bundled if row["slug"] == "market-launch-go-no-go")
    assert launch["is_published"] is True
    assert len(launch["characters"]) == 3
    assert set(launch["task_config"]["state_schema"]) == {
        "market_readiness", "operational_readiness", "budget_approved", "launch_decision"
    }

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
        baseline_session = await memory_service.create_session(
            db,
            scenario.id,
            session_mode="baseline",
            run_config={"safety_max_turns": 50, "player_strategy": "balanced"},
        )
        batch = BatchExperiment(
            batch_uuid="00000000-0000-0000-0000-000000000001",
            name="CI batch smoke",
            config={"concurrency": 2, "random_seed": 42},
            total_runs=2,
        )
        db.add(batch)
        await db.flush()
        db.add_all([
            BatchExperimentRun(
                batch_id=batch.id, scenario_id=scenario.id, condition="test", repetition=1
            ),
            BatchExperimentRun(
                batch_id=batch.id, scenario_id=scenario.id, condition="baseline", repetition=1
            ),
        ])

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
            SessionMessage(
                session_id=baseline_session.id,
                speaker_id="user",
                speaker_type="user",
                speaker_source="ai",
                turn_id=1,
                sequence_no=1,
                content="Baseline AI player move",
            ),
            SessionMessage(
                session_id=baseline_session.id,
                speaker_id="supplier",
                speaker_type="npc",
                speaker_source="ai",
                turn_id=1,
                sequence_no=2,
                content="Baseline independent-agent opponent reply",
            ),
        ])
        await db.flush()

        bundle = await build_session_export_bundle(db, test_session)
        assert bundle["session"]["session_mode"] == "test"
        assert [row["sequence_no"] for row in bundle["messages"]] == [1, 2]
        assert bundle["messages"][0]["speaker_source"] == "ai"
        assert bundle["dialogue_turns"][0]["turn_id"] == 1
        assert bundle["performance_trace"] == []
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
        assert public_bundle["task_result"]["completion_status"] == "in_progress"
        assert public_bundle["performance_trace"] == []
        assert "shared_state" not in public_bundle

        baseline_bundle = await build_session_export_bundle(db, baseline_session)
        assert baseline_bundle["session"]["session_mode"] == "baseline"
        assert baseline_bundle["task_result"] == {}
        observation = baseline_bundle["external_observation"]
        assert observation["protocol"] == "public-transcript-observer-v1"
        assert observation["descriptive_metrics"]["player_turns"] == 1
        assert observation["descriptive_metrics"]["public_message_count"] == 2
        assert observation["descriptive_metrics"]["exact_repetition_count"] == 0
        baseline_public = build_public_session_export_bundle(baseline_bundle)
        assert baseline_public["external_observation"]["protocol"] == "public-transcript-observer-v1"
        assert "shared_state" not in baseline_public

        modes = set((await db.execute(select(GameSession.session_mode))).scalars().all())
        assert modes == {"participation", "test", "baseline"}
        batch_modes = set((await db.execute(select(BatchExperimentRun.condition))).scalars().all())
        assert batch_modes == {"test", "baseline"}
        await db.rollback()

    print("dual-mode PostgreSQL smoke test: ok")


if __name__ == "__main__":
    asyncio.run(main())
