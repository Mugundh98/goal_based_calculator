"""Administration endpoints. Every route requires role = admin (403 otherwise)."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminUser, Audit, DbSession
from app.models import MLModel, User
from app.schemas.admin import (
    AdminOverview,
    AdminUserPage,
    AdminUserRow,
    AdminUserUpdate,
    AuditPageOut,
    ModelVersionOut,
)
from app.services import admin as service
from app.services import audit as audit_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverview)
def overview(_: AdminUser, db: DbSession) -> AdminOverview:
    """Users, activity, data freshness, pipeline jobs, active models and assistant usage."""
    return service.overview(db)


@router.get("/users", response_model=AdminUserPage)
def users(
    _: AdminUser,
    db: DbSession,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> AdminUserPage:
    """Search by e-mail or name, newest accounts first."""
    return service.users(db, q, page, page_size)


@router.patch("/users/{user_id}", response_model=AdminUserRow)
def update_user(
    user_id: int, change: AdminUserUpdate, admin: AdminUser, db: DbSession, audit: Audit
) -> AdminUserRow:
    """Make a user an admin (or not), or deactivate / reactivate the account."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        row, changes = service.update_user(db, admin, user, change)
    except service.AdminError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    if changes:
        audit(
            "admin.user.update",
            admin,
            entity_type="user",
            entity_id=user.id,
            details={"email": user.email, **changes},
        )
    return row


@router.get("/audit", response_model=AuditPageOut)
def audit_log(
    _: AdminUser,
    db: DbSession,
    action: str | None = Query(default=None, max_length=60, description='e.g. "goal." for all'),
    actor_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> AuditPageOut:
    """The audit log, newest first."""
    found = audit_service.entries(
        db, action=action, actor_id=actor_id, page=page, page_size=page_size
    )
    return AuditPageOut(
        items=[service.audit_entry(e) for e in found.items],
        total=found.total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit/actions", response_model=dict[str, str])
def audit_actions(_: AdminUser) -> dict[str, str]:
    """Every action the application records, with its description (for filters)."""
    return audit_service.ACTIONS


@router.get("/models", response_model=list[ModelVersionOut])
def models(_: AdminUser, db: DbSession) -> list[ModelVersionOut]:
    """Every trained ML model version, newest first within each model."""
    return service.model_versions(db)


@router.post("/models/{model_id}/activate", response_model=list[ModelVersionOut])
def activate_model(model_id: int, admin: AdminUser, db: DbSession, audit: Audit) -> list:
    """Make this version the one the app uses (for instance, roll back a bad retraining).
    Run the `ml_score` job afterwards to refresh the fund predictions."""
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Model version not found")
    service.activate(db, model)
    audit(
        "admin.model.activate",
        admin,
        entity_type="ml_model",
        entity_id=model.id,
        details={"name": model.name, "version": model.version},
    )
    return service.model_versions(db)
