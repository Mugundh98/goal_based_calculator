"""Fund explorer queries: search, filter, sort and page through funds; one fund's details."""

from datetime import date, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.data_pipeline.indices import DEFAULT_BENCHMARK
from app.data_pipeline.jobs import ACTIVE_WITHIN_DAYS
from app.finance.fund_metrics import shift_months
from app.models.market import Fund, FundMetrics, NavHistory
from app.schemas.market import (
    CategoryCount,
    FundDetail,
    FundListItem,
    FundMetricsOut,
    FundPage,
    FundSort,
    Period,
    SeriesPoint,
    SortOrder,
)

PERIOD_YEARS: dict[str, int | None] = {"1y": 1, "3y": 3, "5y": 5, "10y": 10, "max": None}
METRIC_COLUMNS = ("return_1y", "return_3y", "return_5y", "volatility", "sharpe", "sortino")


def newest_nav_date(db: Session) -> date | None:
    return db.scalar(select(func.max(Fund.latest_nav_date)))


def active_since(db: Session) -> date | None:
    """Funds whose latest NAV is older than this have closed, matured or merged."""
    newest = newest_nav_date(db)
    return newest - timedelta(days=ACTIVE_WITHIN_DAYS) if newest else None


def _filtered(
    db: Session,
    query: Select,
    q: str | None,
    asset_class: str | None,
    category: str | None,
    plan: str | None,
    option: str | None,
    active_only: bool,
) -> Select:
    if q:
        text = q.strip()
        conditions = [
            Fund.name.icontains(text, autoescape=True),  # % and _ typed by users are literal
            Fund.amc.icontains(text, autoescape=True),
        ]
        if text.isdigit():
            conditions.append(Fund.scheme_code == int(text))
        query = query.where(or_(*conditions))
    if asset_class:
        query = query.where(Fund.asset_class == asset_class)
    if category:
        query = query.where(Fund.category == category)
    if plan:
        query = query.where(Fund.plan == plan)
    if option:
        query = query.where(Fund.option == option)
    if active_only and (since := active_since(db)):
        query = query.where(Fund.latest_nav_date >= since)
    return query


def list_funds(
    db: Session,
    *,
    q: str | None = None,
    asset_class: str | None = None,
    category: str | None = None,
    plan: str | None = None,
    option: str | None = None,
    active_only: bool = True,
    sort: FundSort = "name",
    order: SortOrder = "asc",
    page: int = 1,
    page_size: int = 25,
) -> FundPage:
    """One page of funds with their headline metrics. Funds without a metric sort last."""
    filters = (q, asset_class, category, plan, option, active_only)
    total = db.scalar(_filtered(db, select(func.count()).select_from(Fund), *filters)) or 0

    column = getattr(Fund, sort) if sort in ("name", "latest_nav") else getattr(FundMetrics, sort)
    ordering = column.asc() if order == "asc" else column.desc()
    query = _filtered(
        db,
        select(Fund, FundMetrics).outerjoin(FundMetrics, FundMetrics.fund_id == Fund.id),
        *filters,
    )
    query = (
        query.order_by(ordering.nulls_last(), Fund.name, Fund.id)  # id: stable across pages
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    items = []
    for fund, metrics in db.execute(query).all():
        values = {name: getattr(metrics, name) if metrics else None for name in METRIC_COLUMNS}
        items.append(
            FundListItem(
                id=fund.id,
                scheme_code=fund.scheme_code,
                name=fund.name,
                amc=fund.amc,
                category=fund.category,
                asset_class=fund.asset_class,
                plan=fund.plan,
                option=fund.option,
                latest_nav=fund.latest_nav,
                latest_nav_date=fund.latest_nav_date,
                max_drawdown=metrics.max_drawdown if metrics else None,
                **values,
            )
        )
    return FundPage(items=items, total=total, page=page, page_size=page_size)


def categories(db: Session, active_only: bool = True) -> list[CategoryCount]:
    """Every (asset class, category) pair with its number of funds, for the filters."""
    query = _filtered(
        db,
        select(Fund.asset_class, Fund.category, func.count()).group_by(
            Fund.asset_class, Fund.category
        ),
        None,
        None,
        None,
        None,
        None,
        active_only,
    ).order_by(Fund.asset_class, Fund.category)
    return [
        CategoryCount(asset_class=asset_class, category=category, count=count)
        for asset_class, category, count in db.execute(query).all()
    ]


def get_fund(db: Session, fund_id: int) -> Fund | None:
    return db.get(Fund, fund_id)


def to_detail(db: Session, fund: Fund) -> FundDetail:
    since = active_since(db)
    return FundDetail(
        id=fund.id,
        scheme_code=fund.scheme_code,
        name=fund.name,
        amc=fund.amc,
        scheme_type=fund.scheme_type,
        category=fund.category,
        asset_class=fund.asset_class,
        plan=fund.plan,
        option=fund.option,
        isin_growth=fund.isin_growth,
        isin_reinvestment=fund.isin_reinvestment,
        expense_ratio=fund.expense_ratio,
        latest_nav=fund.latest_nav,
        latest_nav_date=fund.latest_nav_date,
        is_active=bool(fund.latest_nav_date and since and fund.latest_nav_date >= since),
        benchmark=DEFAULT_BENCHMARK,
        metrics=FundMetricsOut.model_validate(fund.metrics) if fund.metrics else None,
    )


def nav_history(db: Session, fund: Fund, period: Period) -> list[SeriesPoint]:
    """NAVs for the period, counted back from the fund's latest NAV (oldest first)."""
    query = select(NavHistory.nav_date, NavHistory.nav).where(NavHistory.fund_id == fund.id)
    years = PERIOD_YEARS[period]
    last = db.scalar(select(func.max(NavHistory.nav_date)).where(NavHistory.fund_id == fund.id))
    if years and last:
        query = query.where(NavHistory.nav_date >= shift_months(last, -12 * years))
    return [
        SeriesPoint(date=day, value=nav)
        for day, nav in db.execute(query.order_by(NavHistory.nav_date)).all()
    ]
