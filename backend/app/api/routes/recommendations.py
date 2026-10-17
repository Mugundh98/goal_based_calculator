from fastapi import APIRouter, HTTPException, status

from app.api.deps import Audit, CurrentUser, DbSession
from app.api.routes.goals import owned_goal
from app.schemas.recommendation import RecommendationRead, RecommendationSummary
from app.services import recommendations as service

router = APIRouter(prefix="/goals/{goal_id}/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationRead, status_code=status.HTTP_201_CREATED)
def create(goal_id: int, user: CurrentUser, db: DbSession, audit: Audit) -> RecommendationRead:
    """Recommend an allocation and funds for the goal now, and keep it as a snapshot."""
    goal = owned_goal(db, user, goal_id)
    try:
        recommendation = service.recommend(db, user, goal)
    except service.RecommendationUnavailable as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    audit(
        "recommendation.create",
        user,
        entity_type="recommendation",
        entity_id=recommendation.id,
        details={"goal_id": goal.id, "equity_share": round(recommendation.equity_share, 4)},
    )
    return service.to_read(recommendation)


@router.get("", response_model=list[RecommendationSummary])
def history(goal_id: int, user: CurrentUser, db: DbSession) -> list[RecommendationSummary]:
    """Earlier recommendations for the goal, newest first."""
    goal = owned_goal(db, user, goal_id)
    return [service.to_summary(r) for r in service.history_for(db, goal)]


@router.get("/latest", response_model=RecommendationRead)
def latest(goal_id: int, user: CurrentUser, db: DbSession) -> RecommendationRead:
    goal = owned_goal(db, user, goal_id)
    found = service.history_for(db, goal)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No recommendation yet")
    return service.to_read(found[0])


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def read(
    goal_id: int, recommendation_id: int, user: CurrentUser, db: DbSession
) -> RecommendationRead:
    goal = owned_goal(db, user, goal_id)
    found = next((r for r in service.history_for(db, goal) if r.id == recommendation_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    return service.to_read(found)
