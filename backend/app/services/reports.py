"""Gathers everything the plan PDF shows, from the same services the pages use."""

from dataclasses import replace
from datetime import date

from sqlalchemy.orm import Session

from app.models import User
from app.reports.plan_pdf import (
    Allocation,
    FundPick,
    GoalSection,
    HoldingRow,
    PlanReport,
    PortfolioSection,
    ProfileSection,
    RetirementSection,
    SimulationSummary,
    Tracking,
    render,
)
from app.schemas.profile import ProfileRead
from app.services import funds as fund_service
from app.services import goals as goal_service
from app.services import portfolio as portfolio_service
from app.services import recommendations as recommendation_service
from app.services import retirement as retirement_service
from app.services import simulations as simulation_service
from app.services.profile import get_profile
from app.services.risk import latest_assessment


def _profile(db: Session, user: User) -> ProfileSection | None:
    stored = get_profile(db, user)
    if stored is None:
        return None
    profile = ProfileRead.model_validate(stored)
    assessment = latest_assessment(db, user)
    return ProfileSection(
        age=profile.age,
        employment=profile.employment_type,
        monthly_income=profile.monthly_income,
        monthly_expenses=profile.monthly_expenses,
        monthly_emi=profile.monthly_emi,
        monthly_surplus=profile.monthly_surplus,
        savings=profile.current_savings,
        investments=profile.existing_investments,
        dependants=profile.dependents,
        risk_category=assessment.category if assessment else None,
        risk_score=assessment.final_score if assessment else None,
        tolerance_score=assessment.tolerance_score if assessment else None,
        capacity_score=assessment.capacity_score if assessment else None,
        assessed_on=assessment.created_at.date() if assessment else None,
    )


def plan_report(db: Session, user: User, today: date | None = None) -> PlanReport:
    today = today or date.today()
    category = goal_service.risk_category(db, user)
    portfolio = portfolio_service.portfolio(db, user, today)
    tracked = {g.goal_id: g for g in portfolio.goals if g.status != "not_started"}

    goals: list[GoalSection] = []
    for goal in goal_service.list_goals(db, user):
        p = goal_service.calculate(goal, category, today)
        section = GoalSection(
            name=goal.name,
            goal_type=goal.goal_type,
            target_year=goal.target_year,
            years=p.years_to_goal,
            cost_today=float(goal.target_amount),
            inflation=float(goal.inflation_rate),
            inflated_target=p.inflated_target,
            current_savings=float(goal.current_savings),
            monthly_sip=float(goal.monthly_sip),
            step_up=float(goal.step_up_rate),
            expected_return=p.expected_return_used,
            projected_value=p.projected_value,
            funded_percent=p.funded_percent,
            on_track=p.on_track,
            required_sip=p.required_sip,
        )
        status = tracked.get(goal.id)
        if status is not None:
            # With recorded investments, the projection starts from their value (as the
            # portfolio page and the assistant do).
            section = replace(
                section,
                current_savings=status.value,
                projected_value=status.projected_value,
                funded_percent=status.funded_percent,
                on_track=status.status == "on_track",
                required_sip=status.required_sip,
                tracking=Tracking(
                    status.status, status.value, status.cost, status.xirr,
                    status.plan_value, status.rebalance_needed,
                ),
            )  # fmt: skip
        recommendations = recommendation_service.history_for(db, goal)
        if recommendations:
            rec = recommendation_service.to_read(recommendations[0])
            section = replace(
                section,
                allocation=[Allocation(a.sleeve, a.label, a.weight) for a in rec.allocation],
                recommended_on=rec.created_at.date(),
                recommended_return=rec.expected_return,
                funds=[FundPick(f.name, f.sleeve_label, f.weight) for f in rec.funds],
            )
        saved = simulation_service.list_simulations(db, goal)
        if saved:
            run = simulation_service.to_read(saved[0])
            ninety = next((r.monthly_sip for r in run.required_sip if r.probability == 90), None)
            section = replace(
                section,
                simulation=SimulationSummary(
                    run.run_at.date(), run.model, run.success_probability,
                    run.final.p10, run.final.p50, run.final.p90, ninety,
                ),
            )  # fmt: skip
        goals.append(section)

    retirement = None
    plan = retirement_service.get_plan(db, user)
    if plan is not None:
        read = retirement_service.to_read(db, user, plan)
        r = read.projection
        retirement = RetirementSection(
            current_age=r.current_age,
            retirement_age=read.retirement_age,
            life_expectancy=read.life_expectancy,
            monthly_expense_today=read.monthly_expense,
            corpus_needed=r.corpus_needed,
            corpus_needed_today=r.corpus_needed_today,
            projected_corpus=r.accumulation.projected_value,
            required_sip=r.accumulation.required_sip,
            monthly_sip=read.monthly_sip,
            withdrawal_rate=r.withdrawal_rate,
            money_lasts_until=r.money_lasts_until,
        )

    holdings = sorted((h for h in portfolio.holdings if h.units > 0), key=lambda h: -h.value)
    portfolio_section = PortfolioSection(
        value=portfolio.totals.value,
        cost=portfolio.totals.cost,
        xirr=portfolio.totals.xirr,
        as_of=portfolio.totals.as_of,
        holdings=[
            HoldingRow(h.fund_name, h.goal_name or "Not assigned", h.value, h.cost, h.xirr)
            for h in holdings
        ],
        alerts=[f"{a.goal_name}: {a.message}" for a in portfolio.alerts],
    )
    return PlanReport(
        name=user.full_name,
        generated_on=today,
        profile=_profile(db, user),
        goals=goals,
        retirement=retirement,
        portfolio=portfolio_section,
        data_as_of=fund_service.newest_nav_date(db),
    )


def plan_pdf(db: Session, user: User, today: date | None = None) -> bytes:
    return render(plan_report(db, user, today))
