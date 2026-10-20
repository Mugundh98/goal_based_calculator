"""Deployment helpers: the reference-data copy and the demo account (Phase 13)."""

from collections.abc import Generator
from datetime import date

import psycopg
import pytest
from alembic.config import Config
from sqlalchemy import func, select

from alembic import command
from app.deploy import copy_data, demo
from app.models import Goal, Holding, KbChunk, KbDocument, RetirementPlan, Transaction, User
from tests.conftest import ALEMBIC_INI, _create_database_if_missing, _test_database_url
from tests.test_portfolio_api import make_fund

# --- Copying reference data ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def target_url(db_engine) -> str:
    """A second, empty database at the same migration: stands in for the hosted one."""
    url = _test_database_url()
    url = url.set(database=f"{url.database}_copy")
    _create_database_if_missing(url)
    rendered = url.render_as_string(hide_password=False)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))
    command.upgrade(config, "head")
    return rendered


@pytest.fixture
def target(target_url) -> Generator[psycopg.Connection]:
    conn = copy_data.connect(target_url)
    yield conn
    conn.rollback()  # every test leaves the target empty again
    conn.close()


@pytest.fixture
def source(db) -> psycopg.Connection:
    """The test session's own connection: COPY sees its uncommitted rows."""
    fund = make_fund(db, 970_001, "Equity Scheme - Large Cap Fund", "equity", 10, 0.12)
    document = KbDocument(slug="sip", title="SIP", source="test", content_hash="x" * 64,
                          embedding_model="test")  # fmt: skip
    document.chunks = [
        KbChunk(chunk_index=i, heading="h", content="c", embedding=unit(i)) for i in range(2)
    ]
    db.add(document)
    db.flush()
    db.info["fund_id"] = fund.id
    return db.connection().connection.driver_connection


def unit(axis: int) -> list[float]:
    return [1.0 if i == axis else 0.0 for i in range(768)]


def count(conn: psycopg.Connection, table: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_libpq_url_drops_the_sqlalchemy_driver():
    url = "postgresql+psycopg://u:p%40ss@host:5432/db?sslmode=require"
    assert copy_data.libpq_url(url) == "postgresql://u:p%40ss@host:5432/db?sslmode=require"


def test_copies_reference_tables_with_ids_and_vectors(source, target, db):
    lines = []
    copied = copy_data.copy_tables(source, target, progress=lines.append)

    nav_rows = count(source, "nav_history")
    assert copied["funds"] == 1 and copied["nav_history"] == nav_rows > 700
    assert copied["kb_chunks"] == 2 and copied["fund_predictions"] == 0
    assert list(copied) == list(copy_data.REFERENCE_TABLES)  # parents first
    assert lines[1] == f"nav_history: {nav_rows:,} rows"
    fund_id = db.info["fund_id"]
    assert target.execute("SELECT id FROM funds").fetchone()[0] == fund_id
    # The id sequence was moved past the copied rows: a new fund gets the next id.
    new_id = target.execute(
        "INSERT INTO funds (scheme_code, name, amc, scheme_type, category, asset_class, plan,"
        " option) VALUES (1, 'New', 'AMC', 'Open Ended', 'Equity', 'equity', 'direct', 'growth')"
        " RETURNING id"
    ).fetchone()[0]
    assert new_id == fund_id + 1
    # Vectors survive the text format: the search finds the chunk pointing the same way.
    nearest = target.execute(
        "SELECT chunk_index FROM kb_chunks ORDER BY embedding <=> %s::vector LIMIT 1",
        (str(unit(1)),),
    ).fetchone()[0]
    assert nearest == 1


def test_refuses_a_filled_target_unless_replacing(source, target):
    copy_data.copy_tables(source, target, tables=("funds", "nav_history"))
    with pytest.raises(copy_data.CopyError, match="already has data in: funds, nav_history"):
        copy_data.copy_tables(source, target, tables=("funds", "nav_history"))
    copied = copy_data.copy_tables(source, target, tables=("funds", "nav_history"), replace=True)
    assert copied["funds"] == 1


def test_refuses_mismatched_migrations_and_unknown_tables(source, target):
    with pytest.raises(copy_data.CopyError, match="Not reference tables: users"):
        copy_data.copy_tables(source, target, tables=("funds", "users"))
    target.execute("UPDATE alembic_version SET version_num = 'older'")
    with pytest.raises(copy_data.CopyError, match="Migration mismatch"):
        copy_data.copy_tables(source, target)
    target.execute("DROP TABLE alembic_version")
    with pytest.raises(copy_data.CopyError, match="alembic upgrade head"):
        copy_data.copy_tables(source, target)


def test_refuses_the_same_database_or_an_empty_source(source, target, target_url):
    # The mistake this guards against: DATABASE_URL still set to the target in the same terminal.
    with copy_data.connect(target_url) as same:
        with pytest.raises(copy_data.CopyError, match="same database"):
            copy_data.copy_tables(same, target)
    # An empty source (the target database itself has no reference rows) copies nothing.
    test_db = _test_database_url().render_as_string(hide_password=False)
    with copy_data.connect(target_url) as empty, copy_data.connect(test_db) as other:
        with pytest.raises(copy_data.CopyError, match="has no rows in funds"):
            copy_data.copy_tables(empty, other, tables=("funds",))
    assert copy_data.describe(target).endswith("/goalwise_test_copy")


# --- Demo account -------------------------------------------------------------------------------


@pytest.fixture
def demo_funds(db) -> dict[str, int]:
    made = {
        "large": make_fund(db, 971_001, "Equity Scheme - Large Cap Fund", "equity", 10, 0.12),
        "mid": make_fund(db, 971_002, "Equity Scheme - Mid Cap Fund", "equity", 20, 0.15),
        "bond": make_fund(db, 971_003, "Debt Scheme - Corporate Bond Fund", "debt", 15, 0.07),
        "liquid": make_fund(db, 971_004, "Debt Scheme - Liquid Fund", "debt", 1000, 0.065),
    }
    db.commit()
    return {key: fund.id for key, fund in made.items()}


def test_demo_account_has_a_complete_plan(db, demo_funds):
    result = demo.create_demo_user(db, "Demo@Example.com", funds=demo_funds)

    user = db.scalar(select(User).where(User.email == "demo@example.com"))
    assert user is not None and result.user.id == user.id
    assert set(result.goals) == {"education", "car", "house", "retirement"}
    assert db.scalar(select(func.count()).select_from(Goal).where(Goal.user_id == user.id)) == 4
    assert db.scalar(select(RetirementPlan).where(RetirementPlan.user_id == user.id))
    stored = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id)
    )
    assert stored == result.transactions > 50  # about three years of monthly SIPs
    held = db.scalars(select(Holding).where(Holding.user_id == user.id)).all()
    assert {h.fund_id for h in held} == set(demo_funds.values())
    # No two years of category history in the test database: no recommendations, and it says so.
    assert result.recommendations == 0 and "No recommendation" in result.notes[0]
    assert any(c.isalpha() for c in result.password) and any(c.isdigit() for c in result.password)


def test_demo_account_reset_and_rules(db, demo_funds):
    first = demo.create_demo_user(db, password="viva2026demo", funds=demo_funds)
    with pytest.raises(demo.DemoError, match="already exists"):
        demo.create_demo_user(db, funds=demo_funds)
    with pytest.raises(demo.DemoError, match="letter and one digit"):
        demo.create_demo_user(db, password="onlyletters", reset=True, funds=demo_funds)

    second = demo.create_demo_user(db, reset=True, funds=demo_funds, today=date.today())
    assert second.user.id != first.user.id
    assert db.get(User, first.user.id) is None  # the old account and its data are gone
    assert (
        db.scalar(select(func.count()).select_from(Goal).where(Goal.user_id == first.user.id)) == 0
    )


def test_demo_needs_market_data(db):
    with pytest.raises(demo.DemoError, match="load the market data first"):
        demo.create_demo_user(db, email="nofunds@example.com")
