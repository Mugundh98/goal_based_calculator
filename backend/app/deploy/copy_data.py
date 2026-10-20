"""Copy the reference data (funds, NAVs, indices, inflation, ML outputs, knowledge base) from one
database to another, e.g. from the local database to a fresh hosted one.

Rebuilding it on the server instead would mean a 35-minute download from AMFI/mfapi and NSE plus
model training, on a free plan that has neither the time nor the memory. User data (accounts,
goals, portfolios, chats, the audit log) is never copied.

Both databases must be at the same migration. Rows stream through PostgreSQL's COPY protocol, so
the 2.5 million NAV rows take minutes, not hours, and use little memory.
"""

from collections.abc import Callable, Sequence

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

# Parents before children (foreign keys).
REFERENCE_TABLES = (
    "funds",
    "nav_history",
    "fund_metrics",
    "index_history",
    "inflation_data",
    "ml_models",
    "fund_predictions",
    "fund_clusters",
    "kb_documents",
    "kb_chunks",
)


class CopyError(Exception):
    pass


def libpq_url(url: str) -> str:
    """postgresql+psycopg://... (SQLAlchemy) -> postgresql://... (psycopg/libpq)."""
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def connect(url: str, timeout: int = 30) -> psycopg.Connection:
    return psycopg.connect(libpq_url(url), connect_timeout=timeout)


def describe(conn: psycopg.Connection) -> str:
    """host:port/database, without the password: says which database a connection reaches."""
    info = conn.info
    return f"{info.host}:{info.port}/{info.dbname}"


def _revision(conn: psycopg.Connection) -> str | None:
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return None
    return row[0] if row else None


def _columns(conn: psycopg.Connection, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    return [r[0] for r in rows]


def _count(conn: psycopg.Connection, table: str) -> int:
    return conn.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
    ).fetchone()[0]


def _reset_sequences(conn: psycopg.Connection, table: str, columns: list[str]) -> None:
    """Rows arrive with their ids; move each id sequence past them so new rows do not clash."""
    for column in columns:
        seq = conn.execute("SELECT pg_get_serial_sequence(%s, %s)", (table, column)).fetchone()[0]
        if seq:
            conn.execute(
                sql.SQL("SELECT setval({}, coalesce(max({}), 0) + 1, false) FROM {}").format(
                    sql.Literal(seq), sql.Identifier(column), sql.Identifier(table)
                )
            )


def copy_tables(
    source: psycopg.Connection,
    target: psycopg.Connection,
    tables: Sequence[str] = REFERENCE_TABLES,
    replace: bool = False,
    progress: Callable[[str], None] = lambda _: None,
) -> dict[str, int]:
    """Copy `tables` from source to target inside the target's open transaction (the caller
    commits). Refuses a target that already has rows in them unless `replace` is set, which
    empties those tables first - and fails if user data (holdings, transactions) still refers to
    a fund, rather than deleting that data."""
    unknown = set(tables) - set(REFERENCE_TABLES)
    if unknown:
        raise CopyError(f"Not reference tables: {', '.join(sorted(unknown))}")
    ordered = [t for t in REFERENCE_TABLES if t in tables]
    if describe(source) == describe(target):
        raise CopyError(
            f"Source and target are the same database ({describe(source)}). The source comes "
            "from DATABASE_URL (or --source): run the command where DATABASE_URL is your local "
            "database, e.g. a new terminal"
        )
    source_rev, target_rev = _revision(source), _revision(target)
    if target_rev is None:
        raise CopyError("The target has no tables yet: run `alembic upgrade head` against it first")
    if source_rev != target_rev:
        raise CopyError(f"Migration mismatch: source at {source_rev}, target at {target_rev}")

    if not any(_count(source, t) for t in ordered):
        raise CopyError(
            f"The source ({describe(source)}) has no rows in {', '.join(ordered)}: is it the "
            "database with your market data?"
        )

    filled = [t for t in ordered if _count(target, t)]
    if filled and not replace:
        raise CopyError(f"The target already has data in: {', '.join(filled)} (use --replace)")
    for table in reversed(filled):  # DELETE, not TRUNCATE: only rows in use block it
        target.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))

    copied: dict[str, int] = {}
    for table in ordered:
        columns = _columns(source, table)
        if columns != _columns(target, table):
            raise CopyError(f"Columns of {table} differ between the databases")
        cols = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        name = sql.Identifier(table)
        with (
            source.cursor().copy(sql.SQL("COPY {} ({}) TO STDOUT").format(name, cols)) as out,
            target.cursor().copy(sql.SQL("COPY {} ({}) FROM STDIN").format(name, cols)) as into,
        ):
            for chunk in out:
                into.write(chunk)
        _reset_sequences(target, table, columns)
        copied[table] = _count(target, table)
        progress(f"{table}: {copied[table]:,} rows")
    return copied
