"""Retirement planner: one plan per user, its savings phase kept as a `retirement` goal.

The current age comes from the financial profile, so a profile is required (ProfileRequiredError,
as for risk assessments). Projections are computed on every read, like goals (ADR-006); the
lifetime simulation reuses the Phase 5 market history and return models (ADR-008, ADR-009).
"""

import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance import tvm
from app.finance.goal_plan import ReturnSource, suggested_return
from app.finance.retirement import RetirementInputs, plan_retirement
from app.finance.risk_profile import age_on
from app.models.goal import Goal
from app.models.retirement import RetirementPlan
from app.models.user import User
from app.schemas.retirement import (
    AccumulationOut,
    CorpusPercentilesOut,
    LevelCorpusOut,
    LevelSipOut,
    LifetimeBandOut,
    LifetimeYearOut,
    RetirementInput,
    RetirementPlanRead,
    RetirementProjectionOut,
    RetirementSimulationOut,
    RetirementSimulationRequest,
    ReturnPhaseOut,
    SurvivalOut,
)
from app.services import simulations
from app.services.goals import risk_category
from app.services.profile import get_profile
from app.services.risk import ProfileRequiredError
from app.simulation import engine
from app.simulation import retirement as lifetime
from app.simulation.allocation import equity_share_for_return

PERCENT = 100
CENT = Decimal("0.01")


class RetirementInputError(ValueError):
    """Inputs that are valid on their own but not for this user (e.g. retiring in the past)."""


@dataclass(frozen=True)
class Resolved:
    inputs: RetirementInputs  # fractions, for app/finance and app/simulation
    pre_return_source: ReturnSource
    this_year: int


def resolve(db: Session, user: User, data: RetirementInput, today: date | None = None) -> Resolved:
    today = today or date.today()
    profile = get_profile(db, user)
    if profile is None:
        raise ProfileRequiredError
    age = age_on(profile.date_of_birth, today)
    if data.retirement_age <= age:
        raise RetirementInputError(f"Retirement age must be above your current age ({age})")
    years = data.retirement_age - age
    if data.pre_retirement_return is None:
        pre, source = suggested_return(risk_category(db, user), years)
    else:
        pre, source = float(data.pre_retirement_return) / PERCENT, "custom"
    inputs = RetirementInputs(
        current_age=age,
        retirement_age=data.retirement_age,
        life_expectancy=data.life_expectancy,
        monthly_expense=float(data.monthly_expense),
        inflation_rate=float(data.inflation_rate) / PERCENT,
        pre_retirement_return=pre,
        post_retirement_return=float(data.post_retirement_return) / PERCENT,
        current_savings=float(data.current_savings),
        monthly_sip=float(data.monthly_sip),
        step_up_rate=float(data.step_up_rate) / PERCENT,
    )
    return Resolved(inputs, source, today.year)


def calculate(
    db: Session, user: User, data: RetirementInput, today: date | None = None
) -> RetirementProjectionOut:
    """The single-return plan. Nothing is saved."""
    resolved = resolve(db, user, data, today)
    plan, this_year = resolved.inputs, resolved.this_year
    projection = plan_retirement(plan)
    a = projection.accumulation
    first_year = projection.first_monthly_withdrawal * tvm.MONTHS_PER_YEAR
    return RetirementProjectionOut(
        current_age=plan.current_age,
        years_to_retirement=plan.years_to_retirement,
        retirement_year=this_year + plan.years_to_retirement,
        retirement_years=plan.retirement_years,
        pre_retirement_return_used=round(plan.pre_retirement_return * PERCENT, 2),
        pre_retirement_return_source=resolved.pre_return_source,
        post_retirement_return=round(plan.post_retirement_return * PERCENT, 2),
        real_post_return=round(
            tvm.real_return(plan.post_retirement_return, plan.inflation_rate) * PERCENT, 2
        ),
        first_monthly_withdrawal=projection.first_monthly_withdrawal,
        corpus_needed=projection.corpus_needed,
        corpus_needed_today=round(corpus_today(plan, projection.corpus_needed), 2),
        corpus_multiple=projection.corpus_multiple,
        withdrawal_rate=round(projection.withdrawal_rate * PERCENT, 2),
        bengen_corpus=round(first_year / 0.04, 2),
        accumulation=AccumulationOut(
            savings_value=a.savings_value,
            sip_value=a.sip_value,
            projected_value=a.projected_value,
            shortfall=a.shortfall,
            required_sip=a.required_sip,
            funded_percent=a.funded_percent,
            on_track=a.on_track,
        ),
        money_lasts_until=projection.money_lasts_until,
        lifetime=[
            LifetimeYearOut(
                year=y.year,
                calendar_year=this_year + y.year,
                age=y.age,
                balance=y.balance,
                phase=y.phase,
            )
            for y in projection.lifetime
        ],
    )


def corpus_today(plan: RetirementInputs, corpus: float) -> float:
    """The corpus in today's money: what the goal stores as its target (Phase 3 inflates it)."""
    return tvm.present_value(corpus, plan.inflation_rate, plan.years_to_retirement)


# --- Saved plan -------------------------------------------------------------------------------


def get_plan(db: Session, user: User) -> RetirementPlan | None:
    return db.scalar(select(RetirementPlan).where(RetirementPlan.user_id == user.id))


def plan_input(plan: RetirementPlan) -> RetirementInput:
    """The saved plan as planner input: retirement fields from the plan, the rest from its goal."""
    goal = plan.goal
    return RetirementInput(
        retirement_age=plan.retirement_age,
        life_expectancy=plan.life_expectancy,
        monthly_expense=plan.monthly_expense,
        inflation_rate=goal.inflation_rate,
        pre_retirement_return=goal.expected_return,
        post_retirement_return=plan.post_retirement_return,
        current_savings=goal.current_savings,
        monthly_sip=goal.monthly_sip,
        step_up_rate=goal.step_up_rate,
    )


def to_read(db: Session, user: User, plan: RetirementPlan) -> RetirementPlanRead:
    data = plan_input(plan)
    return RetirementPlanRead(
        **data.model_dump(),
        goal_id=plan.goal_id,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        projection=calculate(db, user, data),
    )


def _sync_goal(goal: Goal, data: RetirementInput, resolved: Resolved) -> None:
    """Write the savings phase onto the goal: target = corpus in today's money."""
    plan = resolved.inputs
    corpus = plan_retirement(plan).corpus_needed
    goal.goal_type = "retirement"
    goal.name = f"Retirement at {plan.retirement_age}"
    goal.target_amount = Decimal(str(round(corpus_today(plan, corpus), 2))).quantize(CENT)
    goal.target_year = resolved.this_year + plan.years_to_retirement
    goal.priority = 1
    goal.inflation_rate = data.inflation_rate
    goal.expected_return = data.pre_retirement_return
    goal.current_savings = data.current_savings
    goal.monthly_sip = data.monthly_sip
    goal.step_up_rate = data.step_up_rate


def save_plan(db: Session, user: User, data: RetirementInput) -> RetirementPlan:
    """Create or replace the plan and its goal (idempotent, like PUT /api/profile)."""
    resolved = resolve(db, user, data)
    plan = get_plan(db, user)
    if plan is None:
        goal = Goal(user_id=user.id)
        plan = RetirementPlan(user_id=user.id, goal=goal)
        db.add(plan)
    _sync_goal(plan.goal, data, resolved)
    plan.retirement_age = data.retirement_age
    plan.life_expectancy = data.life_expectancy
    plan.monthly_expense = data.monthly_expense
    plan.post_retirement_return = data.post_retirement_return
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db: Session, plan: RetirementPlan) -> None:
    """Deleting the goal deletes the plan (ON DELETE CASCADE): both go."""
    db.delete(plan.goal)
    db.commit()


def resync_after_profile_change(db: Session, user: User) -> None:
    """A new date of birth moves the retirement year: update the goal. Silently skip a plan the
    new age makes impossible (retiring in the past); the planner page then asks for a new age."""
    plan = get_plan(db, user)
    if plan is None:
        return
    data = plan_input(plan)
    try:
        _sync_goal(plan.goal, data, resolve(db, user, data))
    except (RetirementInputError, tvm.FinanceInputError):
        return
    db.commit()


# --- Simulation -------------------------------------------------------------------------------


def simulate(
    db: Session, user: User, request: RetirementSimulationRequest, today: date | None = None
) -> RetirementSimulationOut:
    """Monte Carlo over the whole lifetime. Nothing is saved."""
    resolved = resolve(db, user, request, today)
    plan, this_year = resolved.inputs, resolved.this_year
    history = simulations.market_history(db)
    seed = engine.DEFAULT_SEED if request.seed is None else request.seed

    started = time.perf_counter()
    pre_share = equity_share_for_return(plan.pre_retirement_return)
    post_share = equity_share_for_return(plan.post_retirement_return)
    pre_model = simulations.return_model(request.model, history, pre_share)
    post_model = simulations.return_model(request.model, history, post_share)
    outcome = lifetime.run(plan, pre_model, post_model, paths=request.paths, seed=seed)
    elapsed = round((time.perf_counter() - started) * 1000)

    def phase(annual_return: float, share: float, model) -> ReturnPhaseOut:
        return ReturnPhaseOut(
            expected_return=round(annual_return * PERCENT, 2),
            equity_percent=round(share * PERCENT, 1),
            annual_volatility=round(model.annual_volatility * PERCENT, 2),
        )

    return RetirementSimulationOut(
        model=request.model,
        paths=request.paths,
        seed=seed,
        success_probability=round(outcome.success_probability * PERCENT, 1),
        corpus_at_retirement=CorpusPercentilesOut(
            **{f"p{p}": round(v, 2) for p, v in outcome.corpus_percentiles.items()}
        ),
        corpus_target=outcome.corpus_target,
        survival=[
            SurvivalOut(age=age, probability=round(share * PERCENT, 1))
            for age, share in outcome.survival
        ],
        depletion_age_p10=round(outcome.depletion_age_p10, 1),
        median_depletion_age=None
        if outcome.median_depletion_age is None
        else round(outcome.median_depletion_age, 1),
        required_sip=[
            LevelSipOut(probability=level, monthly_sip=sip)
            for level, sip in outcome.required_sip.items()
        ],
        corpus_needed=[
            LevelCorpusOut(probability=level, corpus=corpus)
            for level, corpus in outcome.corpus_needed.items()
        ],
        before_retirement=phase(plan.pre_retirement_return, pre_share, pre_model),
        after_retirement=phase(plan.post_retirement_return, post_share, post_model),
        history=simulations.history_out(history),
        bands=[
            LifetimeBandOut(
                year=band.year,
                calendar_year=this_year + band.year,
                age=band.age,
                **{f"p{p}": round(v, 2) for p, v in band.percentiles.items()},
                deterministic=round(band.deterministic, 2),
            )
            for band in outcome.bands
        ],
        as_of=today or date.today(),
        elapsed_ms=elapsed,
    )
