from functools import lru_cache
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized Configuration Manager using Pydantic BaseSettings."""

    # Application
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "crewai-enterprise"
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "INFO"

    # LLM Settings
    DEFAULT_LLM_PROVIDER: Literal["openai", "gemini", "mock"] = "mock"
    DEFAULT_MODEL: str = "gpt-4o"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Vector Storage / Memory
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[str] = None

    # Observability
    ENABLE_TELEMETRY: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Returns singleton instance of application settings."""
    return Settings()
