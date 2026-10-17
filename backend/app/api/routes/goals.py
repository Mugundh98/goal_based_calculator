from fastapi import APIRouter, HTTPException, status

from app.api.deps import Audit, CurrentUser, DbSession
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


def _summary(goal: Goal) -> dict[str, object]:
    return {"name": goal.name, "goal_type": goal.goal_type, "target_year": goal.target_year}


@router.get("", response_model=list[GoalRead])
def list_goals(user: CurrentUser, db: DbSession) -> list[GoalRead]:
    """The user's goals with projections, highest priority first."""
    category = service.risk_category(db, user)
    return [service.to_read(goal, category) for goal in service.list_goals(db, user)]


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalInput, user: CurrentUser, db: DbSession, audit: Audit) -> GoalRead:
    goal = service.create_goal(db, user, data)
    audit("goal.create", user, entity_type="goal", entity_id=goal.id, details=_summary(goal))
    return service.to_read(goal, service.risk_category(db, user))


@router.post("/calculate", response_model=GoalProjectionOut)
def calculate(data: GoalCalculationInput, user: CurrentUser, db: DbSession) -> GoalProjectionOut:
    """Project a goal without saving it - powers the live preview in the goal form."""
    return service.calculate(data, service.risk_category(db, user))


@router.get("/{goal_id}", response_model=GoalRead)
def read_goal(goal_id: int, user: CurrentUser, db: DbSession) -> GoalRead:
    return service.to_read(owned_goal(db, user, goal_id), service.risk_category(db, user))


@router.put("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int, data: GoalInput, user: CurrentUser, db: DbSession, audit: Audit
) -> GoalRead:
    """Replace every field of a goal. The retirement goal is edited in the planner instead."""
    goal = owned_goal(db, user, goal_id)
    if goal.retirement_plan is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This goal is managed by the retirement planner; edit it there",
        )
    goal = service.update_goal(db, goal, data)
    audit("goal.update", user, entity_type="goal", entity_id=goal.id, details=_summary(goal))
    return service.to_read(goal, service.risk_category(db, user))


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, user: CurrentUser, db: DbSession, audit: Audit) -> None:
    goal = owned_goal(db, user, goal_id)
    summary = _summary(goal)
    service.delete_goal(db, goal)
    audit("goal.delete", user, entity_type="goal", entity_id=goal_id, details=summary)
