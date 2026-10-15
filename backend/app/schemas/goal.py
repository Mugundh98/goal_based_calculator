from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.finance.goal_plan import ReturnSource
from app.schemas.profile import MoneyIn

GoalType = Literal[
    "retirement",
    "education",
    "house",
    "car",
    "marriage",
    "travel",
    "emergency_fund",
    "wealth",
    "other",
]

MAX_HORIZON_YEARS = 60


def PercentIn(maximum: int):  # noqa: N802 - reads like a type in the field definitions
    """A percentage such as 6 or 12.5 (not a fraction), at most 2 decimal places."""
    return Annotated[Decimal, Field(ge=0, le=maximum, decimal_places=2)]


class GoalCalculationInput(BaseModel):
    """The numbers needed to project a goal. Also used for the live preview while typing."""

    target_amount: Annotated[Decimal, Field(gt=0, lt=Decimal("1e10"), decimal_places=2)]
    target_year: int
    inflation_rate: PercentIn(20) = Decimal(6)
    # None = automatic, taken from the latest risk profile and the time horizon.
    expected_return: PercentIn(30) | None = None
    current_savings: MoneyIn = Decimal(0)
    monthly_sip: MoneyIn = Decimal(0)
    step_up_rate: PercentIn(50) = Decimal(0)

    @field_validator("target_year")
    @classmethod
    def in_the_future(cls, value: int) -> int:
        this_year = date.today().year
        if value <= this_year:
            raise ValueError("Target year must be after this year")
        if value > this_year + MAX_HORIZON_YEARS:
            raise ValueError(f"Target year must be within {MAX_HORIZON_YEARS} years")
        return value


class GoalInput(GoalCalculationInput):
    goal_type: GoalType
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    priority: int = Field(default=2, ge=1, le=3)  # 1 high, 2 medium, 3 low


class GoalProjectionOut(BaseModel):
    years_to_goal: int
    expected_return_used: float  # percent
    expected_return_source: ReturnSource
    inflated_target: float
    savings_value: float
    sip_value: float
    projected_value: float
    shortfall: float
    required_sip: float | None
    funded_percent: float
    on_track: bool
    real_return: float  # percent


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_type: GoalType
    name: str
    priority: int
    # Stored as exact NUMERIC; sent as JSON numbers for the UI.
    target_amount: float
    target_year: int
    inflation_rate: float
    expected_return: float | None
    current_savings: float
    monthly_sip: float
    step_up_rate: float
    created_at: datetime
    updated_at: datetime
    projection: GoalProjectionOut
