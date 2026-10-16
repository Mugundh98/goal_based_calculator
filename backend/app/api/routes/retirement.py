from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.finance.tvm import FinanceInputError
from app.models.retirement import RetirementPlan
from app.models.user import User
from app.schemas.retirement import (
    RetirementInput,
    RetirementPlanRead,
    RetirementProjectionOut,
    RetirementSimulationOut,
    RetirementSimulationRequest,
)
from app.services import retirement as service
from app.services.risk import ProfileRequiredError
from app.services.simulations import SimulationUnavailable

router = APIRouter(prefix="/retirement", tags=["retirement"])

PROFILE_FIRST = "Complete your financial profile first: your age comes from it"


def _errors(error: Exception) -> HTTPException:
    if isinstance(error, ProfileRequiredError):
        return HTTPException(status.HTTP_409_CONFLICT, detail=PROFILE_FIRST)
    if isinstance(error, SimulationUnavailable):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    # Valid on their own, but not for this user's age.
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


HANDLED = (
    ProfileRequiredError,
    SimulationUnavailable,
    service.RetirementInputError,
    FinanceInputError,
)


def owned_plan(db: DbSession, user: User) -> RetirementPlan:
    plan = service.get_plan(db, user)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No retirement plan yet")
    return plan


@router.get("", response_model=RetirementPlanRead)
def read_plan(user: CurrentUser, db: DbSession) -> RetirementPlanRead:
    """The saved plan with its projection. 404 until it has been saved once."""
    plan = owned_plan(db, user)
    try:
        return service.to_read(db, user, plan)
    except HANDLED as error:
        raise _errors(error) from None


@router.put("", response_model=RetirementPlanRead)
def save_plan(data: RetirementInput, user: CurrentUser, db: DbSession) -> RetirementPlanRead:
    """Create or replace the plan (idempotent). Also creates/updates its `retirement` goal."""
    try:
        plan = service.save_plan(db, user, data)
        return service.to_read(db, user, plan)
    except HANDLED as error:
        raise _errors(error) from None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(user: CurrentUser, db: DbSession) -> None:
    """Delete the plan and its goal."""
    service.delete_plan(db, owned_plan(db, user))


@router.post("/calculate", response_model=RetirementProjectionOut)
def calculate(data: RetirementInput, user: CurrentUser, db: DbSession) -> RetirementProjectionOut:
    """Single-return projection without saving: the wizard's live preview."""
    try:
        return service.calculate(db, user, data)
    except HANDLED as error:
        raise _errors(error) from None


@router.post("/simulate", response_model=RetirementSimulationOut)
def simulate(
    request: RetirementSimulationRequest, user: CurrentUser, db: DbSession
) -> RetirementSimulationOut:
    """Monte Carlo over the whole lifetime: the chance the money lasts. Nothing is saved."""
    try:
        return service.simulate(db, user, request)
    except HANDLED as error:
        raise _errors(error) from None
