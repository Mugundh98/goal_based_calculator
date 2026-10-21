"""Idempotent bulk upserts into the market data tables.

Every load is an UPSERT - INSERT ... ON CONFLICT (key) DO UPDATE - so running the same job
twice, or re-loading a file that overlaps what is already stored, never creates duplicates:

* the conflict target is the natural key (scheme code; fund + date; symbol + date; month);
* the UPDATE has a WHERE ... IS DISTINCT FROM ... clause, so a row whose values have not
  changed is not rewritten (no dead row versions), and RETURNING lists only the rows that
  were inserted or changed - so a re-run reports 0 rows written;
* rows are sent in chunks of multi-row INSERT statements: one round trip per few thousand
  rows instead of one per row, and within PostgreSQL's 65,535 parameters per statement.
"""

from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Table, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.data_pipeline.amfi import AmfiRow
from app.data_pipeline.cpi import CpiPoint
from app.models.market import Fund, FundMetrics, IndexHistory, InflationData, NavHistory

MAX_PARAMETERS = 30_000  # per statement; PostgreSQL's limit is 65,535


def _chunks(rows: Sequence[dict], size: int) -> Iterable[Sequence[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def bulk_upsert(
    db: Session,
    table: Table,
    rows: Sequence[dict[str, Any]],
    key: list[str],
    extra_set: dict[str, Any] | None = None,
) -> int:
    """Insert rows; on a key conflict update the other columns only if a value changed.

    Returns the number of rows inserted or changed.
    """
    if not rows:
        return 0
    columns = [name for name in rows[0] if name not in key]
    written = 0
    for chunk in _chunks(rows, max(1, MAX_PARAMETERS // len(rows[0]))):
        statement = insert(table).values(list(chunk))
        if columns:
            statement = statement.on_conflict_do_update(
                index_elements=key,
                set_={name: statement.excluded[name] for name in columns} | (extra_set or {}),
                where=or_(
                    *(table.c[name].is_distinct_from(statement.excluded[name]) for name in columns)
                ),
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=key)
        written += _count(db, statement, table.c[key[0]])
    return written


def _count(db: Session, statement: Any, column: Any) -> int:
    """Rows inserted or updated by an upsert. (The driver reports rowcount -1 for multi-row
    statements, so RETURNING is used: skipped conflicts return nothing.)"""
    return len(db.execute(statement.returning(column)).all())


def upsert_funds(db: Session, rows: Sequence[AmfiRow]) -> int:
    """Create or refresh funds from AMFI rows, including the denormalised latest NAV.

    The latest NAV only moves FORWARD in time: re-loading an older file cannot overwrite a
    newer NAV with a stale one.
    """
    if not rows:
        return 0
    table = Fund.__table__
    records = [
        {
            "scheme_code": row.scheme_code,
            "name": row.name[:200],
            "amc": row.amc[:120],
            "scheme_type": row.scheme_type[:30],
            "category": row.category[:120],
            "asset_class": row.asset_class,
            "plan": row.plan,
            "option": row.option,
            "isin_growth": row.isin_growth,
            "isin_reinvestment": row.isin_reinvestment,
            "latest_nav": row.nav,
            "latest_nav_date": row.nav_date,
        }
        for row in rows
    ]
    descriptive = [
        name for name in records[0] if name not in ("scheme_code", "latest_nav", "latest_nav_date")
    ]
    written = 0
    for chunk in _chunks(records, MAX_PARAMETERS // len(records[0])):
        statement = insert(table).values(list(chunk))
        new = statement.excluded
        is_newer = or_(
            table.c.latest_nav_date.is_(None), new.latest_nav_date >= table.c.latest_nav_date
        )
        statement = statement.on_conflict_do_update(
            index_elements=["scheme_code"],
            set_={name: new[name] for name in descriptive}
            | {
                "latest_nav": case((is_newer, new.latest_nav), else_=table.c.latest_nav),
                "latest_nav_date": case(
                    (is_newer, new.latest_nav_date), else_=table.c.latest_nav_date
                ),
                "updated_at": func.now(),
            },
            where=or_(
                *(table.c[name].is_distinct_from(new[name]) for name in descriptive),
                _nav_moves_forward(table, new),
            ),
        )
        written += _count(db, statement, table.c.id)
    return written


def _nav_moves_forward(table: Table, new: Any) -> Any:
    """True when the incoming NAV is newer than the stored one, or same day but different."""
    return or_(
        table.c.latest_nav_date.is_(None),
        new.latest_nav_date > table.c.latest_nav_date,
        (new.latest_nav_date == table.c.latest_nav_date)
        & table.c.latest_nav.is_distinct_from(new.latest_nav),
    )


def fund_ids_by_scheme_code(db: Session) -> dict[int, int]:
    rows = select(Fund.scheme_code, Fund.id).where(Fund.scheme_code.is_not(None))
    return dict(db.execute(rows).all())


def upsert_navs(db: Session, rows: Sequence[dict[str, Any]]) -> int:
    """NAVs of one or many funds: dicts with fund_id, nav_date, nav."""
    return bulk_upsert(db, NavHistory.__table__, rows, key=["fund_id", "nav_date"])


def upsert_index_closes(db: Session, symbol: str, points: Sequence[tuple[date, Decimal]]) -> int:
    rows = [{"symbol": symbol, "trade_date": day, "close": close} for day, close in points]
    return bulk_upsert(db, IndexHistory.__table__, rows, key=["symbol", "trade_date"])


def upsert_cpi(db: Session, base_year: int, points: Sequence[CpiPoint]) -> int:
    rows = [
        {"base_year": base_year, "period": p.period, "cpi": p.cpi, "is_final": p.is_final}
        for p in points
    ]
    return bulk_upsert(db, InflationData.__table__, rows, key=["base_year", "period"])


def upsert_metrics(db: Session, rows: Sequence[dict[str, Any]]) -> int:
    """One row per fund; computed_at is refreshed whenever a value changes."""
    return bulk_upsert(
        db, FundMetrics.__table__, rows, key=["fund_id"], extra_set={"computed_at": func.now()}
    )
