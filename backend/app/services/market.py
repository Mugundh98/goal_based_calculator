"""Benchmark indices, inflation and pipeline status for the API."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data_pipeline.cpi import DEFAULT_BASE_YEAR
from app.data_pipeline.indices import INDICES
from app.finance.fund_metrics import shift_months
from app.finance.tvm import cagr
from app.models.market import Fund, FundMetrics, IndexHistory, InflationData, JobRun
from app.schemas.market import (
    IndexSummary,
    InflationPoint,
    JobRunOut,
    MarketSummary,
    SeriesPoint,
)
from app.services.funds import active_since, newest_nav_date

PERCENT = 100


def _close_on_or_before(db: Session, symbol: str, day: date) -> tuple[date, float] | None:
    row = db.execute(
        select(IndexHistory.trade_date, IndexHistory.close)
        .where(IndexHistory.symbol == symbol, IndexHistory.trade_date <= day)
        .order_by(IndexHistory.trade_date.desc())
        .limit(1)
    ).first()
    return (row[0], float(row[1])) if row else None


def index_summary(db: Session, symbol: str) -> IndexSummary:
    """Latest close and 1-year return (two index lookups on the primary key)."""
    latest = _close_on_or_before(db, symbol, date.max)
    year_ago = _close_on_or_before(db, symbol, shift_months(latest[0], -12)) if latest else None
    return IndexSummary(
        symbol=symbol,
        name=INDICES[symbol],
        latest_close=latest[1] if latest else None,
        latest_date=latest[0] if latest else None,
        return_1y=round(cagr(year_ago[1], latest[1], 1) * PERCENT, 2) if year_ago else None,
    )


def index_history(db: Session, symbol: str, start: date | None) -> list[SeriesPoint]:
    query = select(IndexHistory.trade_date, IndexHistory.close).where(IndexHistory.symbol == symbol)
    if start:
        query = query.where(IndexHistory.trade_date >= start)
    return [
        SeriesPoint(date=day, value=close)
        for day, close in db.execute(query.order_by(IndexHistory.trade_date)).all()
    ]


def inflation_series(db: Session, base_year: int = DEFAULT_BASE_YEAR) -> list[InflationPoint]:
    """Monthly CPI with year-on-year inflation: CPI(month) / CPI(same month last year) - 1.

    Derived when read, like goal projections: the stored fact is the index.
    """
    rows = db.execute(
        select(InflationData.period, InflationData.cpi)
        .where(InflationData.base_year == base_year)
        .order_by(InflationData.period)
    ).all()
    by_period = {period: float(cpi) for period, cpi in rows}
    points = []
    for period, cpi in by_period.items():
        year_ago = by_period.get(shift_months(period, -12))
        inflation = round((cpi / year_ago - 1) * PERCENT, 2) if year_ago else None
        points.append(InflationPoint(period=period, cpi=cpi, inflation_yoy=inflation))
    return points


def recent_runs(db: Session, limit: int = 20, job_name: str | None = None) -> list[JobRun]:
    query = select(JobRun).order_by(JobRun.started_at.desc(), JobRun.id.desc()).limit(limit)
    if job_name:
        query = query.where(JobRun.job_name == job_name)
    return list(db.scalars(query))


def last_run_of_each_job(db: Session) -> list[JobRun]:
    """DISTINCT ON keeps the first row of each job_name in the given order: the newest run."""
    query = (
        select(JobRun)
        .distinct(JobRun.job_name)
        .order_by(JobRun.job_name, JobRun.started_at.desc(), JobRun.id.desc())
    )
    return list(db.scalars(query))


def summary(db: Session) -> MarketSummary:
    since = active_since(db)
    inflation = inflation_series(db)
    return MarketSummary(
        fund_count=db.scalar(select(func.count()).select_from(Fund)) or 0,
        active_fund_count=(
            db.scalar(select(func.count()).where(Fund.latest_nav_date >= since)) if since else 0
        )
        or 0,
        funds_with_metrics=db.scalar(select(func.count()).select_from(FundMetrics)) or 0,
        latest_nav_date=newest_nav_date(db),
        indices=[index_summary(db, symbol) for symbol in INDICES],
        latest_inflation=inflation[-1] if inflation else None,
        last_runs=[JobRunOut.model_validate(run) for run in last_run_of_each_job(db)],
    )
