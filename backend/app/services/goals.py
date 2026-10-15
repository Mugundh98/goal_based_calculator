"""Goal CRUD plus projections. Projections are computed on every read, never stored."""

from dataclasses import asdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance.goal_plan import GoalInputs, project_goal, suggested_return
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import GoalCalculationInput, GoalInput, GoalProjectionOut, GoalRead
from app.services.risk import latest_assessment

PERCENT = 100


def risk_category(db: Session, user: User) -> str | None:
    assessment = latest_assessment(db, user)
    return assessment.category if assessment else None


def calculate(
    data: GoalCalculationInput | Goal, category: str | None, today: date | None = None
) -> GoalProjectionOut:
    """Project a goal (saved or not yet saved) from its inputs."""
    years = data.target_year - (today or date.today()).year
    if data.expected_return is None:
        annual_return, source = suggested_return(category, years)
    else:
        annual_return, source = float(data.expected_return) / PERCENT, "custom"

    projection = project_goal(
        GoalInputs(
            target_today=float(data.target_amount),
            years=years,
            inflation_rate=float(data.inflation_rate) / PERCENT,
            expected_return=annual_return,
            current_savings=float(data.current_savings),
            monthly_sip=float(data.monthly_sip),
            step_up_rate=float(data.step_up_rate) / PERCENT,
        )
    )
    fields = asdict(projection)
    fields["real_return"] = round(projection.real_return * PERCENT, 2)
    return GoalProjectionOut(
        **fields,
        expected_return_used=round(annual_return * PERCENT, 2),
        expected_return_source=source,
    )


def to_read(goal: Goal, category: str | None) -> GoalRead:
    stored = {name: getattr(goal, name) for name in GoalRead.model_fields.keys() - {"projection"}}
    return GoalRead(**stored, projection=calculate(goal, category))


def list_goals(db: Session, user: User) -> list[Goal]:
    """Highest priority first, then nearest target year."""
    query = (
        select(Goal)
        .where(Goal.user_id == user.id)
        .order_by(Goal.priority, Goal.target_year, Goal.id)
    )
    return list(db.scalars(query))


def get_goal(db: Session, user: User, goal_id: int) -> Goal | None:
    """None both when the goal does not exist and when it belongs to someone else."""
    return db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))


def create_goal(db: Session, user: User, data: GoalInput) -> Goal:
    goal = Goal(user_id=user.id, **data.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def update_goal(db: Session, goal: Goal, data: GoalInput) -> Goal:
    for field, value in data.model_dump().items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: Session, goal: Goal) -> None:
    db.delete(goal)
    db.commit()
