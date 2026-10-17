"""Settings that matter when the API is deployed (Phase 13)."""

import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import DEV_JWT_SECRET, Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@ep-x.neon.tech/neondb?sslmode=require",
        "postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require",
        "postgresql+psycopg://u:p@ep-x.neon.tech/neondb?sslmode=require",
    ],
)
def test_hosted_database_urls_use_psycopg(given):
    settings = Settings(_env_file=None, database_url=given)
    assert settings.database_url == "postgresql+psycopg://u:p@ep-x.neon.tech/neondb?sslmode=require"


def test_production_refuses_the_development_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None, environment="production", jwt_secret_key=DEV_JWT_SECRET)
    assert Settings(_env_file=None, environment="production", jwt_secret_key="x" * 48)


def test_cors_origins_are_split_and_trimmed():
    settings = Settings(
        _env_file=None, cors_origins=" https://goalwise.vercel.app , ,http://localhost:5173"
    )
    assert settings.cors_origin_list == ["https://goalwise.vercel.app", "http://localhost:5173"]


def test_cors_regex_admits_preview_deployments_only():
    settings = Settings(
        _env_file=None,
        cors_origins="https://goalwise.vercel.app",
        cors_origin_regex=r"https://goalwise-[a-z0-9-]+\.vercel\.app",
    )
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_methods=["*"],
    )
    app.get("/ping")(lambda: {"ok": True})
    client = TestClient(app)

    def allowed(origin: str) -> str | None:
        response = client.get("/ping", headers={"Origin": origin})
        return response.headers.get("access-control-allow-origin")

    assert allowed("https://goalwise.vercel.app") == "https://goalwise.vercel.app"
    assert (
        allowed("https://goalwise-git-main-abc123.vercel.app")
        == "https://goalwise-git-main-abc123.vercel.app"
    )
    assert allowed("https://evil.example.com") is None
    assert allowed("https://goalwise-x.vercel.app.evil.com") is None


def test_simulations_wait_for_a_free_slot(monkeypatch):
    from app.simulation import limits

    monkeypatch.setattr(limits, "_slots", lambda: semaphore)
    semaphore = threading.BoundedSemaphore(1)
    running, overlaps = [], []

    def simulate():
        with limits.simulation_slot():
            running.append(1)
            overlaps.append(len(running))
            time.sleep(0.05)
            running.pop()

    threads = [threading.Thread(target=simulate) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert overlaps == [1, 1, 1]  # never two at once


def test_simulation_slots_follow_the_setting(monkeypatch):
    from app.simulation import limits

    limits._slots.cache_clear()
    monkeypatch.setattr(
        limits, "get_settings", lambda: Settings(_env_file=None, simulation_concurrency=2)
    )
    try:
        slots = limits._slots()
        assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
        assert not slots.acquire(blocking=False)
    finally:
        limits._slots.cache_clear()
