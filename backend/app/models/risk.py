from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class RiskAssessment(Base):
    """One completed questionnaire. Rows are never updated: each attempt is a snapshot."""

    __tablename__ = "risk_assessments"
    __table_args__ = (
        CheckConstraint(
            "category IN ('conservative', 'moderate', 'aggressive')",
            name="ck_risk_assessments_category",
        ),
        CheckConstraint(
            "tolerance_score BETWEEN 0 AND 100 AND capacity_score BETWEEN 0 AND 100 "
            "AND final_score BETWEEN 0 AND 100",
            name="ck_risk_assessments_scores",
        ),
        # "Latest assessment for a user" = WHERE user_id = ? ORDER BY created_at DESC LIMIT 1.
        Index("ix_risk_assessments_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    questionnaire_version: Mapped[str] = mapped_column(String(10))
    answers: Mapped[dict[str, str]] = mapped_column(JSONB)  # {question_id: option_id}
    tolerance_score: Mapped[int] = mapped_column(SmallInteger)
    capacity_score: Mapped[int] = mapped_column(SmallInteger)
    final_score: Mapped[int] = mapped_column(SmallInteger)
    category: Mapped[str] = mapped_column(String(20))
    # Factor-by-factor capacity scoring, frozen at assessment time (the profile may change later).
    capacity_breakdown: Mapped[list[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="risk_assessments")
