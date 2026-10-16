"""Pipeline jobs against the real test database: upserts, idempotency and the job log."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.data_pipeline import jobs
from app.data_pipeline.indices import INDICES
from app.models import Fund, FundMetrics, IndexHistory, InflationData, JobRun, NavHistory
from app.services.market import inflation_series
from tests.pipeline_samples import CPI_RECORDS, MFAPI_HISTORY, NAV_ALL, NAV_ALL_NEXT_DAY


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def fund(db, scheme_code):
    return db.scalar(select(Fund).where(Fund.scheme_code == scheme_code))


def navs(db, scheme_code):
    return db.execute(
        select(NavHistory.nav_date, NavHistory.nav)
        .join(Fund)
        .where(Fund.scheme_code == scheme_code)
        .order_by(NavHistory.nav_date)
    ).all()


# --- Daily NAV load ---------------------------------------------------------------------------


def test_daily_nav_loads_funds_and_navs(db):
    result = jobs.daily_nav(db, text=NAV_ALL)
    assert (result.rows_read, result.rows_written) == (11, 7)
    assert result.details["funds_written"] == 7
    assert result.details["skipped"]["nav_not_positive"] == 1
    assert result.details["latest_nav_date"] == "2026-10-15"
    assert count(db, Fund) == 7 and count(db, NavHistory) == 7

    axis = fund(db, 120465)
    assert (axis.name, axis.amc, axis.category, axis.asset_class) == (
        "Axis Large Cap Fund", "Axis Mutual Fund", "Large Cap Fund", "equity",
    )  # fmt: skip
    assert (axis.latest_nav, axis.latest_nav_date) == (Decimal("62.15"), date(2026, 10, 15))


def test_daily_nav_is_idempotent(db):
    jobs.daily_nav(db, text=NAV_ALL)
    again = jobs.daily_nav(db, text=NAV_ALL)
    # Same file again: nothing inserted, nothing rewritten.
    assert again.rows_written == 0 and again.details["funds_written"] == 0
    assert count(db, Fund) == 7 and count(db, NavHistory) == 7


def test_next_day_appends_a_nav_and_moves_latest_forward(db):
    jobs.daily_nav(db, text=NAV_ALL)
    next_day = jobs.daily_nav(db, text=NAV_ALL_NEXT_DAY)
    assert next_day.rows_written == 1 and next_day.details["funds_written"] == 1
    assert navs(db, 120465) == [
        (date(2026, 10, 15), Decimal("62.15")),
        (date(2026, 10, 16), Decimal("63")),
    ]
    assert fund(db, 120465).latest_nav_date == date(2026, 10, 16)


def test_an_older_file_never_overwrites_the_latest_nav(db):
    jobs.daily_nav(db, text=NAV_ALL_NEXT_DAY)
    older = jobs.daily_nav(db, text=NAV_ALL)
    assert older.rows_written == 1  # the 15 Oct NAV is still added to the history
    assert older.details["funds_written"] == 0
    axis = fund(db, 120465)
    assert (axis.latest_nav, axis.latest_nav_date) == (Decimal("63"), date(2026, 10, 16))


def test_corrected_nav_is_updated(db):
    jobs.daily_nav(db, text=NAV_ALL)
    corrected = jobs.daily_nav(db, text=NAV_ALL.replace("62.1500", "62.2000"))
    assert corrected.rows_written == 1  # same day, new value: UPDATE, not a second row
    assert navs(db, 120465) == [(date(2026, 10, 15), Decimal("62.2"))]


def test_database_rejects_duplicate_and_invalid_navs(db):
    jobs.daily_nav(db, text=NAV_ALL)
    fund_id = fund(db, 120465).id
    db.add(NavHistory(fund_id=fund_id, nav_date=date(2026, 10, 15), nav=Decimal(1)))
    with pytest.raises(IntegrityError):  # composite primary key (fund_id, nav_date)
        db.flush()
    db.rollback()
    db.add(NavHistory(fund_id=fund_id, nav_date=date(2026, 10, 1), nav=Decimal(0)))
    with pytest.raises(IntegrityError):  # CHECK nav > 0
        db.flush()


# --- Backfill, indices, CPI -------------------------------------------------------------------


@pytest.fixture
def history_cache(tmp_path):
    """Pre-filled download cache, so the backfill never goes to the network."""
    (tmp_path / "120465.json").write_text(json.dumps(MFAPI_HISTORY))
    for code in (119091, 120716):
        (tmp_path / f"{code}.json").write_text('{"data": [{"date": "01-10-2026", "nav": "10"}]}')
    return tmp_path


def test_backfill_loads_history_of_direct_growth_funds(db, history_cache):
    jobs.daily_nav(db, text=NAV_ALL)
    result = jobs.backfill_nav(db, cache_dir=history_cache)
    # Candidates: open-ended, direct, growth, active -> equity 120465, debt 119091, index 120716
    assert result.details["funds"] == 3
    assert result.rows_read == 6 and result.rows_written == 5  # 15 Oct 2026 was already loaded
    assert [day for day, _ in navs(db, 120465)] == [
        date(2021, 10, 15), date(2025, 10, 10), date(2026, 10, 14), date(2026, 10, 15),
    ]  # fmt: skip
    assert result.details["skipped"] == {"duplicate_date": 1, "bad_row": 1}
    assert result.details["funds_with_gaps"] == 1  # the sample skips 2021 -> 2025
    assert result.details["largest_gaps"][0] == {
        "scheme_code": 120465,
        "days": 1456,
        "until": "2025-10-10",
    }

    assert jobs.backfill_nav(db, cache_dir=history_cache).rows_written == 0  # idempotent


def test_backfill_filters_and_limit(db, history_cache):
    jobs.daily_nav(db, text=NAV_ALL)
    only_equity = jobs.backfill_nav(db, asset_classes=("equity",), cache_dir=history_cache)
    assert only_equity.details["funds"] == 1
    assert jobs.backfill_nav(db, limit=1, cache_dir=history_cache).details["funds"] == 1


def test_index_history_full_then_incremental(db):
    calls = []

    def fake_fetch(symbol, start):
        calls.append((symbol, start))
        return [(date(2026, 10, 14), 24000.0), (date(2026, 10, 15), 24100.5)]

    first = jobs.index_history(db, fetch=fake_fetch)
    assert first.rows_written == 2 * len(INDICES)
    assert all(start is None for _, start in calls)  # nothing stored yet: whole history

    calls.clear()
    again = jobs.index_history(db, fetch=fake_fetch)
    assert again.rows_written == 0
    # Afterwards only the last few days are fetched (overlap catches late corrections).
    assert {start for _, start in calls} == {date(2026, 10, 5)}
    assert count(db, IndexHistory) == 2 * len(INDICES)


def test_inflation_job_and_year_on_year_inflation(db):
    result = jobs.inflation(db, records=CPI_RECORDS)
    assert result.rows_written == 5
    assert count(db, InflationData) == 5
    latest = inflation_series(db)[-1]
    # December 2025 over December 2024: 198.0 / 195.4 - 1 = 1.33% (MOSPI publishes 1.33)
    assert (latest.period, latest.inflation_yoy) == (date(2025, 12, 1), 1.33)
    assert inflation_series(db)[0].inflation_yoy is None  # no month a year earlier


# --- Fund metrics -----------------------------------------------------------------------------


def test_fund_metrics_job(db):
    jobs.daily_nav(db, text=NAV_ALL)  # Axis Large Cap: 62.15 on 15 Oct 2026
    axis = fund(db, 120465)
    start = date(2025, 9, 1)

    def nav(day: int) -> Decimal:  # rising 0.05% a day
        return Decimal(50 * 1.0005**day).quantize(Decimal("0.0001"))

    # 409 daily NAVs from 1 Sep 2025 to 14 Oct 2026
    db.add_all(
        NavHistory(fund_id=axis.id, nav_date=start + timedelta(days=k), nav=nav(k))
        for k in range(409)
    )
    db.commit()

    result = jobs.fund_metrics(db, risk_free_rate=0.06)
    assert result.details["funds"] == 1  # the other funds have a single NAV
    metrics = db.get(FundMetrics, axis.id)
    # 1 year: 15 Oct 2025 (day 44 of the series) to 15 Oct 2026
    assert metrics.return_1y == pytest.approx((62.15 / float(nav(44)) - 1) * 100, abs=1e-3)
    assert metrics.return_3y is None  # only a year of history
    assert metrics.rolling_1y_positive == 100
    assert metrics.risk_free_rate == 6
    assert metrics.as_of_date == date(2026, 10, 15)
    assert metrics.history_start == start

    assert jobs.fund_metrics(db, risk_free_rate=0.06).rows_written == 0  # unchanged values


def test_fund_metrics_ignore_a_face_value_change(db):
    """The same fund, but its units were worth ten times more until day 300 (a 1:10 change):
    every statistic must be exactly as if nothing had happened."""
    jobs.daily_nav(db, text=NAV_ALL)
    axis = fund(db, 120465)
    start = date(2025, 9, 1)

    def nav(day: int) -> Decimal:
        value = 50 * 1.0005**day * (10 if day < 300 else 1)
        return Decimal(value).quantize(Decimal("0.0001"))

    db.add_all(
        NavHistory(fund_id=axis.id, nav_date=start + timedelta(days=k), nav=nav(k))
        for k in range(409)
    )
    db.commit()
    result = jobs.fund_metrics(db, risk_free_rate=0.06)
    assert result.details["unit_changes"] == 1
    metrics = db.get(FundMetrics, axis.id)
    unadjusted_day_44 = float(nav(44)) / 10
    assert metrics.return_1y == pytest.approx((62.15 / unadjusted_day_44 - 1) * 100, abs=1e-2)
    assert metrics.rolling_1y_positive == 100  # no fake -90% year


# --- The job runner and job_runs --------------------------------------------------------------


def test_run_job_records_a_successful_run(db):
    run = jobs.run_job("daily_nav", triggered_by="cli", db=db, text=NAV_ALL)
    stored = db.get(JobRun, run.id)
    assert (stored.status, stored.triggered_by) == ("success", "cli")
    assert (stored.rows_read, stored.rows_written) == (11, 7)
    assert stored.details["skipped"]["bad_date"] == 1
    assert stored.finished_at is not None and stored.error is None


def test_run_job_records_a_failure_and_rolls_back(db, monkeypatch):
    def broken(session):
        session.add(Fund(scheme_code=1, name="x", amc="x", scheme_type="x", category="x",
                         asset_class="equity", plan="direct", option="growth"))  # fmt: skip
        session.flush()
        raise RuntimeError("source is down")

    monkeypatch.setitem(jobs.JOBS, "broken", broken)
    run = jobs.run_job("broken", db=db)
    assert run.status == "failed"
    assert run.error == "RuntimeError: source is down"
    assert count(db, Fund) == 0  # the half-done work was rolled back


def test_only_one_run_of_a_job_at_a_time(db):
    db.add(JobRun(job_name="daily_nav", triggered_by="scheduler", status="running", details={}))
    db.commit()
    run = jobs.run_job("daily_nav", db=db, text=NAV_ALL)
    assert run.status == "skipped"
    assert count(db, Fund) == 0  # the job did not run

    # The partial unique index enforces it in the database itself.
    db.add(JobRun(job_name="daily_nav", triggered_by="cli", status="running", details={}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_crashed_run_does_not_block_the_job_forever(db):
    crashed = JobRun(
        job_name="daily_nav",
        triggered_by="scheduler",
        status="running",
        started_at=datetime.now(UTC) - timedelta(hours=7),
        details={},
    )
    db.add(crashed)
    db.commit()
    assert jobs.run_job("daily_nav", db=db, text=NAV_ALL).status == "success"
    db.refresh(crashed)
    assert (crashed.status, crashed.error) == ("failed", "abandoned (process stopped)")


def test_unknown_job(db):
    with pytest.raises(ValueError, match="unknown job"):
        jobs.run_job("nope", db=db)
