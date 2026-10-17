from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_SIP_MONTHS = 360


class TransactionCreate(BaseModel):
    fund_id: int
    goal_id: int | None = None  # None = not assigned to a goal
    txn_type: Literal["buy", "sell"]
    txn_date: date
    # A purchase needs the amount; units are optional (from a statement, otherwise worked out
    # from the NAV). A redemption needs the amount or the units.
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    units: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=4)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _amount_or_units(self) -> "TransactionCreate":
        if self.txn_type == "buy" and self.amount is None:
            raise ValueError("A purchase needs the amount invested")
        if self.amount is None and self.units is None:
            raise ValueError("Give the amount or the units redeemed")
        return self


class SipCreate(BaseModel):
    """Monthly purchases of the same amount on the same day of the month."""

    fund_id: int
    goal_id: int | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    start_date: date
    end_date: date | None = None  # default: today

    @model_validator(mode="after")
    def _period(self) -> "SipCreate":
        end = self.end_date or date.today()
        if self.start_date > end:
            raise ValueError("The SIP must start before it ends")
        months = (end.year - self.start_date.year) * 12 + end.month - self.start_date.month
        if months >= MAX_SIP_MONTHS:
            raise ValueError("At most 30 years of instalments at a time")
        return self


class TransactionRead(BaseModel):
    id: int
    fund_id: int
    fund_name: str
    goal_id: int | None
    goal_name: str | None
    txn_type: str
    txn_date: date
    amount: float
    units: float
    nav: float
    note: str | None
    created_at: datetime


class HoldingRead(BaseModel):
    id: int
    goal_id: int | None
    goal_name: str | None
    fund_id: int
    fund_name: str
    amc: str
    category: str
    plan: str  # direct / regular: names repeat across plans and options
    option: str
    sleeve: str
    sleeve_label: str
    units: float
    avg_cost: float | None  # cost per unit held
    cost: float
    nav: float | None
    nav_date: date | None
    value: float
    gain: float
    gain_percent: float | None
    realised_gain: float
    xirr: float | None  # percent a year; None under a year or without a rate
    first_date: date


class PortfolioTotals(BaseModel):
    cost: float
    value: float
    gain: float
    gain_percent: float | None
    realised_gain: float
    xirr: float | None
    as_of: date | None  # newest NAV date used


class GoalStatus(BaseModel):
    goal_id: int
    name: str
    goal_type: str
    target_year: int
    years_to_goal: int
    status: Literal["on_track", "off_track", "not_started"]
    value: float
    cost: float
    gain: float
    xirr: float | None
    expected_return: float  # percent a year the goal's plan assumes
    plan_value: float  # the money put in, grown at the plan's return
    vs_plan: float  # value - plan_value
    monthly_sip: float
    inflated_target: float
    projected_value: float
    funded_percent: float
    shortfall: float
    required_sip: float | None
    rebalance_needed: bool | None  # None: no recommendation to compare with
    equity_actual: float | None  # percent
    equity_target: float | None  # percent


class Alert(BaseModel):
    kind: Literal["rebalance", "off_track", "stale_recommendation", "no_recommendation"]
    severity: Literal["warning", "info"]
    goal_id: int
    goal_name: str
    message: str


class PortfolioRead(BaseModel):
    totals: PortfolioTotals
    holdings: list[HoldingRead]
    goals: list[GoalStatus]
    alerts: list[Alert]


class HistoryPoint(BaseModel):
    date: date
    invested: float  # net money put in so far
    value: float
    plan: float


class ValuePoint(BaseModel):
    date: date
    value: float


class DriftRowOut(BaseModel):
    row: str
    label: str
    value: float
    actual: float  # percent
    target: float  # percent
    drift: float  # percentage points
    trade: float  # rupees to buy (+) or sell (-)


class RebalanceOut(BaseModel):
    rows: list[DriftRowOut]
    equity_actual: float
    equity_target: float
    equity_drift: float
    needed: bool
    threshold: float  # percentage points
    recommendation_id: int
    recommended_at: datetime


class GoalProgress(BaseModel):
    status: GoalStatus
    history: list[HistoryPoint]
    projection: list[ValuePoint]  # from today to the target year, with the current SIP
    target: ValuePoint  # the inflated target in the target year
    rebalance: RebalanceOut | None
    holdings: list[HoldingRead]
