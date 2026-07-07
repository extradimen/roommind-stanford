from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LLMConfig(Base):
    """Global LLM provider/model configuration (admin-editable)."""

    __tablename__ = "llm_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, default="default")
    provider: Mapped[str] = mapped_column(String(32))  # ollama_cloud | siliconflow
    model: Mapped[str] = mapped_column(String(128))
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_env: Mapped[str | None] = mapped_column(String(64), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScenarioTemplate(Base):
    """Reusable scenario blueprint."""

    __tablename__ = "scenario_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_goal: Mapped[str] = mapped_column(Text)
    phases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    win_conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    scene_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    director_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    router_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    orchestration_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    characters: Mapped[list["CharacterTemplate"]] = relationship(back_populates="scenario", cascade="all, delete-orphan")


class CharacterTemplate(Base):
    """NPC character definition bound to a scenario."""

    __tablename__ = "character_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario_templates.id", ondelete="CASCADE"))
    character_id: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(128))
    persona: Mapped[str] = mapped_column(Text)
    responsibility: Mapped[str] = mapped_column(Text)
    tendency: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    private_state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spawn_point: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    llm_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    scenario: Mapped["ScenarioTemplate"] = relationship(back_populates="characters")


class DispatchRule(Base):
    """Speaker routing / scheduling rules (admin-editable)."""

    __tablename__ = "dispatch_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("scenario_templates.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    priority_character_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    min_speakers: Mapped[int] = mapped_column(Integer, default=1)
    max_speakers: Mapped[int] = mapped_column(Integer, default=2)
    weights: Mapped[dict[str, float]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario_templates.id"))
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_phase: Mapped[str] = mapped_column(String(64), default="opening")
    orchestration_mode: Mapped[str] = mapped_column(String(32), default="generative")
    shared_state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["SessionMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    memories: Mapped[list["EpisodeMemory"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionMessage(Base):
    __tablename__ = "session_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id", ondelete="CASCADE"))
    speaker_id: Mapped[str] = mapped_column(String(64))
    speaker_type: Mapped[str] = mapped_column(String(16))  # user | npc | director | system
    content: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gesture: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["GameSession"] = relationship(back_populates="messages")


class EpisodeMemory(Base):
    __tablename__ = "episode_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)
    actors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    impact: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    visibility: Mapped[str] = mapped_column(String(16), default="shared")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["GameSession"] = relationship(back_populates="memories")


class AgentMemoryNode(Base):
    """Per-agent memory stream node (observation / reflection / plan)."""

    __tablename__ = "agent_memory_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[str] = mapped_column(String(64), index=True)
    node_type: Mapped[str] = mapped_column(String(32))  # observation | reflection | plan | action
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=5.0)
    turn_id: Mapped[int] = mapped_column(Integer, default=0)
    tick: Mapped[int] = mapped_column(Integer, default=0)
    source_event_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
