"""Configuration settings for ITO Server.

Uses pydantic-settings for environment variable management.
- Dev: Loads from .env file
- Prod: Uses environment variables (from Google Secret Manager in Cloud Run)
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Neo4j Connection Settings
    NEO4J_URL: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str

    # SQLite Database Settings (Required)
    DATABASE_PATH: str

    # JWT Authentication Settings (Required)
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # First Admin User (Required - auto-created on startup if no users exist)
    FIRST_ADMIN_USER: str
    FIRST_ADMIN_PASSWORD: SecretStr

    # Application Settings
    APP_NAME: str = "ITO Server"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API Settings
    DEFAULT_HOPS: int = 1
    MAX_HOPS: int = 5
    DEFAULT_LIMIT: int = 100
    MAX_LIMIT: int = 1000

    # CORS Settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
