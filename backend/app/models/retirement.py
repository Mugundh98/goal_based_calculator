from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.goal import Percent
from app.models.mixins import TimestampMixin
from app.models.profile import Money

if TYPE_CHECKING:
    from app.models.goal import Goal
    from app.models.user import User


class RetirementPlan(TimestampMixin, Base):
    """The retirement-only inputs. The savings phase is the linked `retirement` goal.

    Savings, SIP, step-up, inflation and the pre-retirement return are stored once, on the goal,
    so the Goals page, the Phase 5 simulation and later recommendations see retirement like any
    other goal. The goal's target (corpus in today's money) and year are kept in sync by the
    retirement service (ADR-009).
    """

    __tablename__ = "retirement_plans"
    __table_args__ = (
        CheckConstraint(
            "retirement_age BETWEEN 30 AND 80", name="ck_retirement_plans_retirement_age"
        ),
        CheckConstraint(
            "life_expectancy > retirement_age AND life_expectancy <= 105",
            name="ck_retirement_plans_life_expectancy",
        ),
        CheckConstraint("monthly_expense > 0", name="ck_retirement_plans_monthly_expense"),
        CheckConstraint(
            "post_retirement_return BETWEEN 0 AND 30", name="ck_retirement_plans_post_return"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Both UNIQUE: one plan per user, and each plan owns exactly one goal (one-to-one twice).
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), unique=True)
    retirement_age: Mapped[int] = mapped_column(SmallInteger)
    life_expectancy: Mapped[int] = mapped_column(SmallInteger)  # plan until this age
    monthly_expense: Mapped[Decimal] = mapped_column(Money)  # spending in retirement, today's ₹
    post_retirement_return: Mapped[Decimal] = mapped_column(Percent, server_default="8")

    user: Mapped["User"] = relationship(back_populates="retirement_plan")
    goal: Mapped["Goal"] = relationship(back_populates="retirement_plan")
