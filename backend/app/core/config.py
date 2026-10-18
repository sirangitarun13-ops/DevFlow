"""Environment-backed application settings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or an optional .env file."""

    app_name: str = "DevFlow API"
    app_environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://localhost/devflow"
    database_echo: bool = False
    jwt_secret_key: str = Field(default="", description="JWT signing secret; must be set to a long random value")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "3/minute"
    # Trusted proxy IPs for Uvicorn's forwarded_allow_ips configuration.
    # When running behind a reverse proxy (nginx, ALB, etc.), set this to the
    # proxy IP addresses or CIDR ranges. Uvicorn will only trust X-Forwarded-For
    # headers from these IPs. Default is None (trust only 127.0.0.1).
    # Example: "10.0.0.0/8, 172.16.0.0/12" or "192.168.1.10, 192.168.1.11"
    forwarded_allow_ips: str | None = None

    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        if not value:
            raise ValueError("JWT_SECRET_KEY must be configured (non-empty)")
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters for HS256")
        return value

    def is_sqlite(self) -> bool:
        """Return True if the configured database is SQLite."""
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return the cached process-wide settings object."""

    return Settings()


settings = get_settings()
