from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()
# Long-running batch jobs and idle browser sessions can leave PostgreSQL
# connections in the pool after the server/database has closed them.  Validate
# pooled connections before checkout and recycle them periodically so one stale
# socket does not turn an otherwise healthy read request into a 500.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    from sqlalchemy import text

    from app.models.db import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE scenario_templates "
                "ADD COLUMN IF NOT EXISTS orchestration_config JSONB DEFAULT '{}'::jsonb"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE character_templates "
                "ADD COLUMN IF NOT EXISTS llm_config JSONB DEFAULT '{}'::jsonb"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE game_sessions "
                "ADD COLUMN IF NOT EXISTS orchestration_mode VARCHAR(32) DEFAULT 'generative'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE game_sessions "
                "ADD COLUMN IF NOT EXISTS session_mode VARCHAR(32) NOT NULL DEFAULT 'participation'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE game_sessions "
                "ADD COLUMN IF NOT EXISTS run_config JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE session_messages "
                "ADD COLUMN IF NOT EXISTS speaker_source VARCHAR(16) NOT NULL DEFAULT 'human'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE session_messages "
                "ADD COLUMN IF NOT EXISTS turn_id INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE session_messages "
                "ADD COLUMN IF NOT EXISTS sequence_no INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text(
                "UPDATE session_messages SET speaker_source = "
                "CASE WHEN speaker_type = 'npc' THEN 'ai' "
                "WHEN speaker_type IN ('director', 'system') THEN 'system' ELSE 'human' END "
                "WHERE speaker_source IS NULL OR speaker_source = 'human'"
            )
        )
        await conn.execute(
            text("ALTER TABLE scenario_templates ADD COLUMN IF NOT EXISTS player_side_goal TEXT")
        )
        await conn.execute(
            text("ALTER TABLE scenario_templates ADD COLUMN IF NOT EXISTS opponent_side_goal TEXT")
        )
        await conn.execute(
            text("ALTER TABLE scenario_templates ADD COLUMN IF NOT EXISTS task_config JSONB NOT NULL DEFAULT '{}'::jsonb")
        )
        await conn.execute(
            text(
                "UPDATE scenario_templates SET player_side_goal = business_goal "
                "WHERE player_side_goal IS NULL OR player_side_goal = ''"
            )
        )
        await conn.execute(
            text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS side VARCHAR(32) DEFAULT 'opponent'")
        )
        await conn.execute(
            text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS character_name VARCHAR(128) DEFAULT ''")
        )
        await conn.execute(
            text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS job_title VARCHAR(128) DEFAULT ''")
        )
        await conn.execute(text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS team_id VARCHAR(64) DEFAULT 'independent'"))
        await conn.execute(text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS relationship_to_player VARCHAR(32) DEFAULT 'counterpart'"))
        await conn.execute(text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS interaction_role VARCHAR(64) DEFAULT 'participant'"))
        await conn.execute(text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS authority JSONB NOT NULL DEFAULT '{}'::jsonb"))
        await conn.execute(text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS aliases JSONB NOT NULL DEFAULT '[]'::jsonb"))
        await conn.execute(text("ALTER TABLE character_templates ADD COLUMN IF NOT EXISTS fallback_actions JSONB NOT NULL DEFAULT '{}'::jsonb"))
