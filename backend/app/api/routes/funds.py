from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models.market import Fund
from app.schemas.market import (
    AssetClass,
    CategoryCount,
    FundDetail,
    FundNavHistory,
    FundPage,
    FundSort,
    Option,
    Period,
    Plan,
    SortOrder,
)
from app.services import funds as service

router = APIRouter(prefix="/funds", tags=["funds"])


def existing_fund(db: DbSession, fund_id: int) -> Fund:
    fund = service.get_fund(db, fund_id)
    if fund is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Fund not found")
    return fund


@router.get("", response_model=FundPage)
def list_funds(
    _: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100, description="Name, fund house or code")] = None,
    asset_class: AssetClass | None = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    plan: Plan | None = None,
    option: Option | None = None,
    active_only: bool = True,
    sort: FundSort = "name",
    order: SortOrder = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FundPage:
    """Search, filter, sort and page through mutual funds with their key metrics."""
    return service.list_funds(
        db,
        q=q,
        asset_class=asset_class,
        category=category,
        plan=plan,
        option=option,
        active_only=active_only,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/categories", response_model=list[CategoryCount])
def categories(_: CurrentUser, db: DbSession, active_only: bool = True) -> list[CategoryCount]:
    """Asset classes and SEBI categories with fund counts (for the filters)."""
    return service.categories(db, active_only)


@router.get("/{fund_id}", response_model=FundDetail)
def read_fund(fund_id: int, _: CurrentUser, db: DbSession) -> FundDetail:
    return service.to_detail(db, existing_fund(db, fund_id))


@router.get("/{fund_id}/nav", response_model=FundNavHistory)
def nav_history(
    fund_id: int, _: CurrentUser, db: DbSession, period: Period = "3y"
) -> FundNavHistory:
    """Daily NAVs for the period, oldest first, in today's units (face-value changes listed)."""
    fund = existing_fund(db, fund_id)
    points, unit_changes = service.nav_history(db, fund, period)
    return FundNavHistory(fund_id=fund.id, period=period, points=points, unit_changes=unit_changes)
