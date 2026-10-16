from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.routes.funds import existing_fund
from app.schemas.ml import ClustersOut, FundInsight, InflationOut, ModelCard, RankingsOut
from app.services import ml as service

router = APIRouter(prefix="/ml", tags=["fund intelligence"])


def _unavailable(error: service.ModelUnavailable) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail=f"The {error.args[0]} model has not been trained yet: run python -m app.ml train",
    )


@router.get("/models", response_model=list[ModelCard])
def models(_: CurrentUser, db: DbSession) -> list[ModelCard]:
    """The active model versions and their headline validation results."""
    return service.model_cards(db)


@router.get("/rankings", response_model=RankingsOut)
def rankings(
    _: CurrentUser,
    db: DbSession,
    peer_group: Annotated[str | None, Query(max_length=30)] = None,
) -> RankingsOut:
    """Funds of one peer group, ranked by the expected next-12-month quartile, with reasons."""
    try:
        return service.rankings(db, peer_group)
    except service.ModelUnavailable as error:
        raise _unavailable(error) from None


@router.get("/clusters", response_model=ClustersOut)
def clusters(_: CurrentUser, db: DbSession) -> ClustersOut:
    """Behaviour clusters: profiles and one point per fund for the scatter plot."""
    try:
        return service.clusters(db)
    except service.ModelUnavailable as error:
        raise _unavailable(error) from None


@router.get("/funds/{fund_id}", response_model=FundInsight)
def fund_insight(fund_id: int, _: CurrentUser, db: DbSession) -> FundInsight:
    """The ranker's view and the cluster of one fund (empty when the fund is not covered)."""
    return service.fund_insight(db, existing_fund(db, fund_id))


@router.get("/inflation", response_model=InflationOut)
def inflation(_: CurrentUser, db: DbSession) -> InflationOut:
    """Recent CPI inflation and the SARIMA forecast for the next 12 months."""
    try:
        return service.inflation(db)
    except service.ModelUnavailable as error:
        raise _unavailable(error) from None
