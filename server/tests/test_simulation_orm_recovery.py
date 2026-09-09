"""Opt-in real ORM/JSONB transaction and startup-resume test.

Own random schema only. Scheduling is intercepted: no LLM or production work.
This does not simulate an OS crash or execute the scheduled worker.
"""
import asyncio
import uuid
from unittest.mock import patch, AsyncMock

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.db import Base, ScenarioTemplate, GameSession, SessionMessage, BatchExperiment, BatchExperimentRun
from app.world.executor import SCHEMA, execute
from app.world.receipt_evidence import verified_receipts
from app.session_export import serialize_message
from app.batch_experiments import resume_batch_experiments, _execute_run
from app.models.db import CharacterTemplate, DispatchRule
from app.world.input_binding import capture_inputs, verify_inputs, verify_manifest_binding
from app.research_protocol import experiment_manifest, sha256_json


async def main():
    schema = "simulation_orm_test_" + uuid.uuid4().hex
    admin = create_async_engine("postgresql+asyncpg:///postgres")
    engine = create_async_engine("postgresql+asyncpg:///postgres",
        connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tables = [cls.__table__ for cls in (ScenarioTemplate, GameSession, SessionMessage,
                                      BatchExperiment, BatchExperimentRun, CharacterTemplate, DispatchRule)]
    cfg = {"simulation_executor": {"schema": SCHEMA, "actions": {
        "act": {"actors": ["a"], "field": "done", "value": True}}}}
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
        async with factory() as db:
            scenario = ScenarioTemplate(slug="fixture", title="fixture", business_goal="fixture", task_config=cfg)
            db.add(scenario)
            await db.flush()
            binding = {str(scenario.id): await capture_inputs(db, scenario.id)}
            await verify_inputs(db, binding, scenario.id)
            manifest = experiment_manifest(study_phase="exploration", random_seed=1,
                                           frozen_inputs_sha256=sha256_json(binding))
            verify_manifest_binding(manifest, binding)
            corrupt = {**manifest, "frozen_inputs_sha256": "wrong"}
            try:
                verify_manifest_binding(corrupt, binding)
            except ValueError:
                pass
            else:
                raise AssertionError("Manifest/input mismatch was not rejected")
            scenario.task_config = {}
            await db.flush()
            try:
                await verify_inputs(db, binding, scenario.id)
            except ValueError:
                pass
            else:
                raise AssertionError("World contract drift was not rejected")
            scenario.task_config = cfg
            await db.flush()
            await verify_inputs(db, binding, scenario.id)
            state = {}
            receipt = execute(cfg, state, actor_id="a", turn_id=1,
                              request={"request_id": "r", "operation": "act"})
            session = GameSession(session_uuid=str(uuid.uuid4()), scenario_id=scenario.id,
                                  shared_state={"task_state": state})
            db.add(session)
            await db.flush()
            db.add(SessionMessage(session_id=session.id, speaker_id="a", speaker_type="npc",
                                  turn_id=1, sequence_no=1, content=receipt["content"]))
            batches = [BatchExperiment(batch_uuid=str(uuid.uuid4()), status=status)
                       for status in ("running", "evaluation_running", "cancelled", "completed")]
            db.add_all(batches)
            await db.flush()
            for status in ("evaluation_running", "evaluation_completed"):
                db.add(BatchExperimentRun(batch_id=batches[1].id, scenario_id=scenario.id,
                    condition="test", repetition=1, status=status,
                    result={"sentinel": "must survive"}))
            await db.commit()
            session_id = session.id
        await engine.dispose()  # New DB connection/ORM session, not server restart.
        async with factory() as db:
            restored = await db.get(GameSession, session_id)
            messages = list((await db.scalars(select(SessionMessage))).all())
            assert len(verified_receipts(cfg, restored.shared_state,
                                        [serialize_message(m) for m in messages])) == 1
            restored.shared_state = {}
            db.add(SessionMessage(session_id=session_id, speaker_id="a", speaker_type="npc",
                                  content="uncommitted", sequence_no=2))
            await db.flush()
            await db.rollback()
        with patch("app.batch_experiments.async_session_factory", factory), \
             patch("app.batch_experiments._schedule") as dialogue, \
             patch("app.batch_experiments._schedule_evaluation") as evaluation:
            await resume_batch_experiments()
            dialogue.assert_called_once_with(batches[0].batch_uuid)
            evaluation.assert_called_once_with(batches[1].batch_uuid, 1)
        async with factory() as db:
            restored = await db.get(GameSession, session_id)
            assert restored.shared_state == {"task_state": state}
            assert len(list((await db.scalars(select(SessionMessage))).all())) == 1
            runs = list((await db.scalars(select(BatchExperimentRun).order_by(BatchExperimentRun.id))).all())
            assert [r.status for r in runs] == ["evaluation_queued", "evaluation_completed"]
            assert all(r.result == {"sentinel": "must survive"} for r in runs)
        async with factory() as db:
            session = await db.get(GameSession, session_id)
            run = BatchExperimentRun(batch_id=batches[0].id, scenario_id=scenario.id,
                condition="test", repetition=1, status="queued", session_uuid=session.session_uuid,
                result={"last_completed_turn_index": 1})
            db.add(run)
            await db.flush()
            session.session_mode = "test"
            session.run_config = {"batch_experiment_run_id": run.id}
            session.shared_state = {"task_state": state, "_test_state": {"completed_turns": 1},
                                    "_performance_trace": [{"turn_index": 1, "llm_events": []}]}
            await db.commit()
            rid = run.id
        calls = []
        async def step(db, session_uuid, locale):
            calls.append(session_uuid)
            if len(calls) > 1:
                raise asyncio.CancelledError()
            session = await db.get(GameSession, session_id)
            session.shared_state = {**session.shared_state, "_test_state": {"completed_turns": 2}}
            db.add(SessionMessage(session_id=session_id, speaker_id="a", speaker_type="npc",
                                  content="committed second turn", sequence_no=2, turn_id=2))
            return {"status": "active", "test_state": {"completed_turns": 2}}
        with patch("app.batch_experiments.async_session_factory", factory), \
             patch("app.batch_experiments.memory_service.create_session", AsyncMock()) as create, \
             patch("app.api.game._run_autonomous_step", step):
            await _execute_run(rid, 5, 8, None)
            await _execute_run(rid, 5, 8, None)
            create.assert_not_called()
        async with factory() as db:
            run = await db.get(BatchExperimentRun, rid)
            session = await db.get(GameSession, session_id)
            assert run.status == "queued"
            assert run.session_uuid == session.session_uuid
            assert run.result["last_completed_turn_index"] == 2
            assert [r["next_turn_index"] for r in run.result["dialogue_recovery_history"]] == [2, 3]
            assert session.shared_state["task_state"] == state
            assert len(list((await db.scalars(select(SessionMessage))).all())) == 2
        print("ORM persistence, startup scheduling and actual worker checkpoint continuation passed")
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
