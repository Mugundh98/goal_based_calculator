"""Runs the risk-profiling rules for a user and stores the result."""

from dataclasses import asdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance import risk_profile as rp
from app.models.risk import RiskAssessment
from app.models.user import User
from app.services.profile import get_profile


class ProfileRequiredError(Exception):
    """Capacity cannot be scored without a financial profile."""


def create_assessment(db: Session, user: User, answers: dict[str, str]) -> RiskAssessment:
    profile = get_profile(db, user)
    if profile is None:
        raise ProfileRequiredError

    tolerance = rp.tolerance_score(answers)  # raises InvalidAnswersError
    factors = rp.capacity_factors(
        rp.CapacityInputs(
            age=rp.age_on(profile.date_of_birth, date.today()),
            employment_type=profile.employment_type,
            monthly_income=profile.monthly_income,
            monthly_expenses=profile.monthly_expenses,
            monthly_emi=profile.monthly_emi,
            current_savings=profile.current_savings,
            dependents=profile.dependents,
        )
    )
    capacity = rp.capacity_score(factors)
    final_score, category = rp.final_profile(tolerance, capacity)

    assessment = RiskAssessment(
        user_id=user.id,
        questionnaire_version=rp.QUESTIONNAIRE_VERSION,
        answers=answers,
        tolerance_score=tolerance,
        capacity_score=capacity,
        final_score=final_score,
        category=category,
        capacity_breakdown=[asdict(f) for f in factors],
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def list_assessments(db: Session, user: User) -> list[RiskAssessment]:
    """Newest first."""
    query = (
        select(RiskAssessment)
        .where(RiskAssessment.user_id == user.id)
        .order_by(RiskAssessment.created_at.desc(), RiskAssessment.id.desc())
    )
    return list(db.scalars(query))


def latest_assessment(db: Session, user: User) -> RiskAssessment | None:
    return next(iter(list_assessments(db, user)), None)
