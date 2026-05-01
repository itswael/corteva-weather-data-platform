import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Base settings which read from environment where possible.

    Avoid hardcoded secrets -- prefer environment variables. Sensible
    defaults are provided for local development but are intended to be
    overridden in CI/production.
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

    alchemy_echo: bool = Field(default_factory=lambda: os.getenv("ALCHEMY_ECHO", "false").lower() in ("1", "true", "yes"))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class LocalSettings(CommonSettings):
    """Local/dev settings (inherits defaults)."""


class TestSettings(CommonSettings):
    """Test settings: prefer an in-memory SQLite DB when not provided."""

    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:"))


class ProdSettings(CommonSettings):
    """Production settings: expect `DATABASE_URL` to be provided via env."""

    # Keep the same field but prefer environment-provided value; if absent
    # it will fall back to the base default. Operators should set
    # `DATABASE_URL` in the environment for production.
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))


_ENV_TO_CLASS = {
    "local": LocalSettings,
    "dev": LocalSettings,
    "test": TestSettings,
    "production": ProdSettings,
    "prod": ProdSettings,
}


@lru_cache(maxsize=1)
def get_settings(env: Optional[str] = None) -> CommonSettings:
    """Factory loader that returns the environment-appropriate Settings.

    - If `env` is provided it will be used; otherwise `APP_ENV` is read.
    - The returned object is cached to provide a single shared config
      instance across the application (safe and recommended).
    """

    if env is None:
        env = os.getenv("APP_ENV", "local")

    key = env.lower()
    cls = _ENV_TO_CLASS.get(key, LocalSettings)
    return cls()
