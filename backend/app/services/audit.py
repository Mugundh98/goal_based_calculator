"""The audit log: recording key actions and reading them back for administrators.

Routes record an action after it has succeeded (the `Audit` dependency in api/deps.py), so the
log lists what actually happened; failed logins are recorded too, because they matter for
security. Rows are never changed or deleted (a database trigger enforces it).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, User

# Every action the application records, with a description for the admin dashboard.
ACTIONS: dict[str, str] = {
    "auth.register": "Account created",
    "auth.login": "Logged in",
    "auth.login_failed": "Failed login",
    "auth.name.change": "Name changed",
    "auth.password.change": "Password changed",
    "auth.security_question.set": "Security question set",
    "auth.password_reset": "Password reset with the security question",
    "auth.password_reset_failed": "Wrong answer to the security question",
    "profile.save": "Financial profile saved",
    "risk.assess": "Risk questionnaire completed",
    "goal.create": "Goal created",
    "goal.update": "Goal changed",
    "goal.delete": "Goal deleted",
    "retirement.save": "Retirement plan saved",
    "retirement.delete": "Retirement plan deleted",
    "simulation.save": "Simulation saved",
    "simulation.delete": "Saved simulation deleted",
    "recommendation.create": "Recommendation made",
    "portfolio.transaction.create": "Transaction recorded",
    "portfolio.sip.create": "SIP instalments recorded",
    "portfolio.transaction.update": "Transaction corrected",
    "portfolio.transaction.delete": "Transaction deleted",
    "portfolio.fund.create": "Own fund added",
    "assistant.goal.create": "Goal created by the assistant",
    "report.download": "Plan report downloaded",
    "admin.user.update": "User changed by an administrator",
    "admin.job.run": "Data job started",
    "admin.model.activate": "Model version activated",
    "cli.role.change": "Role changed from the command line",
}


def record(
    db: Session,
    action: str,
    *,
    actor: User | None = None,
    actor_email: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Add an audit row to the session (the caller commits)."""
    if action not in ACTIONS:
        raise ValueError(f"Unknown audit action {action!r}")  # a typo would hide events
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


class Auditor:
    """Records actions for one request, with the client's IP address."""

    def __init__(self, db: Session, ip_address: str | None) -> None:
        self.db = db
        self.ip_address = ip_address

    def __call__(
        self,
        action: str,
        actor: User | None = None,
        *,
        actor_email: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        record(
            self.db,
            action,
            actor=actor,
            actor_email=actor_email,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=self.ip_address,
        )
        self.db.commit()


@dataclass(frozen=True)
class AuditPage:
    items: list[AuditLog]
    total: int


def entries(
    db: Session,
    *,
    action: str | None = None,
    actor_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> AuditPage:
    """Newest first, optionally for one action (or prefix such as "goal.") or one actor."""
    query = select(AuditLog)
    if action:
        query = query.where(
            AuditLog.action.startswith(action)
            if action.endswith(".")
            else AuditLog.action == action
        )
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(AuditLog.id.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return AuditPage(list(items), total)


def last_logins(db: Session, user_ids: list[int]) -> dict[int, datetime]:
    """When each user last logged in, from the audit log."""
    if not user_ids:
        return {}
    rows = db.execute(
        select(AuditLog.actor_id, func.max(AuditLog.created_at))
        .where(AuditLog.action == "auth.login", AuditLog.actor_id.in_(user_ids))
        .group_by(AuditLog.actor_id)
    ).all()
    return {actor_id: when for actor_id, when in rows}
