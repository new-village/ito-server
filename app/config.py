"""Configuration settings for AMI Server.

Uses pydantic-settings for environment variable management.
- Dev: Loads from .env file
- Prod: Uses environment variables (from Google Secret Manager in Cloud Run)
"""

import logging
import sys
from functools import lru_cache

from pydantic import SecretStr, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Required environment variables with descriptions
REQUIRED_ENV_VARS = {
    "NEO4J_URL": "Neo4j database connection URL (e.g., neo4j+s://xxx.databases.neo4j.io)",
    "NEO4J_USERNAME": "Neo4j username",
    "NEO4J_PASSWORD": "Neo4j password",
    "DATABASE_PATH": "SQLite database file path (e.g., ./ami.db)",
    "SECRET_KEY": "Secret key for JWT token signing (min 32 characters)",
    "FIRST_ADMIN_USER": "Initial admin username",
    "FIRST_ADMIN_PASSWORD": "Initial admin password",
}


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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # Long-lived refresh token

    # First Admin User (Required - auto-created on startup if no users exist)
    FIRST_ADMIN_USER: str
    FIRST_ADMIN_PASSWORD: SecretStr

    # Application Settings
    APP_NAME: str = "AMI Server"
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

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key_length(cls, v: SecretStr) -> SecretStr:
        """Validate that SECRET_KEY is at least 32 characters."""
        if len(v.get_secret_value()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters for security")
        return v


def _log_configuration_error(errors: list[dict]) -> None:
    """Log a helpful error message for configuration errors."""
    logger.error("")
    logger.error("=" * 60)
    logger.error("❌ CONFIGURATION ERROR: Invalid or missing environment variables")
    logger.error("=" * 60)
    logger.error("")

    for error in errors:
        field = error["loc"][0] if error["loc"] else "unknown"
        error_type = error["type"]
        msg = error.get("msg", "")

        if error_type == "missing":
            desc = REQUIRED_ENV_VARS.get(field, "Required configuration value")
            logger.error(f"  • {field} (MISSING)")
            logger.error(f"    {desc}")
        else:
            logger.error(f"  • {field}: {msg}")

        logger.error("")

    logger.error("To fix this, either:")
    logger.error("  1. Create a .env file (copy from .env.example)")
    logger.error("  2. Set environment variables directly (e.g., Cloud Run secrets)")
    logger.error("")
    logger.error("See .env.example for a template.")
    logger.error("=" * 60)
    logger.error("")


def validate_settings() -> Settings:
    """Validate and load settings with helpful error messages.

    Returns:
        Settings instance if validation succeeds.

    Raises:
        SystemExit: If validation fails, exits with code 1.
    """
    try:
        return Settings()
    except ValidationError as e:
        _log_configuration_error(e.errors())
        sys.exit(1)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance with validation."""
    return validate_settings()
