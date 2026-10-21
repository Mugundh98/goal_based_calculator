"""Administration: system overview, user management, model versions."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ml import registry
from app.models import (
    AuditLog,
    ChatMessage,
    Fund,
    Goal,
    JobRun,
    MLModel,
    Recommendation,
    Simulation,
    ToolCall,
    Transaction,
    User,
)
from app.schemas.admin import (
    ActiveModel,
    ActivityCounts,
    AdminOverview,
    AdminUserPage,
    AdminUserRow,
    AdminUserUpdate,
    AssistantStats,
    AuditEntryOut,
    JobStatus,
    ModelVersionOut,
    ToolUsage,
    UserCounts,
)
from app.services import audit
from app.services.funds import newest_nav_date


class AdminError(ValueError):
    """A change that is not allowed (409)."""


def _count(db: Session, model: type, *conditions: Any) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def overview(db: Session, now: datetime | None = None) -> AdminOverview:
    now = now or datetime.now(UTC)
    week = now - timedelta(days=7)
    latest_runs = (
        select(JobRun).distinct(JobRun.job_name).order_by(JobRun.job_name, JobRun.started_at.desc())
    )
    tools = db.execute(
        select(
            ToolCall.tool,
            func.count(),
            func.count().filter(ToolCall.status == "error"),
            func.avg(ToolCall.latency_ms),
        )
        .where(ToolCall.created_at >= week)
        .group_by(ToolCall.tool)
        .order_by(func.count().desc())
    ).all()
    answers = ChatMessage.role == "assistant"
    recent = ChatMessage.created_at >= week
    return AdminOverview(
        users=UserCounts(
            total=_count(db, User),
            active=_count(db, User, User.is_active),
            admins=_count(db, User, User.role == "admin"),
            new_last_7_days=_count(db, User, User.created_at >= week),
        ),
        activity=ActivityCounts(
            goals=_count(db, Goal),
            transactions=_count(db, Transaction),
            saved_simulations=_count(db, Simulation),
            recommendations=_count(db, Recommendation),
            logins_7_days=_count(
                db, AuditLog, AuditLog.action == "auth.login", AuditLog.created_at >= week
            ),
            failed_logins_7_days=_count(
                db, AuditLog, AuditLog.action == "auth.login_failed", AuditLog.created_at >= week
            ),
        ),  # fmt: skip
        funds=_count(db, Fund, Fund.owner_user_id.is_(None)),
        latest_nav_date=newest_nav_date(db),
        jobs=[
            JobStatus(
                job_name=r.job_name,
                status=r.status,
                started_at=r.started_at,
                finished_at=r.finished_at,
                rows_written=r.rows_written,
            )
            for r in db.scalars(latest_runs)
        ],
        models=[
            ActiveModel(name=m.name, version=m.version, trained_at=m.trained_at)
            for m in db.scalars(select(MLModel).where(MLModel.is_active).order_by(MLModel.name))
        ],
        assistant=AssistantStats(
            questions_7_days=_count(db, ChatMessage, ChatMessage.role == "user", recent),
            answers_7_days=_count(db, ChatMessage, answers, recent),
            fallback_answers_7_days=_count(
                db, ChatMessage, answers, recent, ChatMessage.payload["error"].isnot(None)
            ),
            answers_with_ungrounded_numbers_7_days=_count(
                db,
                ChatMessage,
                answers,
                recent,
                # NULL when the key is missing, so only answers with a non-empty list count.
                func.jsonb_array_length(ChatMessage.payload["ungrounded"]) > 0,
            ),
            tools=[
                ToolUsage(tool=t, calls=c, errors=e, average_ms=round(float(a or 0), 1))
                for t, c, e, a in tools
            ],
        ),
    )


def _rows(db: Session, users: list[User]) -> list[AdminUserRow]:
    ids = [u.id for u in users]
    logins = audit.last_logins(db, ids)
    goals = dict(
        db.execute(
            select(Goal.user_id, func.count()).where(Goal.user_id.in_(ids)).group_by(Goal.user_id)
        ).all()
    )
    return [
        AdminUserRow(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_login=logins.get(u.id),
            goals=goals.get(u.id, 0),
        )
        for u in users
    ]


def users(db: Session, q: str | None = None, page: int = 1, page_size: int = 25) -> AdminUserPage:
    query = select(User)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(User.email.like(pattern), func.lower(User.full_name).like(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    found = db.scalars(
        query.order_by(User.created_at.desc(), User.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return AdminUserPage(items=_rows(db, list(found)), total=total, page=page, page_size=page_size)


def update_user(
    db: Session, admin: User, user: User, change: AdminUserUpdate
) -> tuple[AdminUserRow, dict[str, Any]]:
    """Change a user's role or active flag; returns the row and what changed (for the audit)."""
    if user.id == admin.id:
        # Otherwise the last admin could lock everyone out of administration.
        raise AdminError("You cannot change your own role or deactivate yourself")
    changes: dict[str, Any] = {}
    if change.role is not None and change.role != user.role:
        changes["role"] = {"from": user.role, "to": change.role}
        user.role = change.role
    if change.is_active is not None and change.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": change.is_active}
        user.is_active = change.is_active
    db.commit()
    db.refresh(user)
    return _rows(db, [user])[0], changes


def audit_entry(entry: AuditLog) -> AuditEntryOut:
    return AuditEntryOut(
        id=entry.id,
        created_at=entry.created_at,
        actor_id=entry.actor_id,
        actor_email=entry.actor_email,
        action=entry.action,
        description=audit.ACTIONS.get(entry.action, entry.action),
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        details=entry.details,
        ip_address=entry.ip_address,
    )


def _headline(metrics: dict[str, Any]) -> dict[str, Any]:
    """The plain numbers among a model's stored metrics, plus each model's key validation
    result (lists and tables left out)."""
    flat = {k: v for k, v in metrics.items() if isinstance(v, int | float | str)}
    pooled = (metrics.get("reported_years") or {}).get("pooled", {})  # fund ranker, 2021-2025
    if "model" in pooled:
        flat["rank_ic"] = pooled["model"].get("rank_ic")
        flat["top_pick_hit_rate"] = pooled["model"].get("top_pick_hit_rate")
        if "momentum" in pooled:
            flat["momentum_rank_ic"] = pooled["momentum"].get("rank_ic")
    errors = (metrics.get("evaluation") or {}).get("mae_12m_ahead", {})  # inflation forecast
    flat |= {f"mae_12m_{name}": value for name, value in errors.items()}
    evaluation = metrics.get("evaluation")
    if isinstance(evaluation, dict):
        flat |= {k: v for k, v in evaluation.items() if isinstance(v, int | float)}
    return flat


def model_versions(db: Session) -> list[ModelVersionOut]:
    return [
        ModelVersionOut(
            id=m.id,
            name=m.name,
            version=m.version,
            algorithm=m.algorithm,
            data_start=m.data_start,
            data_end=m.data_end,
            trained_at=m.trained_at,
            is_active=m.is_active,
            headline=_headline(m.metrics),
        )
        for m in db.scalars(select(MLModel).order_by(MLModel.name, MLModel.version.desc()))
    ]


def activate(db: Session, model: MLModel) -> None:
    registry.activate_model(db, model)
    db.commit()
