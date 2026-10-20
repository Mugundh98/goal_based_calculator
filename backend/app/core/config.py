"""Application settings, loaded from environment variables or a .env file."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-in-production-0000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GoalWise API"
    app_version: str = "1.0.1"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://goalwise:goalwise@127.0.0.1:5432/goalwise"
    database_connect_timeout: int = 3  # seconds; raise it for a database that sleeps when idle

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Optional regular expression for more origins, e.g. Vercel preview deployments.
    cors_origin_regex: str = ""

    # JSON Web Token settings (authentication).
    jwt_secret_key: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Market data pipeline (Phase 4).
    scheduler_enabled: bool = False  # run the daily jobs inside the API process
    data_cache_dir: str = "data/cache"  # downloaded NAV histories (relative to backend/)
    risk_free_rate: float = 0.06  # a year, as a fraction: Sharpe and Sortino ratios

    # Monte Carlo runs allowed at the same time (each can take ~180 MB); 1 on a 512 MB server.
    simulation_concurrency: int = Field(default=4, ge=1)

    # Conversational assistant (Phase 10). No key = the assistant is switched off.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_fallback_model: str = "gemini-2.5-flash"  # tried once when the first is rate-limited
    gemini_embedding_model: str = "gemini-embedding-001"
    chat_messages_per_hour: int = 30  # per user

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        """Hosting providers hand out postgres:// URLs; SQLAlchemy needs the driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.jwt_secret_key == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET_KEY must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
