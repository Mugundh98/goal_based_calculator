from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.finance.risk_profile import age_on

EmploymentType = Literal["salaried", "self_employed", "business_owner", "retired", "other"]

# Rupee amounts: non-negative, at most 2 decimal places, below ₹1,000 crore.
MoneyIn = Annotated[Decimal, Field(ge=0, lt=Decimal("1e10"), decimal_places=2)]


class ProfileInput(BaseModel):
    date_of_birth: date
    employment_type: EmploymentType
    monthly_income: MoneyIn
    monthly_expenses: MoneyIn
    monthly_emi: MoneyIn = Decimal(0)
    current_savings: MoneyIn = Decimal(0)
    existing_investments: MoneyIn = Decimal(0)
    dependents: int = Field(default=0, ge=0, le=20)

    @field_validator("date_of_birth")
    @classmethod
    def adult_and_plausible(cls, value: date) -> date:
        age = age_on(value, date.today())
        if age < 18:
            raise ValueError("You must be at least 18 years old")
        if age > 100:
            raise ValueError("Please check the date of birth")
        return value


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date_of_birth: date
    employment_type: EmploymentType
    # Stored as exact NUMERIC; sent as JSON numbers for the UI.
    monthly_income: float
    monthly_expenses: float
    monthly_emi: float
    current_savings: float
    existing_investments: float
    dependents: int

    @computed_field
    @property
    def age(self) -> int:
        return age_on(self.date_of_birth, date.today())

    @computed_field
    @property
    def monthly_surplus(self) -> float:
        """Money left each month after expenses and EMIs - what can be invested."""
        return round(self.monthly_income - self.monthly_expenses - self.monthly_emi, 2)
