"""A demo account with a complete, realistic plan, for the viva and for first-time visitors.

The household is a salaried 36-year-old with two children: a profile, a moderate risk profile,
three goals, a retirement plan, about three years of SIPs and lump sums in real funds (so the
portfolio has an XIRR and goal progress) and a recommendation for every goal.

Each goal's mix is close to what GoalWise recommends for its horizon (mostly liquid funds for the
car in two years), except the education goal, which has drifted a little towards equity, to show
a rebalancing alert. Dates are relative to today, so the portfolio always looks current.
"""

import secrets
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.finance.risk_profile import QUESTIONS
from app.models import User
from app.schemas.auth import UserCreate
from app.schemas.goal import GoalInput
from app.schemas.portfolio import SipCreate, TransactionCreate
from app.schemas.profile import ProfileInput
from app.schemas.retirement import RetirementInput
from app.services import funds as fund_service
from app.services import goals as goal_service
from app.services import portfolio as portfolio_service
from app.services import recommendations as recommendation_service
from app.services import retirement as retirement_service
from app.services.profile import upsert_profile
from app.services.risk import create_assessment

DEFAULT_EMAIL = "demo@example.com"  # a reserved domain: no real mailbox
DEFAULT_NAME = "Priya Sharma"

# Real direct-growth funds, found by name in the fund master.
FUND_QUERIES = {
    "large": "nippon india large cap",
    "mid": "hdfc mid",
    "bond": "icici prudential corporate bond",
    "liquid": "hdfc liquid",
}


class DemoError(Exception):
    pass


@dataclass
class DemoResult:
    user: User
    password: str
    goals: dict[str, int]
    transactions: int
    recommendations: int
    notes: list[str] = field(default_factory=list)


def new_password() -> str:
    """Random, and acceptable to the sign-up rules (a letter and a digit)."""
    while True:
        password = secrets.token_urlsafe(12)
        if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
            return password


def find_funds(db: Session) -> dict[str, int]:
    found = {}
    for key, query in FUND_QUERIES.items():
        page = fund_service.list_funds(db, q=query, plan="direct", option="growth", page_size=1)
        if not page.items:
            raise DemoError(f"No fund matches {query!r}: load the market data first")
        found[key] = page.items[0].id
    return found


def create_demo_user(
    db: Session,
    email: str = DEFAULT_EMAIL,
    password: str | None = None,
    full_name: str = DEFAULT_NAME,
    reset: bool = False,
    funds: dict[str, int] | None = None,
    today: date | None = None,
) -> DemoResult:
    """Create the account and its plan. With reset, an existing account is deleted first."""
    today = today or date.today()
    email = email.strip().lower()
    password = password or new_password()
    try:  # the same rules as signing up
        UserCreate(email=email, password=password, full_name=full_name)
    except ValidationError as exc:
        raise DemoError(exc.errors()[0]["msg"]) from exc
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if not reset:
            raise DemoError(f"{email} already exists (use --reset to recreate it)")
        db.execute(delete(User).where(User.id == existing.id))  # its data goes with it (CASCADE)
        db.commit()
    funds = funds or find_funds(db)

    user = User(email=email, password_hash=hash_password(password), full_name=full_name)
    db.add(user)
    db.commit()
    upsert_profile(
        db,
        user,
        ProfileInput(
            date_of_birth=date(today.year - 36, 5, 17),
            employment_type="salaried",
            monthly_income=Decimal(150000),
            monthly_expenses=Decimal(60000),
            monthly_emi=Decimal(10000),
            current_savings=Decimal(400000),
            existing_investments=Decimal(200000),
            dependents=2,
        ),
    )
    create_assessment(db, user, {q.id: "c" for q in QUESTIONS})  # middle answers: moderate

    def goal(**fields) -> int:
        return goal_service.create_goal(db, user, GoalInput(**fields)).id

    goals = {
        "education": goal(
            goal_type="education",
            name="Pisai's college",
            target_amount=Decimal(2500000),
            target_year=today.year + 10,
            monthly_sip=Decimal(15000),
            step_up_rate=Decimal(5),
        ),
        "car": goal(
            goal_type="car",
            name="New car",
            target_amount=Decimal(800000),
            target_year=today.year + 2,
            monthly_sip=Decimal(20000),
        ),
        "house": goal(
            goal_type="house",
            name="Home down payment",
            target_amount=Decimal(2000000),
            target_year=today.year + 6,
            priority=2,
            monthly_sip=Decimal(12000),
        ),
    }
    plan = retirement_service.save_plan(
        db,
        user,
        RetirementInput(
            retirement_age=58,
            monthly_expense=Decimal(60000),
            current_savings=Decimal(600000),  # EPF and PPF
            monthly_sip=Decimal(15000),
            step_up_rate=Decimal(5),
        ),
    )
    goals["retirement"] = plan.goal_id

    days_ago = lambda n: today - timedelta(days=n)  # noqa: E731
    created = 0
    for sip in (
        SipCreate(fund_id=funds["large"], goal_id=goals["education"], amount=Decimal(10000),
                  start_date=days_ago(1000)),
        SipCreate(fund_id=funds["mid"], goal_id=goals["education"], amount=Decimal(5000),
                  start_date=days_ago(800)),
        SipCreate(fund_id=funds["large"], goal_id=goals["house"], amount=Decimal(2500),
                  start_date=days_ago(600)),
        SipCreate(fund_id=funds["mid"], goal_id=goals["house"], amount=Decimal(800),
                  start_date=days_ago(600)),
        SipCreate(fund_id=funds["bond"], goal_id=goals["house"], amount=Decimal(6700),
                  start_date=days_ago(600)),
    ):  # fmt: skip
        created += len(portfolio_service.add_sip(db, user, sip, today=today))
    for txn in (
        TransactionCreate(fund_id=funds["bond"], goal_id=goals["education"], txn_type="buy",
                          txn_date=days_ago(950), amount=Decimal(150000)),
        TransactionCreate(fund_id=funds["liquid"], goal_id=goals["car"], txn_type="buy",
                          txn_date=days_ago(500), amount=Decimal(230000)),
        TransactionCreate(fund_id=funds["bond"], goal_id=goals["car"], txn_type="buy",
                          txn_date=days_ago(500), amount=Decimal(75000)),
        TransactionCreate(fund_id=funds["large"], goal_id=goals["car"], txn_type="buy",
                          txn_date=days_ago(480), amount=Decimal(25000)),
        TransactionCreate(fund_id=funds["large"], goal_id=goals["education"], txn_type="sell",
                          txn_date=days_ago(250), amount=Decimal(40000)),
    ):  # fmt: skip
        portfolio_service.add_transaction(db, user, txn)
        created += 1

    result = DemoResult(user, password, goals, created, 0)
    for goal_id in goals.values():
        goal_row = goal_service.get_goal(db, user, goal_id)
        try:
            recommendation_service.recommend(db, user, goal_row, today=today)
            result.recommendations += 1
        except recommendation_service.RecommendationUnavailable as exc:
            result.notes.append(f"No recommendation: {exc}")
            break
    return result
