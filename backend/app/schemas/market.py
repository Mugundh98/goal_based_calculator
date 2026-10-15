from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

AssetClass = Literal[
    "equity", "debt", "hybrid", "index", "etf", "fund_of_funds", "solution_oriented", "other"
]
Plan = Literal["direct", "regular"]
Option = Literal["growth", "idcw", "bonus", "other"]
FundSort = Literal[
    "name", "latest_nav", "return_1y", "return_3y", "return_5y", "volatility", "sharpe",
    "sortino", "max_drawdown",
]  # fmt: skip
SortOrder = Literal["asc", "desc"]
Period = Literal["1y", "3y", "5y", "10y", "max"]

# Percentages are percent (12.5 = 12.5%); sharpe and sortino are plain ratios.


class FundListItem(BaseModel):
    id: int
    scheme_code: int
    name: str
    amc: str
    category: str
    asset_class: AssetClass
    plan: Plan
    option: Option
    latest_nav: float | None
    latest_nav_date: date | None
    return_1y: float | None
    return_3y: float | None
    return_5y: float | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None


class FundPage(BaseModel):
    items: list[FundListItem]
    total: int  # matching funds, for pagination
    page: int
    page_size: int


class CategoryCount(BaseModel):
    asset_class: AssetClass
    category: str
    count: int


class FundMetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of_date: date
    history_start: date
    return_1y: float | None
    return_3y: float | None
    return_5y: float | None
    rolling_1y_avg: float | None
    rolling_1y_min: float | None
    rolling_1y_max: float | None
    rolling_1y_positive: float | None
    rolling_3y_avg: float | None
    rolling_3y_min: float | None
    rolling_3y_max: float | None
    rolling_3y_positive: float | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    risk_free_rate: float  # percent, used for Sharpe and Sortino
    computed_at: datetime


class FundDetail(BaseModel):
    id: int
    scheme_code: int
    name: str
    amc: str
    scheme_type: str
    category: str
    asset_class: AssetClass
    plan: Plan
    option: Option
    isin_growth: str | None
    isin_reinvestment: str | None
    expense_ratio: float | None
    latest_nav: float | None
    latest_nav_date: date | None
    is_active: bool  # published a NAV in the last 30 days
    benchmark: str  # index symbol to compare with
    metrics: FundMetricsOut | None


class SeriesPoint(BaseModel):
    date: date
    value: float


class FundNavHistory(BaseModel):
    fund_id: int
    period: Period
    points: list[SeriesPoint]  # NAVs, oldest first


class IndexSummary(BaseModel):
    symbol: str
    name: str
    latest_close: float | None
    latest_date: date | None
    return_1y: float | None  # percent


class IndexHistoryOut(BaseModel):
    symbol: str
    name: str
    points: list[SeriesPoint]  # closing levels, oldest first


class InflationPoint(BaseModel):
    period: date  # first day of the month
    cpi: float
    inflation_yoy: float | None  # percent; None for the first 12 months


class InflationOut(BaseModel):
    base_year: int
    points: list[InflationPoint]


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_name: str
    status: str
    triggered_by: str
    started_at: datetime
    finished_at: datetime | None
    rows_read: int
    rows_written: int
    details: dict[str, Any]
    error: str | None


class MarketSummary(BaseModel):
    """Everything the fund explorer header shows: freshness of each data set."""

    fund_count: int
    active_fund_count: int
    funds_with_metrics: int
    latest_nav_date: date | None
    indices: list[IndexSummary]
    latest_inflation: InflationPoint | None
    last_runs: list[JobRunOut]  # the latest run of each job
