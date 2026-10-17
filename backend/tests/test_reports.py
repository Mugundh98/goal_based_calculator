"""The plan PDF: rendering (pure) and the download endpoint."""

from datetime import date
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy import select

from app.models import AuditLog
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

THIS_YEAR = date.today().year


def text_of(pdf: bytes) -> str:
    reader = PdfReader(BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def goal(**overrides) -> GoalSection:
    values = dict(
        name="Daughter's education", goal_type="education", target_year=2036, years=10,
        cost_today=2_500_000, inflation=6, inflated_target=4_477_119.24, current_savings=0,
        monthly_sip=15_000, step_up=0, expected_return=10, projected_value=3_022_000,
        funded_percent=67.4, on_track=False, required_sip=22_224,
    )  # fmt: skip
    return GoalSection(**(values | overrides))


def full_plan() -> PlanReport:
    return PlanReport(
        name="Priya Demo",
        generated_on=date(2026, 10, 17),
        profile=ProfileSection(
            age=36,
            employment="salaried",
            monthly_income=150_000,
            monthly_expenses=60_000,
            monthly_emi=10_000,
            monthly_surplus=80_000,
            savings=300_000,
            investments=0,
            dependants=2,
            risk_category="moderate",
            risk_score=55,
            tolerance_score=60,
            capacity_score=55,
            assessed_on=date(2026, 10, 1),
        ),  # fmt: skip
        goals=[
            goal(
                allocation=[
                    Allocation("large_cap", "Large-cap equity", 41.63),
                    Allocation("long_debt", "Longer-term bonds", 58.37),
                ],
                recommended_on=date(2026, 10, 17),
                recommended_return=10.7,
                funds=[FundPick("quant Large Cap Fund", "Large-cap equity", 20.8)],
                simulation=SimulationSummary(
                    date(2026, 10, 16), "bootstrap", 31.2, 2_100_000, 3_000_000, 4_300_000, 27_464
                ),
                tracking=Tracking("on_track", 1_605_939, 1_156_056, 10.98, 1_557_358, True),
            ),
            goal(
                name="New car <fast> & red",
                goal_type="car",
                target_year=2028,
                years=2,
                on_track=True,
                funded_percent=100,
                required_sip=0,
            ),
        ],  # fmt: skip
        retirement=RetirementSection(
            current_age=36,
            retirement_age=60,
            life_expectancy=85,
            monthly_expense_today=50_000,
            corpus_needed=72_500_000,
            corpus_needed_today=17_900_000,
            projected_corpus=40_000_000,
            required_sip=38_000,
            monthly_sip=20_000,
            withdrawal_rate=3.3,
            money_lasts_until=74.5,
        ),  # fmt: skip
        portfolio=PortfolioSection(
            value=1_919_565,
            cost=1_456_056,
            xirr=9.76,
            as_of=date(2026, 10, 15),
            holdings=[
                HoldingRow("HDFC Mid Cap Fund", "Daughter's education", 388_705, 275_000, 15.48)
            ],
            alerts=["New car: Off track: a SIP of ₹20,946 would close the gap."],
        ),  # fmt: skip
        data_as_of=date(2026, 10, 15),
    )


def test_full_plan_renders_every_section():
    pdf = render(full_plan())
    assert pdf.startswith(b"%PDF")
    text = text_of(pdf)
    for expected in (
        "Your financial plan", "Prepared for Priya Demo", "About you", "Moderate",
        "Your goals", "Daughter's education", "New car <fast> & red", "Rs 44,77,119",
        "Rs 22,224", "Recommended allocation", "quant Large Cap Fund", "31.2% chance",
        "XIRR 10.98%", "rebalancing is due", "Retirement", "Rs 7.25 crore",
        "runs out at about age 74", "Your investments", "Rs 19,19,565", "HDFC Mid Cap Fund",
        "Rs 20,946 would close the gap", "not investment advice", "Page 1",
    ):  # fmt: skip
        assert expected in text, expected
    assert "₹" not in text  # the built-in fonts have no rupee glyph: written "Rs"


def test_an_empty_plan_still_renders():
    plan = PlanReport("New User", date(2026, 10, 17), None, [], None, None, None)
    text = text_of(render(plan))
    assert "No goals yet" in text and "not assessed" in text


def test_download_needs_login(client):
    assert client.get("/api/reports/plan").status_code == 401


def test_download_my_plan(client, db, auth_headers):
    client.post("/api/goals", headers=auth_headers, json={
        "goal_type": "house", "name": "Flat in Pune", "target_amount": 6_000_000,
        "target_year": THIS_YEAR + 8, "monthly_sip": 25_000,
    })  # fmt: skip
    response = client.get("/api/reports/plan", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="goalwise-plan-'
    )
    assert response.headers["cache-control"] == "no-store"
    text = text_of(response.content)
    assert "Prepared for Test User" in text and "Flat in Pune" in text
    logged = db.scalar(select(AuditLog).where(AuditLog.action == "report.download"))
    assert logged.actor_email == "user@example.com" and logged.details["bytes"] == len(
        response.content
    )
