"""Runs only when a real database is reachable (locally via Docker, or in CI)."""

import pytest

from app.services.health import check_database

status = check_database()


@pytest.mark.skipif(not status.connected, reason="PostgreSQL is not running")
def test_database_connected_with_pgvector():
    assert status.connected
    assert status.pgvector, "Run 'alembic upgrade head' to enable the vector extension"
