"""Shared test fixtures.

Database tests run against a separate `<db>_test` database, built from scratch with the real
Alembic migrations once per test session. Each test runs inside a transaction that is rolled
back afterwards, so tests never see each other's data.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _test_database_url() -> URL:
    url = make_url(get_settings().database_url)
    return url.set(database=f"{url.database}_test")


def _create_database_if_missing(url: URL) -> None:
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 3},
    )
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    url = _test_database_url()
    try:
        _create_database_if_missing(url)
    except OperationalError:
        pytest.skip("PostgreSQL is not running")

    config = Config(str(ALEMBIC_INI))
    # '%' must be escaped for Alembic's config parser.
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    # Downgrade then upgrade: proves every migration can be undone and re-applied.
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Generator[Session]:
    connection = db_engine.connect()
    transaction = connection.begin()
    # Commits inside the app become savepoints; the outer transaction is rolled back at the end.
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
