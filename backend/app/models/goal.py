from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin
from app.models.profile import Money

if TYPE_CHECKING:
    from app.models.user import User

GOAL_TYPES = (
    "retirement",
    "education",
    "house",
    "car",
    "marriage",
    "travel",
    "emergency_fund",
    "wealth",
    "other",
)

# NUMERIC(5, 2): a percentage such as 6.00 or 12.50 - exact, like money.
Percent = Numeric(5, 2)


class Goal(TimestampMixin, Base):
    """A financial goal. Only the user's inputs are stored; projections are always recomputed."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint(
            "goal_type IN ('retirement', 'education', 'house', 'car', 'marriage', 'travel', "
            "'emergency_fund', 'wealth', 'other')",
            name="ck_goals_goal_type",
        ),
        CheckConstraint("priority BETWEEN 1 AND 3", name="ck_goals_priority"),
        CheckConstraint(
            "target_amount > 0 AND current_savings >= 0 AND monthly_sip >= 0",
            name="ck_goals_amounts",
        ),
        CheckConstraint(
            "inflation_rate BETWEEN 0 AND 20 AND step_up_rate BETWEEN 0 AND 50 "
            "AND (expected_return IS NULL OR expected_return BETWEEN 0 AND 30)",
            name="ck_goals_rates",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # One-to-many: a user has many goals. Indexed because every query filters on it.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[Decimal] = mapped_column(Money)  # in TODAY's rupees
    target_year: Mapped[int] = mapped_column(SmallInteger)
    priority: Mapped[int] = mapped_column(SmallInteger, server_default="2")  # 1 high .. 3 low
    inflation_rate: Mapped[Decimal] = mapped_column(Percent, server_default="6")  # % a year
    # NULL = "automatic": derived from the latest risk profile each time the goal is read.
    expected_return: Mapped[Decimal | None] = mapped_column(Percent)  # % a year
    current_savings: Mapped[Decimal] = mapped_column(Money, server_default="0")
    monthly_sip: Mapped[Decimal] = mapped_column(Money, server_default="0")
    step_up_rate: Mapped[Decimal] = mapped_column(Percent, server_default="0")  # % a year

    user: Mapped["User"] = relationship(back_populates="goals")
