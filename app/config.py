from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings loaded from environment variables or .env file."""

    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite:///./devguard.db"

    # GitHub Webhook & API
    GITHUB_WEBHOOK_SECRET: str = "devguard_local_secret_key_123"
    GITHUB_TOKEN: str = ""

    # LLM Settings
    LLM_PROVIDER: Literal["gemini", "openai", "ollama", "mock"] = "gemini"
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings getter."""
    return Settings()
