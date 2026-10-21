"""Market data loaded by the data pipeline (Phase 4): funds, NAVs, indices, inflation, job log.

Unlike the user tables, these rows are not owned by a user. They are facts copied from public
sources (AMFI, NSE via Yahoo Finance, MOSPI) and refreshed by scheduled jobs.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

ASSET_CLASSES = (
    "equity",
    "debt",
    "hybrid",
    "index",
    "etf",
    "fund_of_funds",
    "solution_oriented",
    "other",
)
PLANS = ("direct", "regular")
OPTIONS = ("growth", "idcw", "bonus", "other")
JOB_STATUSES = ("running", "success", "failed", "skipped")

# NAVs are published with up to 8 decimal places (some liquid and arbitrage funds).
Nav = Numeric(18, 8)


class Fund(TimestampMixin, Base):
    """One mutual fund scheme as listed by AMFI (each plan/option has its own scheme code).

    A fund a user adds by hand (not in AMFI's list) is a row with an owner and no scheme code: it
    has no NAV history, so its transactions carry the NAV the user entered and its holdings are
    valued at cost. It is visible only to its owner, never in the explorer or recommendations.
    """

    __tablename__ = "funds"
    __table_args__ = (
        CheckConstraint(
            "asset_class IN ('equity', 'debt', 'hybrid', 'index', 'etf', 'fund_of_funds', "
            "'solution_oriented', 'other')",
            name="ck_funds_asset_class",
        ),
        CheckConstraint("plan IN ('direct', 'regular')", name="ck_funds_plan"),
        CheckConstraint("option IN ('growth', 'idcw', 'bonus', 'other')", name="ck_funds_option"),
        CheckConstraint("latest_nav IS NULL OR latest_nav > 0", name="ck_funds_latest_nav"),
        # AMFI funds have a scheme code and no owner; a user's own fund has an owner and no code.
        CheckConstraint(
            "(owner_user_id IS NULL) = (scheme_code IS NOT NULL)", name="ck_funds_manual"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # AMFI's own identifier: the natural key used to match every daily file to this row.
    scheme_code: Mapped[int | None] = mapped_column(Integer, unique=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    amc: Mapped[str] = mapped_column(String(120), index=True)  # fund house
    scheme_type: Mapped[str] = mapped_column(String(30))  # Open Ended / Close Ended / Interval
    category: Mapped[str] = mapped_column(String(120), index=True)  # e.g. "Large Cap Fund"
    asset_class: Mapped[str] = mapped_column(String(20), index=True)  # normalised, see above
    plan: Mapped[str] = mapped_column(String(10))
    option: Mapped[str] = mapped_column(String(10))
    isin_growth: Mapped[str | None] = mapped_column(String(12))
    isin_reinvestment: Mapped[str | None] = mapped_column(String(12))
    expense_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # % a year (later)
    # Copied from the newest nav_history row (controlled redundancy): the fund list shows the
    # latest NAV for thousands of funds without scanning the largest table.
    latest_nav: Mapped[Decimal | None] = mapped_column(Nav)
    latest_nav_date: Mapped[date | None] = mapped_column(Date)

    metrics: Mapped["FundMetrics | None"] = relationship(
        back_populates="fund", cascade="all, delete-orphan", uselist=False
    )


class NavHistory(Base):
    """One NAV per fund per day - the largest table (millions of rows)."""

    __tablename__ = "nav_history"
    __table_args__ = (CheckConstraint("nav > 0", name="ck_nav_history_nav"),)

    # Composite primary key (fund_id, nav_date): no duplicates possible, and its index serves
    # the only query this table gets - "the NAVs of fund X between two dates".
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id", ondelete="CASCADE"), primary_key=True
    )
    nav_date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[Decimal] = mapped_column(Nav)


class FundMetrics(Base):
    """Return and risk statistics for a fund, recomputed after each NAV load (one row per fund).

    Stored, unlike goal projections, because they need the fund's whole NAV history and the fund
    explorer sorts thousands of funds by them. Percentages (12.5 = 12.5%) except the ratios.
    Floats: derived statistics, not money (see ADR-007).
    """

    __tablename__ = "fund_metrics"

    fund_id: Mapped[int] = mapped_column(
        ForeignKey("funds.id", ondelete="CASCADE"), primary_key=True
    )
    as_of_date: Mapped[date] = mapped_column(Date)  # date of the latest NAV used
    history_start: Mapped[date] = mapped_column(Date)  # date of the first NAV available
    return_1y: Mapped[float | None] = mapped_column(Float)  # CAGR, %
    return_3y: Mapped[float | None] = mapped_column(Float)
    return_5y: Mapped[float | None] = mapped_column(Float)
    rolling_1y_avg: Mapped[float | None] = mapped_column(Float)  # every 1-year window, %
    rolling_1y_min: Mapped[float | None] = mapped_column(Float)
    rolling_1y_max: Mapped[float | None] = mapped_column(Float)
    rolling_1y_positive: Mapped[float | None] = mapped_column(Float)  # % of windows above 0
    rolling_3y_avg: Mapped[float | None] = mapped_column(Float)
    rolling_3y_min: Mapped[float | None] = mapped_column(Float)
    rolling_3y_max: Mapped[float | None] = mapped_column(Float)
    rolling_3y_positive: Mapped[float | None] = mapped_column(Float)
    volatility: Mapped[float | None] = mapped_column(Float)  # annualised, last 3 years, %
    sharpe: Mapped[float | None] = mapped_column(Float)  # last 3 years
    sortino: Mapped[float | None] = mapped_column(Float)  # last 3 years
    max_drawdown: Mapped[float | None] = mapped_column(Float)  # last 3 years, % (negative)
    # The assumption behind Sharpe and Sortino, stored with them (% a year).
    risk_free_rate: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    fund: Mapped[Fund] = relationship(back_populates="metrics")


class IndexHistory(Base):
    """Daily closing level of a market index (Nifty 50, ...), the benchmark for funds."""

    __tablename__ = "index_history"
    __table_args__ = (CheckConstraint("close > 0", name="ck_index_history_close"),)

    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)  # Yahoo symbol, ^NSEI
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[Decimal] = mapped_column(Numeric(14, 4))


class InflationData(Base):
    """Monthly Consumer Price Index (All India, Combined, General) published by MOSPI.

    Only the index is stored; year-on-year inflation is calculated when read.
    """

    __tablename__ = "inflation_data"
    __table_args__ = (CheckConstraint("cpi > 0", name="ck_inflation_data_cpi"),)

    base_year: Mapped[int] = mapped_column(SmallInteger, primary_key=True)  # 2012 = 100
    period: Mapped[date] = mapped_column(Date, primary_key=True)  # first day of the month
    cpi: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    is_final: Mapped[bool] = mapped_column(server_default="true")  # False = provisional


class JobRun(Base):
    """One execution of a pipeline job: the pipeline's audit log."""

    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'failed', 'skipped')", name="ck_job_runs_status"
        ),
        # Partial unique index: at most ONE running row per job. The database itself stops
        # two processes (two API workers, the CLI) from running the same job at once.
        Index(
            "uq_job_runs_one_running",
            "job_name",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(10), server_default="running")
    triggered_by: Mapped[str] = mapped_column(String(20))  # scheduler / cli / admin
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_read: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_written: Mapped[int] = mapped_column(Integer, server_default="0")
    # Data-quality counts (rows skipped and why), sources used, ...
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text)
