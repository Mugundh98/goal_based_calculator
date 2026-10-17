from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.routes.goals import owned_goal
from app.schemas.portfolio import (
    GoalProgress,
    PortfolioRead,
    SipCreate,
    TransactionCreate,
    TransactionRead,
)
from app.services import portfolio as service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _http(error: service.PortfolioError, conflict: bool = False) -> HTTPException:
    if isinstance(error, service.NotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    code = status.HTTP_409_CONFLICT if conflict else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(code, detail=str(error))


@router.get("", response_model=PortfolioRead)
def read(user: CurrentUser, db: DbSession) -> PortfolioRead:
    """Holdings valued at the latest NAV, totals with XIRR, each goal's status and alerts."""
    return service.portfolio(db, user)


@router.get("/transactions", response_model=list[TransactionRead])
def transactions(
    user: CurrentUser,
    db: DbSession,
    goal_id: int | None = Query(default=None),
    fund_id: int | None = Query(default=None),
) -> list[TransactionRead]:
    """Newest first."""
    return service.list_transactions(db, user, goal_id, fund_id)


@router.post("/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create(data: TransactionCreate, user: CurrentUser, db: DbSession) -> TransactionRead:
    """Record a purchase or redemption at that day's NAV; holdings are updated with it."""
    try:
        transaction = service.add_transaction(db, user, data)
    except service.PortfolioError as error:
        raise _http(error) from None
    return next(t for t in service.list_transactions(db, user) if t.id == transaction.id)


@router.post(
    "/transactions/sip", response_model=list[TransactionRead], status_code=status.HTTP_201_CREATED
)
def create_sip(data: SipCreate, user: CurrentUser, db: DbSession) -> list[TransactionRead]:
    """Record the past instalments of a monthly SIP in one go."""
    try:
        ids = set(service.add_sip(db, user, data))
    except service.PortfolioError as error:
        raise _http(error) from None
    return [t for t in service.list_transactions(db, user) if t.id in ids]


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(transaction_id: int, user: CurrentUser, db: DbSession) -> None:
    try:
        service.delete_transaction(db, user, transaction_id)
    except service.PortfolioError as error:
        raise _http(error, conflict=True) from None


@router.get("/goals/{goal_id}", response_model=GoalProgress)
def goal_progress(goal_id: int, user: CurrentUser, db: DbSession) -> GoalProgress:
    """A goal's value over time against its plan, the projection to the target, and drift."""
    return service.goal_progress(db, user, owned_goal(db, user, goal_id))
