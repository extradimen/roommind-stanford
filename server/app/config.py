from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.platform_config import ENV_PATH, load_platform_config, resolve_public_host
from app.platform_llm import (
    resolve_active_model,
    resolve_ollama_api_key,
    resolve_ollama_base_url,
    resolve_ollama_model_id,
    resolve_siliconflow_api_key,
    resolve_siliconflow_base_url,
    resolve_siliconflow_model_id,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8800
    admin_port: int = 5180
    client_port: int = 5181
    postgres_port: int = 5434
    redis_port: int = 6380
    public_host: str = "localhost"

    database_url: str = "postgresql+asyncpg://roommind:roommind_dev@localhost:5434/roommind"
    redis_url: str = "redis://localhost:6380/0"

    # LLM API keys in .env; provider/model controlled via admin → platform.json
    llm_provider: str = Field(default="siliconflow", validation_alias="LLM_PROVIDER")
    ollama_api_key: str = Field(default="", validation_alias="OLLAMA_API_KEY")
    ollama_base_url: str = Field(default="https://ollama.com", validation_alias="OLLAMA_BASE_URL")
    ollama_model_id: str = Field(default="kimi-k2.5:cloud", validation_alias="OLLAMA_MODEL_ID")
    siliconflow_api_key: str = Field(default="", validation_alias="SILICONFLOW_API_KEY")
    siliconflow_base_url: str = Field(
        default="https://api.siliconflow.com/v1", validation_alias="SILICONFLOW_BASE_URL"
    )
    siliconflow_model_id: str = Field(
        default="moonshotai/Kimi-K2.5", validation_alias="SILICONFLOW_MODEL_ID"
    )

    # Legacy aliases (still read from .env if present)
    ollama_cloud_api_key: str = Field(default="", validation_alias="OLLAMA_CLOUD_API_KEY")
    ollama_cloud_base_url: str = Field(default="", validation_alias="OLLAMA_CLOUD_BASE_URL")
    default_llm_provider: str = Field(default="", validation_alias="DEFAULT_LLM_PROVIDER")
    default_llm_model: str = Field(default="", validation_alias="DEFAULT_LLM_MODEL")

    admin_secret: str = Field(
        default="roommind-stanford-admin-dev-secret", validation_alias="ADMIN_SECRET"
    )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    cfg = load_platform_config()
    provider, model = resolve_active_model()

    return s.model_copy(
        update={
            "api_host": cfg.hosts.api_bind,
            "api_port": cfg.ports.api,
            "admin_port": cfg.ports.admin,
            "client_port": cfg.ports.client,
            "postgres_port": cfg.ports.postgres,
            "redis_port": cfg.ports.redis,
            "public_host": resolve_public_host(cfg),
            "database_url": cfg.database_url(),
            "redis_url": cfg.redis_url(),
            "llm_provider": provider,
            "ollama_api_key": resolve_ollama_api_key(),
            "ollama_base_url": resolve_ollama_base_url(),
            "ollama_model_id": resolve_ollama_model_id(),
            "siliconflow_api_key": resolve_siliconflow_api_key(),
            "siliconflow_base_url": resolve_siliconflow_base_url(),
            "siliconflow_model_id": resolve_siliconflow_model_id(),
            "default_llm_provider": provider,
            "default_llm_model": model,
        }
    )


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
