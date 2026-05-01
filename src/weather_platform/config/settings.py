"""Application configuration management using Pydantic BaseSettings.

This module implements a factory pattern for environment-specific configuration.
Supports local, test, and production settings with sensible defaults for each.

Configuration Priority:
1. Environment variables (e.g., DATABASE_URL, APP_ENV)
2. .env file (if present in working directory)
3. Hardcoded defaults (suitable for local development)

Production deployments MUST provide:
- DATABASE_URL: PostgreSQL connection string
- APP_ENV: set to "prod" or "production"
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Base settings with defaults suitable for local development.
    
    Read configuration from environment variables with fallback defaults.
    Avoid hardcoded secrets -- all sensitive values should be provided
    via environment variables in production.
    
    Attributes:
        app_name: Application name (default: weather-platform)
        app_env: Environment identifier: local, test, prod (default: local)
        app_version: Semantic version (default: 0.1.0)
        log_level: Logging level (INFO, DEBUG, etc., default: INFO)
        database_url: PostgreSQL/SQLite connection string
        alchemy_echo: Enable SQLAlchemy SQL logging (default: False)
    """

    app_name: str = Field(default_factory=lambda: os.getenv("APP_NAME", "weather-platform"))
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    app_version: str = Field(default_factory=lambda: os.getenv("APP_VERSION", "0.1.0"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Database connection should be supplied via `DATABASE_URL` in production.
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://weather:weather@localhost:5432/weather",
        )
    )

    # Enable SQLAlchemy to log all SQL statements (useful for debugging, disable in prod)
    alchemy_echo: bool = Field(default_factory=lambda: os.getenv("ALCHEMY_ECHO", "false").lower() in ("1", "true", "yes"))

    # Configure Pydantic to read from .env file if present
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class LocalSettings(CommonSettings):
    """Local/dev settings (inherits all defaults from CommonSettings).
    
    Intended for developer machines. Uses sensible defaults that enable
    rapid iteration without requiring environment variable setup.
    """


class TestSettings(CommonSettings):
    """Test settings: prefer SQLite in-memory database.
    
    Overrides database_url to use SQLite in-memory unless DATABASE_URL
    environment variable is explicitly provided. Enables fast test execution
    without external database dependency.
    """

    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"))


class ProdSettings(CommonSettings):
    """Production settings: expect DATABASE_URL environment variable.
    
    Requires explicit DATABASE_URL configuration for security. Fails fast
    if database connection details are not provided, preventing accidental
    use of default local database credentials in production.
    """

    # Database URL must be provided via environment variable in production
    # Empty default will cause connection errors if not set, which is intentional
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))


# Mapping of environment names to configuration classes
_ENV_TO_CLASS = {
    "local": LocalSettings,
    "dev": LocalSettings,
    "test": TestSettings,
    "production": ProdSettings,
    "prod": ProdSettings,
}


@lru_cache(maxsize=1)
def get_settings(env: Optional[str] = None) -> CommonSettings:
    """Factory function to load environment-appropriate settings.
    
    Returns a singleton configuration object based on the environment.
    Uses @lru_cache to ensure a single settings instance across the app.
    
    Configuration sources (in priority order):
    1. Explicit env parameter
    2. APP_ENV environment variable
    3. Default to "local"
    
    Args:
        env: Environment name (local, dev, test, prod, production).
             If None, reads from APP_ENV environment variable.
    
    Returns:
        CommonSettings: Appropriate settings subclass for the environment
        
    Example:
        # In FastAPI app factory
        settings = get_settings()  # Uses APP_ENV or defaults to local
        
        # In tests
        settings = get_settings(env="test")  # Forces test configuration
        
        # In CLI with explicit env
        settings = get_settings(env="prod")  # Forces production settings
    """
    # Determine which environment to use
    if env is None:
        env = os.getenv("APP_ENV", "local")

    # Look up the appropriate settings class, defaulting to LocalSettings
    key = env.lower()
    cls = _ENV_TO_CLASS.get(key, LocalSettings)
    
    # Return configured settings instance (cached)
    return cls()
