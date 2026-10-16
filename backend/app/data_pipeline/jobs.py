"""Pipeline jobs and the runner that records each run in job_runs.

Each job is Extract (download) -> Transform (parse, validate, classify) -> Load (upsert):
ETL, because the raw files are not useful in the database as they are (section lines,
"N.A." NAVs, mixed category names) and validating BEFORE loading keeps bad rows out.

Every job is idempotent, so the scheduler can safely retry it or run it twice.
"""

import logging
import ssl
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.data_pipeline import amfi, cpi, indices, mfapi
from app.data_pipeline.loaders import (
    fund_ids_by_scheme_code,
    upsert_cpi,
    upsert_funds,
    upsert_index_closes,
    upsert_metrics,
    upsert_navs,
)
from app.finance.fund_metrics import FundStatistics, fund_statistics
from app.finance.nav_adjust import adjust_series
from app.models.market import Fund, IndexHistory, JobRun, NavHistory

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
USER_AGENT = "GoalWise/0.4 (educational project; market data pipeline)"
STALE_RUN_AFTER = timedelta(hours=6)  # a "running" row older than this was a crashed process
ACTIVE_WITHIN_DAYS = 30  # a fund with no NAV for longer is treated as closed or matured
BACKFILL_ASSET_CLASSES = ("equity", "hybrid", "index", "debt")
INDEX_OVERLAP_DAYS = 10  # re-fetch a few days so late corrections are picked up
DOWNLOAD_PAUSE_SECONDS = 0.2  # be polite to free APIs


@dataclass
class JobResult:
    rows_read: int = 0
    rows_written: int = 0
    details: dict[str, Any] = field(default_factory=dict)


def http_client(verify: ssl.SSLContext | bool = True) -> httpx.Client:
    return httpx.Client(
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        verify=verify,
    )


# --- Jobs -------------------------------------------------------------------------------------


def daily_nav(db: Session, text: str | None = None) -> JobResult:
    """Latest NAV of every scheme from AMFI: refresh `funds` and append to `nav_history`."""
    if text is None:
        with http_client() as client:
            text = amfi.fetch_nav_all(client)
    parsed = amfi.parse_nav_all(text)

    funds_written = upsert_funds(db, parsed.rows)
    ids = fund_ids_by_scheme_code(db)
    navs_written = upsert_navs(
        db,
        [
            {"fund_id": ids[row.scheme_code], "nav_date": row.nav_date, "nav": row.nav}
            for row in parsed.rows
        ],
    )
    db.commit()
    dates = Counter(row.nav_date for row in parsed.rows)
    return JobResult(
        rows_read=parsed.rows_read,
        rows_written=navs_written,
        details={
            "funds_written": funds_written,
            "skipped": dict(parsed.skipped),
            "latest_nav_date": max(dates).isoformat() if dates else None,
            "funds_on_latest_date": dates[max(dates)] if dates else 0,
        },
    )


def backfill_candidates(
    db: Session, asset_classes: tuple[str, ...], limit: int | None, only_missing: bool
) -> list[Fund]:
    """Open-ended, direct-plan, growth-option funds that published a NAV recently.

    Direct growth is the cleanest NAV series of each scheme: no distributor commission and no
    payouts that would make the NAV drop without a loss.
    """
    newest = db.scalar(select(func.max(Fund.latest_nav_date)))
    if newest is None:
        return []
    query = select(Fund).where(
        Fund.scheme_type == "Open Ended",
        Fund.plan == "direct",
        Fund.option == "growth",
        Fund.asset_class.in_(asset_classes),
        Fund.latest_nav_date >= newest - timedelta(days=ACTIVE_WITHIN_DAYS),
    )
    if only_missing:  # fewer than ~2 months of NAVs stored = never backfilled
        stored = (
            select(func.count())
            .where(NavHistory.fund_id == Fund.id)
            .correlate(Fund)
            .scalar_subquery()
        )
        query = query.where(stored < 40)
    return list(db.scalars(query.order_by(Fund.asset_class, Fund.name).limit(limit)))


def backfill_nav(
    db: Session,
    asset_classes: tuple[str, ...] = BACKFILL_ASSET_CLASSES,
    limit: int | None = None,
    only_missing: bool = True,
    cache_dir: Path | None = None,
) -> JobResult:
    """Full NAV history of each candidate fund from mfapi.in, cached on disk.

    Commits after every fund, so an interrupted backfill keeps its progress and a re-run
    (only_missing) continues where it stopped.
    """
    cache_dir = cache_dir or Path(get_settings().data_cache_dir) / "mfapi"
    funds = backfill_candidates(db, asset_classes, limit, only_missing)
    result = JobResult(details={"funds": len(funds), "failed": [], "skipped": {}})
    skipped: Counter = Counter()
    gaps: list[dict[str, Any]] = []
    with http_client() as client:
        for fund in funds:
            cached = (cache_dir / f"{fund.scheme_code}.json").exists()
            try:
                document = mfapi.load_history(client, fund.scheme_code, cache_dir)
            except (httpx.HTTPError, ValueError) as exc:
                result.details["failed"].append(
                    {"scheme_code": fund.scheme_code, "error": str(exc)}
                )
                continue
            history = mfapi.parse_history(document)
            skipped.update(history.skipped)
            gap_days, gap_end = history.largest_gap()
            if gap_days > mfapi.GAP_WARNING_DAYS:
                gaps.append(
                    {"scheme_code": fund.scheme_code, "days": gap_days, "until": str(gap_end)}
                )
            rows = [{"fund_id": fund.id, "nav_date": d, "nav": nav} for d, nav in history.points]
            result.rows_read += len(rows)
            result.rows_written += upsert_navs(db, rows)
            db.commit()
            if not cached:
                time.sleep(DOWNLOAD_PAUSE_SECONDS)
    result.details["skipped"] = dict(skipped)
    # Funds with a suspiciously long stretch without NAVs, longest first (at most 20 listed).
    result.details["funds_with_gaps"] = len(gaps)
    result.details["largest_gaps"] = sorted(gaps, key=lambda g: -g["days"])[:20]
    return result


def index_history(
    db: Session,
    full: bool = False,
    fetch: Callable[[str, date | None], list[tuple[date, float | None]]] = indices.fetch_closes,
) -> JobResult:
    """Daily closes of the benchmark indices; only recent days unless `full`."""
    result = JobResult(details={"skipped": {}})
    skipped: Counter = Counter()
    for symbol in indices.INDICES:
        last = db.scalar(
            select(func.max(IndexHistory.trade_date)).where(IndexHistory.symbol == symbol)
        )
        start = None if full or last is None else last - timedelta(days=INDEX_OVERLAP_DAYS)
        series = indices.clean_closes(fetch(symbol, start))
        skipped.update(series.skipped)
        result.rows_read += len(series.points) + series.skipped.total()
        result.rows_written += upsert_index_closes(db, symbol, series.points)
        result.details[symbol] = series.points[-1][0].isoformat() if series.points else None
    db.commit()
    result.details["skipped"] = dict(skipped)
    return result


def inflation(
    db: Session, base_year: int = cpi.DEFAULT_BASE_YEAR, records: list[dict] | None = None
) -> JobResult:
    """Monthly All-India CPI from MOSPI."""
    if records is None:
        with http_client(verify=cpi.mospi_ssl_context()) as client:
            records = cpi.fetch_cpi(client, base_year)
    series = cpi.parse_cpi(records)
    written = upsert_cpi(db, base_year, series.points)
    db.commit()
    return JobResult(
        rows_read=len(records),
        rows_written=written,
        details={
            "base_year": base_year,
            "skipped": dict(series.skipped),
            "latest_month": series.points[-1].period.isoformat() if series.points else None,
        },
    )


MIN_HISTORY_DAYS = 365  # no statistic needs less than a year of NAVs
METRICS_BATCH = 500


def _metrics_row(fund_id: int, stats: FundStatistics, risk_free_rate: float) -> dict[str, Any]:
    def pct(value: float | None) -> float | None:
        return None if value is None else round(value * 100, 4)

    def ratio(value: float | None) -> float | None:
        return None if value is None else round(value, 4)

    row: dict[str, Any] = {
        "fund_id": fund_id,
        "as_of_date": stats.as_of_date,
        "history_start": stats.history_start,
        "return_1y": pct(stats.return_1y),
        "return_3y": pct(stats.return_3y),
        "return_5y": pct(stats.return_5y),
        "volatility": pct(stats.volatility),
        "sharpe": ratio(stats.sharpe),
        "sortino": ratio(stats.sortino),
        "max_drawdown": pct(stats.max_drawdown),
        "risk_free_rate": pct(risk_free_rate),
    }
    for years, summary in ((1, stats.rolling_1y), (3, stats.rolling_3y)):
        row[f"rolling_{years}y_avg"] = pct(summary.average) if summary else None
        row[f"rolling_{years}y_min"] = pct(summary.minimum) if summary else None
        row[f"rolling_{years}y_max"] = pct(summary.maximum) if summary else None
        row[f"rolling_{years}y_positive"] = pct(summary.positive_share) if summary else None
    return row


def fund_metrics(db: Session, risk_free_rate: float | None = None) -> JobResult:
    """Recompute fund_metrics for every fund with at least a year of NAV history."""
    rate = get_settings().risk_free_rate if risk_free_rate is None else risk_free_rate
    fund_ids = list(
        db.scalars(
            select(NavHistory.fund_id)
            .group_by(NavHistory.fund_id)
            .having(
                func.max(NavHistory.nav_date) - func.min(NavHistory.nav_date) >= MIN_HISTORY_DAYS
            )
            .order_by(NavHistory.fund_id)
        )
    )
    result = JobResult(details={"funds": len(fund_ids), "risk_free_rate": rate, "unit_changes": 0})
    batch: list[dict[str, Any]] = []
    for fund_id in fund_ids:
        series = [
            (day, float(nav))
            for day, nav in db.execute(
                select(NavHistory.nav_date, NavHistory.nav)
                .where(NavHistory.fund_id == fund_id)
                .order_by(NavHistory.nav_date)
            ).all()
        ]
        result.rows_read += len(series)
        # A face-value change (NAV x100, /10) is not a return: restate earlier NAVs first.
        series, changes = adjust_series(series)
        result.details["unit_changes"] += len(changes)
        batch.append(_metrics_row(fund_id, fund_statistics(series, rate), rate))
        if len(batch) >= METRICS_BATCH:
            result.rows_written += upsert_metrics(db, batch)
            batch = []
    result.rows_written += upsert_metrics(db, batch)
    db.commit()
    return result


def ml_score(db: Session) -> JobResult:
    """Apply the active ML models (Phase 7) to the latest month: rankings and clusters."""
    from app.ml import train  # imported here: pandas/LightGBM are only needed by this job

    counts = train.score(db)
    return JobResult(rows_written=sum(counts.values()), details=counts)


JOBS: dict[str, Callable[..., JobResult]] = {
    "daily_nav": daily_nav,
    "backfill_nav": backfill_nav,
    "index_history": index_history,
    "inflation": inflation,
    "fund_metrics": fund_metrics,
    "ml_score": ml_score,
}


# --- Runner -----------------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _start(db: Session, job_name: str, triggered_by: str) -> JobRun | None:
    """Insert the 'running' row, or None if this job is already running elsewhere."""
    # A process that crashed mid-job leaves a 'running' row behind; free the job again.
    db.execute(
        update(JobRun)
        .where(
            JobRun.job_name == job_name,
            JobRun.status == "running",
            JobRun.started_at < _now() - STALE_RUN_AFTER,
        )
        .values(status="failed", finished_at=_now(), error="abandoned (process stopped)")
    )
    run = JobRun(job_name=job_name, triggered_by=triggered_by, status="running", details={})
    db.add(run)
    try:
        db.commit()  # the partial unique index allows one 'running' row per job
    except IntegrityError:
        db.rollback()
        return None
    return run


def run_job(
    job_name: str, triggered_by: str = "cli", db: Session | None = None, **options: Any
) -> JobRun:
    """Run one job and record it in job_runs (running -> success / failed, or skipped)."""
    if job_name not in JOBS:
        raise ValueError(f"unknown job {job_name!r}; choose from {sorted(JOBS)}")
    own_session = db is None
    db = db or SessionLocal()
    try:
        run = _start(db, job_name, triggered_by)
        if run is None:
            skipped = JobRun(
                job_name=job_name,
                triggered_by=triggered_by,
                status="skipped",
                finished_at=_now(),
                details={},
                error="another run of this job is still in progress",
            )
            db.add(skipped)
            db.commit()
            return skipped

        logger.info("job %s started (run %s)", job_name, run.id)
        try:
            result = JOBS[job_name](db, **options)
        except Exception as exc:  # recorded, not raised: the scheduler must keep running
            db.rollback()
            logger.exception("job %s failed", job_name)
            run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"[:2000]
        else:
            run.status = "success"
            run.rows_read, run.rows_written = result.rows_read, result.rows_written
            run.details = result.details
        run.finished_at = _now()
        db.commit()
        logger.info("job %s %s: %s rows written", job_name, run.status, run.rows_written)
        return run
    finally:
        if own_session:
            db.close()
