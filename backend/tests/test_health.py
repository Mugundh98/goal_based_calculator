from fastapi.testclient import TestClient

from app.main import app
from app.schemas.health import DatabaseStatus
from app.services.health import check_database

client = TestClient(app)


def test_health_ok_when_database_ready():
    app.dependency_overrides[check_database] = lambda: DatabaseStatus(connected=True, pgvector=True)
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {"connected": True, "pgvector": True, "error": None}


def test_health_degraded_when_database_down():
    app.dependency_overrides[check_database] = lambda: DatabaseStatus(
        connected=False, pgvector=False, error="OperationalError"
    )
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_cors_allows_frontend_origin():
    response = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
