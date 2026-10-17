"""Application settings, loaded from environment variables or a .env file."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-in-production-0000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GoalWise API"
    app_version: str = "0.9.0"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://goalwise:goalwise@127.0.0.1:5432/goalwise"

    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # JSON Web Token settings (authentication).
    jwt_secret_key: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Market data pipeline (Phase 4).
    scheduler_enabled: bool = False  # run the daily jobs inside the API process
    data_cache_dir: str = "data/cache"  # downloaded NAV histories (relative to backend/)
    risk_free_rate: float = 0.06  # a year, as a fraction: Sharpe and Sortino ratios

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
