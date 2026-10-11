from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

EMPLOYMENT_TYPES = ("salaried", "self_employed", "business_owner", "retired", "other")

# NUMERIC(14, 2): exact decimal money, up to 999,999,999,999.99. Never float for money.
Money = Numeric(14, 2)


class FinancialProfile(TimestampMixin, Base):
    __tablename__ = "financial_profiles"
    __table_args__ = (
        CheckConstraint(
            "employment_type IN "
            "('salaried', 'self_employed', 'business_owner', 'retired', 'other')",
            name="ck_financial_profiles_employment_type",
        ),
        CheckConstraint(
            "monthly_income >= 0 AND monthly_expenses >= 0 AND monthly_emi >= 0 "
            "AND current_savings >= 0 AND existing_investments >= 0",
            name="ck_financial_profiles_non_negative",
        ),
        CheckConstraint("dependents BETWEEN 0 AND 20", name="ck_financial_profiles_dependents"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True makes this one-to-one; CASCADE deletes the profile with its user.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    # Date of birth, not age: age changes every year, the birth date never does.
    date_of_birth: Mapped[date] = mapped_column(Date)
    employment_type: Mapped[str] = mapped_column(String(20))
    monthly_income: Mapped[Decimal] = mapped_column(Money)  # take-home
    monthly_expenses: Mapped[Decimal] = mapped_column(Money)  # household spending
    monthly_emi: Mapped[Decimal] = mapped_column(Money, server_default="0")  # loan instalments
    current_savings: Mapped[Decimal] = mapped_column(Money, server_default="0")  # bank + FDs
    existing_investments: Mapped[Decimal] = mapped_column(Money, server_default="0")
    dependents: Mapped[int] = mapped_column(SmallInteger, server_default="0")

    user: Mapped["User"] = relationship(back_populates="profile")
