from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


# --- LLM Config ---


class LLMConfigOut(BaseModel):
    id: int
    name: str
    provider: str
    model: str
    base_url: str | None
    temperature: float
    max_tokens: int
    is_active: bool

    model_config = {"from_attributes": True}


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_active: bool | None = None


class LLMProviderKeysOut(BaseModel):
    configured: bool
    masked: str = ""


class LLMKeysOut(BaseModel):
    siliconflow: LLMProviderKeysOut
    ollama: LLMProviderKeysOut
    storage: str = ".env"


class LLMKeysUpdate(BaseModel):
    """Pass null/omit to keep unchanged; pass empty string to clear."""
    siliconflow_api_key: str | None = None
    ollama_api_key: str | None = None


class LLMModelOption(BaseModel):
    id: str
    name: str
    kind: str | None = None  # "chat" | "reasoning"
    recommended: bool = False


class LLMProvidersOut(BaseModel):
    providers: dict[str, list[str]]
    catalogs: dict[str, list[LLMModelOption]] = Field(default_factory=dict)
    meta: dict[str, Any] | None = None


# --- Character ---


class CharacterTemplateIn(BaseModel):
    character_id: str
    side: str = "opponent"
    character_name: str = ""
    job_title: str = ""
    display_name: str | None = None
    persona: str
    responsibility: str
    tendency: dict[str, Any] = Field(default_factory=dict)
    private_state: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None
    voice_id: str | None = None
    spawn_point: str | None = None
    avatar_manifest: dict[str, Any] = Field(default_factory=dict)
    llm_config: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class CharacterTemplateOut(CharacterTemplateIn):
    id: int
    scenario_id: int
    display_name: str

    model_config = {"from_attributes": True}


class ScenarioDispatchRuleIn(BaseModel):
    name: str
    description: str | None = None
    trigger_keywords: list[str] = Field(default_factory=list)
    priority_character_ids: list[str] = Field(default_factory=list)
    min_speakers: int = 1
    max_speakers: int = 2
    weights: dict[str, float] = Field(default_factory=dict)
    is_active: bool = True


class DispatchRuleIn(ScenarioDispatchRuleIn):
    scenario_id: int | None = None


class DispatchRuleOut(DispatchRuleIn):
    id: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Scenario ---


class ScenarioTemplateIn(BaseModel):
    slug: str
    title: str
    description: str | None = None
    player_side_goal: str = ""
    opponent_side_goal: str = ""
    business_goal: str | None = None  # legacy input; maps to player_side_goal
    phases: list[str] = Field(default_factory=lambda: ["opening", "discovery", "bargaining", "closing"])
    win_conditions: list[dict[str, Any]] = Field(default_factory=list)
    scene_config: dict[str, Any] = Field(default_factory=dict)
    orchestration_config: dict[str, Any] | None = None
    is_published: bool = False
    characters: list[CharacterTemplateIn] = Field(default_factory=list)
    dispatch_rules: list[ScenarioDispatchRuleIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_goals(self) -> "ScenarioTemplateIn":
        if not self.player_side_goal and self.business_goal:
            self.player_side_goal = self.business_goal
        return self


class ScenarioTemplateOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None
    player_side_goal: str = ""
    opponent_side_goal: str = ""
    business_goal: str
    phases: list[str]
    win_conditions: list[dict[str, Any]]
    scene_config: dict[str, Any]
    orchestration_config: dict[str, Any] = Field(default_factory=dict)
    is_published: bool
    characters: list[CharacterTemplateOut] = Field(default_factory=list)
    dispatch_rules: list[DispatchRuleOut] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


    @model_validator(mode="before")
    @classmethod
    def fill_goal_fields(cls, data: Any) -> Any:
        if hasattr(data, "business_goal"):
            player = getattr(data, "player_side_goal", None) or data.business_goal or ""
            opponent = getattr(data, "opponent_side_goal", None) or ""
            return {
                "id": data.id,
                "slug": data.slug,
                "title": data.title,
                "description": data.description,
                "player_side_goal": player,
                "opponent_side_goal": opponent,
                "business_goal": data.business_goal or player,
                "phases": data.phases,
                "win_conditions": data.win_conditions,
                "scene_config": data.scene_config,
                "orchestration_config": data.orchestration_config or {},
                "is_published": data.is_published,
                "characters": data.characters,
                "dispatch_rules": [],
                "created_at": getattr(data, "created_at", None),
                "updated_at": getattr(data, "updated_at", None),
            }
        if isinstance(data, dict):
            if not data.get("player_side_goal") and data.get("business_goal"):
                data = {**data, "player_side_goal": data["business_goal"]}
            if not data.get("business_goal") and data.get("player_side_goal"):
                data = {**data, "business_goal": data["player_side_goal"]}
        return data


class ScenarioListItem(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None
    is_published: bool
    character_count: int = 0

    model_config = {"from_attributes": True}


# --- Game Session ---


class SessionCreate(BaseModel):
    scenario_id: int
    user_id: str | None = None


class SessionOut(BaseModel):
    session_uuid: str
    scenario_id: int
    current_phase: str
    orchestration_mode: str = "generative"
    shared_state: dict[str, Any]
    status: str

    model_config = {"from_attributes": True}


class UserMessageIn(BaseModel):
    content: str
    locale: str | None = None


class OrchestrationConfigIn(BaseModel):
    orchestration_config: dict[str, Any]


class ChatMessageOut(BaseModel):
    speaker_id: str
    speaker_type: str
    content: str
    emotion: str | None = None
    gesture: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SessionDebugOut(BaseModel):
    session_uuid: str
    scenario_id: int
    orchestration_mode: str
    current_phase: str
    shared_state: dict[str, Any]
    orchestration_config: dict[str, Any]
    last_debug: dict[str, Any] = Field(default_factory=dict)
    messages: list[ChatMessageOut]
    agent_memories: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    character_names: dict[str, str] = Field(default_factory=dict)


class AgentMemoryNodeOut(BaseModel):
    id: int | None = None
    node_type: str
    content: str
    importance: float
    turn_id: int
    tick: int
    is_active: bool
    source_event_ids: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None

    model_config = {"from_attributes": True}


class AgentMemoryNodeUpdate(BaseModel):
    content: str | None = None
    importance: float | None = None
    is_active: bool | None = None


class SessionAgentMemoriesOut(BaseModel):
    session_uuid: str
    orchestration_mode: str
    character_names: dict[str, str] = Field(default_factory=dict)
    agents: dict[str, list[AgentMemoryNodeOut]] = Field(default_factory=dict)
    world_timeline: list[dict[str, Any]] = Field(default_factory=list)
    last_agent_debug: dict[str, Any] = Field(default_factory=dict)
    last_turn_id: int | None = None


class SessionListItem(BaseModel):
    session_uuid: str
    scenario_id: int
    orchestration_mode: str
    current_phase: str
    status: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Platform Config ---


class PlatformPortsIn(BaseModel):
    api: int = Field(ge=1024, le=65535)
    admin: int = Field(ge=1024, le=65535)
    client: int = Field(ge=1024, le=65535)
    postgres: int = Field(ge=1024, le=65535)
    redis: int = Field(ge=1024, le=65535)


class PlatformHostsIn(BaseModel):
    api_bind: str = "0.0.0.0"
    public_host: str = "auto"


class PlatformDatabaseIn(BaseModel):
    user: str = "roommind"
    password: str = "roommind_dev"
    name: str = "roommind"


class PlatformConfigIn(BaseModel):
    ports: PlatformPortsIn
    hosts: PlatformHostsIn
    database: PlatformDatabaseIn = Field(default_factory=PlatformDatabaseIn)


class PlatformConfigOut(PlatformConfigIn):
    urls: dict[str, str]
    detected_public_host: str = ""
    config_path: str
    restart_note: str
