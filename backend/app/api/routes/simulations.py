from fastapi import APIRouter, HTTPException, status

from app.api.deps import Audit, CurrentUser, DbSession
from app.api.routes.goals import owned_goal
from app.models.simulation import Simulation
from app.models.user import User
from app.schemas.simulation import (
    ComparisonOut,
    ComparisonRequest,
    SimulationRead,
    SimulationRequest,
    SimulationResultOut,
    SimulationSummary,
)
from app.services import simulations as service

router = APIRouter(tags=["simulations"])


def _unavailable(error: service.SimulationUnavailable) -> HTTPException:
    # 409 Conflict: the request is valid, but the goal or the data is not in a state to run it.
    return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))


def owned_simulation(db: DbSession, user: User, simulation_id: int) -> Simulation:
    simulation = service.get_simulation(db, user, simulation_id)
    if simulation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return simulation


@router.post("/goals/{goal_id}/simulate", response_model=SimulationResultOut)
def simulate(
    goal_id: int, request: SimulationRequest, user: CurrentUser, db: DbSession
) -> SimulationResultOut:
    """Run a simulation without saving it - powers the what-if sliders."""
    goal = owned_goal(db, user, goal_id)
    try:
        return service.run_simulation(db, user, goal, request)
    except service.SimulationUnavailable as error:
        raise _unavailable(error) from None


@router.post("/goals/{goal_id}/simulate/compare", response_model=ComparisonOut)
def compare(
    goal_id: int, request: ComparisonRequest, user: CurrentUser, db: DbSession
) -> ComparisonOut:
    """All four return models on the same inputs and random numbers."""
    goal = owned_goal(db, user, goal_id)
    try:
        return service.compare_models(db, user, goal, request)
    except service.SimulationUnavailable as error:
        raise _unavailable(error) from None


@router.post(
    "/goals/{goal_id}/simulations",
    response_model=SimulationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_simulation(
    goal_id: int, request: SimulationRequest, user: CurrentUser, db: DbSession, audit: Audit
) -> SimulationRead:
    """Run a simulation and save it as a snapshot."""
    goal = owned_goal(db, user, goal_id)
    try:
        result = service.run_simulation(db, user, goal, request)
    except service.SimulationUnavailable as error:
        raise _unavailable(error) from None
    saved = service.save_simulation(db, goal, result)
    audit(
        "simulation.save",
        user,
        entity_type="simulation",
        entity_id=saved.id,
        details={"goal_id": goal.id, "model": result.model, "chance": result.success_probability},
    )
    return service.to_read(saved)


@router.get("/goals/{goal_id}/simulations", response_model=list[SimulationSummary])
def list_simulations(goal_id: int, user: CurrentUser, db: DbSession) -> list[SimulationSummary]:
    """Saved runs of a goal, newest first (without the bands)."""
    goal = owned_goal(db, user, goal_id)
    return [service.to_summary(s) for s in service.list_simulations(db, goal)]


@router.get("/simulations/{simulation_id}", response_model=SimulationRead)
def read_simulation(simulation_id: int, user: CurrentUser, db: DbSession) -> SimulationRead:
    return service.to_read(owned_simulation(db, user, simulation_id))


@router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_simulation(simulation_id: int, user: CurrentUser, db: DbSession, audit: Audit) -> None:
    service.delete_simulation(db, owned_simulation(db, user, simulation_id))
    audit("simulation.delete", user, entity_type="simulation", entity_id=simulation_id)
