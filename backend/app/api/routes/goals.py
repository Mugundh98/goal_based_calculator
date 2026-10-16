from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import GoalCalculationInput, GoalInput, GoalProjectionOut, GoalRead
from app.services import goals as service

router = APIRouter(prefix="/goals", tags=["goals"])


def owned_goal(db: DbSession, user: User, goal_id: int) -> Goal:
    goal = service.get_goal(db, user, goal_id)
    if goal is None:
        # 404, not 403, for other users' goals: do not reveal that the id exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.get("", response_model=list[GoalRead])
def list_goals(user: CurrentUser, db: DbSession) -> list[GoalRead]:
    """The user's goals with projections, highest priority first."""
    category = service.risk_category(db, user)
    return [service.to_read(goal, category) for goal in service.list_goals(db, user)]


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalInput, user: CurrentUser, db: DbSession) -> GoalRead:
    goal = service.create_goal(db, user, data)
    return service.to_read(goal, service.risk_category(db, user))


@router.post("/calculate", response_model=GoalProjectionOut)
def calculate(data: GoalCalculationInput, user: CurrentUser, db: DbSession) -> GoalProjectionOut:
    """Project a goal without saving it - powers the live preview in the goal form."""
    return service.calculate(data, service.risk_category(db, user))


@router.get("/{goal_id}", response_model=GoalRead)
def read_goal(goal_id: int, user: CurrentUser, db: DbSession) -> GoalRead:
    return service.to_read(owned_goal(db, user, goal_id), service.risk_category(db, user))


@router.put("/{goal_id}", response_model=GoalRead)
def update_goal(goal_id: int, data: GoalInput, user: CurrentUser, db: DbSession) -> GoalRead:
    """Replace every field of a goal. The retirement goal is edited in the planner instead."""
    goal = owned_goal(db, user, goal_id)
    if goal.retirement_plan is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This goal is managed by the retirement planner; edit it there",
        )
    goal = service.update_goal(db, goal, data)
    return service.to_read(goal, service.risk_category(db, user))


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, user: CurrentUser, db: DbSession) -> None:
    service.delete_goal(db, owned_goal(db, user, goal_id))
