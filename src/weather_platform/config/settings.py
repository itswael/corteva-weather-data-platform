import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    """Base settings which read from environment where possible.

    Avoid hardcoded secrets -- prefer environment variables. Sensible
    defaults are provided for local development but are intended to be
    overridden in CI/production.
    """

    app_name: str = Field(default="weather-platform")
    app_env: str = Field(default="local")
    app_version: str = Field(default="0.1.0")
    log_level: str = Field(default="INFO")
    app_secret_key: SecretStr = Field(default=SecretStr("local-development-secret-key-change-me"))

    # SecretStr prevents accidental secret leakage in logs/repr output.
    database_url: SecretStr = Field(
        default=SecretStr("postgresql+psycopg2://weather:weather@localhost:5432/weather")
    )
    alchemy_echo: bool = Field(default=False)

    # Secure deployment defaults.
    enable_docs: bool = Field(default=True)
    enforce_https: bool = Field(default=False)
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        valid = {"local", "dev", "test", "prod", "production"}
        if normalized not in valid:
            raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(valid))}")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in valid:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(sorted(valid))}")
        return normalized

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            raw_parts = [part.strip() for part in value.split(",")]
            return [part for part in raw_parts if part]
        return value

    @property
    def database_dsn(self) -> str:
        """Return the usable database DSN from the secret value."""
        return self.database_url.get_secret_value()

    @model_validator(mode="after")
    def validate_security_defaults(self) -> "CommonSettings":
        is_prod = self.app_env in {"prod", "production"}
        if not is_prod:
            return self

        if not self.database_dsn:
            raise ValueError("DATABASE_URL is required in production")
        if self.alchemy_echo:
            raise ValueError("ALCHEMY_ECHO must be false in production")
        if self.log_level == "DEBUG":
            raise ValueError("LOG_LEVEL=DEBUG is not allowed in production")

        secret = self.app_secret_key.get_secret_value()
        if len(secret) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters in production")

        # Wildcard hosts allow host-header attacks in internet deployments.
        if "*" in self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS cannot contain '*' in production")
        return self


class LocalSettings(CommonSettings):
    """Local/dev settings (inherits defaults)."""

    enable_docs: bool = True
    enforce_https: bool = False


class TestSettings(CommonSettings):
    """Test settings: prefer an in-memory SQLite DB when not provided."""

    database_url: SecretStr = Field(default=SecretStr("sqlite+pysqlite:///:memory:"))
    enable_docs: bool = True
    enforce_https: bool = False
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])


class ProdSettings(CommonSettings):
    """Production settings: expect `DATABASE_URL` to be provided via env."""

    database_url: SecretStr = Field(default=SecretStr(""))
    enable_docs: bool = False
    enforce_https: bool = True
    allowed_hosts: list[str] = Field(default_factory=list)


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
