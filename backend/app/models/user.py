from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.goal import Goal
    from app.models.profile import FinancialProfile
    from app.models.risk import RiskAssessment


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # One-to-one: each user has at most one financial profile.
    profile: Mapped["FinancialProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    # One-to-many: every questionnaire attempt is kept as history; a user has many goals.
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    goals: Mapped[list["Goal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
