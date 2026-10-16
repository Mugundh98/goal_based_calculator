"""Retirement planning: how big a corpus is needed, how to build it, and how long it lasts.

Two phases, with the Phase 3 conventions (ADR-006) in both:

1. Accumulation (today -> retirement): savings and a SIP (annuity due, optional yearly step-up)
   grow at the pre-retirement return. This IS a goal - the target is the corpus - so it reuses
   goal_plan.project_goal.
2. Withdrawal (retirement -> life expectancy): the corpus pays the household's expenses at the
   start of every month. The monthly amount is today's expense grown by inflation to retirement,
   then raised by inflation once a year. The corpus earns the post-retirement return.

Corpus needed = present value, at retirement, of that rising stream of withdrawals
(tvm.present_value_growing_annuity). With exactly that corpus the last withdrawal at life
expectancy empties it. Pure: no database, no HTTP (ADR-009).
"""

import math
from dataclasses import dataclass

from app.finance import tvm
from app.finance.goal_plan import GoalInputs, GoalProjection, project_goal

MONTHS = tvm.MONTHS_PER_YEAR
BENGEN_RATE = 0.04  # the "4% rule" (Bengen, 1994): first-year withdrawal / corpus
BENGEN_YEARS = 30
TOLERANCE = 0.5  # half a rupee, as Phase 3: float rounding never "runs out" of an exact corpus


@dataclass(frozen=True)
class RetirementInputs:
    current_age: int
    retirement_age: int
    life_expectancy: int  # plan until this age (the money must last until then)
    monthly_expense: float  # household spending in retirement, in TODAY's rupees
    inflation_rate: float  # fraction per year, before and after retirement
    pre_retirement_return: float  # fraction per year
    post_retirement_return: float  # fraction per year
    current_savings: float = 0.0  # already set aside for retirement
    monthly_sip: float = 0.0
    step_up_rate: float = 0.0  # yearly SIP increase, fraction

    def __post_init__(self) -> None:
        if self.retirement_age <= self.current_age:
            raise tvm.FinanceInputError("retirement age must be above the current age")
        if self.life_expectancy <= self.retirement_age:
            raise tvm.FinanceInputError("life expectancy must be above the retirement age")

    @property
    def years_to_retirement(self) -> int:
        return self.retirement_age - self.current_age

    @property
    def retirement_years(self) -> int:
        return self.life_expectancy - self.retirement_age


@dataclass(frozen=True)
class LifetimeYear:
    age: int  # age at the END of the year (the first entry is today, the current age)
    year: int  # years from now
    balance: float  # projected balance (0 once the money has run out)
    phase: str  # "accumulation" or "retirement"


@dataclass(frozen=True)
class RetirementProjection:
    first_monthly_withdrawal: float  # first month of retirement, in rupees of that time
    corpus_needed: float  # at retirement
    corpus_multiple: float  # corpus_needed / first year's spending ("x times annual expenses")
    withdrawal_rate: float  # first year's spending / corpus_needed (compare: 4% rule)
    accumulation: GoalProjection  # the savings phase, target = corpus_needed
    money_lasts_until: float | None  # age when the projected corpus runs out (None: it lasts)
    lifetime: list[LifetimeYear]


def first_monthly_withdrawal(plan: RetirementInputs) -> float:
    return tvm.inflate(plan.monthly_expense, plan.inflation_rate, plan.years_to_retirement)


def corpus_needed(plan: RetirementInputs) -> float:
    return tvm.present_value_growing_annuity(
        first_monthly_withdrawal(plan),
        plan.inflation_rate,
        plan.post_retirement_return,
        plan.retirement_years,
    )


def accumulation_goal(plan: RetirementInputs, corpus: float) -> GoalInputs:
    """The savings phase as a Phase 3 goal whose target is the corpus."""
    return GoalInputs(
        target_today=corpus,  # already in rupees of the retirement year ...
        years=plan.years_to_retirement,
        inflation_rate=0.0,  # ... so the goal must not inflate it again
        expected_return=plan.pre_retirement_return,
        current_savings=plan.current_savings,
        monthly_sip=plan.monthly_sip,
        step_up_rate=plan.step_up_rate,
    )


def withdrawal_amount(first_monthly: float, inflation_rate: float, month: int) -> float:
    """Withdrawal at the start of retirement month `month` (0-based): raised once a year."""
    return first_monthly * (1 + inflation_rate) ** (month // MONTHS)


def drawdown(
    corpus: float, first_monthly: float, inflation_rate: float, annual_return: float, years: int
) -> tuple[list[float], float | None]:
    """Balance at the end of each retirement year, and when the money runs out.

    Month by month: take out the withdrawal at the start of the month, grow the rest for a
    month. Returns (year-end balances, years until depletion or None if it lasts). Depletion is
    the month whose withdrawal cannot be paid in full, so 24.5 = in the 7th month of year 25.
    """
    i = tvm.monthly_rate(annual_return)
    balance = corpus
    balances: list[float] = []
    ran_out: float | None = None
    for month in range(years * MONTHS):
        balance -= withdrawal_amount(first_monthly, inflation_rate, month)
        if balance < -TOLERANCE and ran_out is None:
            ran_out = month / MONTHS
        balance = max(balance, 0.0) * (1 + i)
        if month % MONTHS == MONTHS - 1:
            balances.append(balance)
    return balances, ran_out


def plan_retirement(plan: RetirementInputs) -> RetirementProjection:
    first = first_monthly_withdrawal(plan)
    needed = corpus_needed(plan)
    goal = accumulation_goal(plan, needed)
    accumulation = project_goal(goal)

    # Year-by-year path: savings phase (closed-form Phase 3 values), then the drawdown of the
    # corpus the current plan is projected to reach.
    saving = [_value_after(goal, year) for year in range(plan.years_to_retirement + 1)]
    spending, ran_out = drawdown(
        saving[-1],
        first,
        plan.inflation_rate,
        plan.post_retirement_return,
        plan.retirement_years,
    )
    lifetime = [
        LifetimeYear(plan.current_age + year, year, round(value, 2), "accumulation")
        for year, value in enumerate(saving)
    ] + [
        LifetimeYear(
            plan.retirement_age + year,
            plan.years_to_retirement + year,
            round(value, 2),
            "retirement",
        )
        for year, value in enumerate(spending, start=1)
    ]

    annual_spending = first * MONTHS
    return RetirementProjection(
        first_monthly_withdrawal=round(first, 2),
        corpus_needed=round(needed, 2),
        corpus_multiple=round(needed / annual_spending, 2),
        withdrawal_rate=round(annual_spending / needed, 6),
        accumulation=accumulation,
        money_lasts_until=None if ran_out is None else round(plan.retirement_age + ran_out, 1),
        lifetime=lifetime,
    )


def _value_after(goal: GoalInputs, years: int) -> float:
    """Savings + SIP value after `years` (Phase 3 closed forms)."""
    if goal.step_up_rate:
        sip = tvm.step_up_sip_future_value(
            goal.monthly_sip, goal.expected_return, years, goal.step_up_rate
        )
    else:
        sip = tvm.sip_future_value(goal.monthly_sip, goal.expected_return, years * MONTHS)
    return tvm.future_value(goal.current_savings, goal.expected_return, years) + sip


def sustainable_withdrawal_rate(inflation_rate: float, annual_return: float, years: int) -> float:
    """The highest first-year withdrawal rate (of the corpus) that lasts exactly `years`.

    The inverse of the corpus multiple: 12 / PV of a growing annuity of ₹1 a month. Bengen's 4%
    rule is this number for US history (~3% inflation) over 30 years.
    """
    pv = tvm.present_value_growing_annuity(1.0, inflation_rate, annual_return, years)
    return MONTHS / pv if pv > 0 else math.inf
