"""API tests for the portfolio tracker (real test database, synthetic daily NAVs)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, insert, select

from app.finance.formatting import inr
from app.models import Fund, Holding, NavHistory, Recommendation, Transaction, User
from app.services import portfolio as service
from tests.conftest import login_headers

TODAY = date.today()
LATEST = TODAY - timedelta(days=1)
START = LATEST - timedelta(days=3 * 365)
THIS_YEAR = TODAY.year
SPLIT_ON = START + timedelta(days=400)  # the unit-change fund's ₹10 -> ₹1,000 re-denomination


def nav_on(base: float, growth: float, day: date) -> float:
    return base * (1 + growth) ** ((day - START).days / 365)


def weekdays(start: date, end: date) -> list[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def make_fund(db, code, category, asset_class, base, growth, split_on=None):
    days = weekdays(START, LATEST)
    navs = [nav_on(base, growth, d) * (100 if split_on and d >= split_on else 1) for d in days]
    fund = Fund(
        scheme_code=code,
        name=f"Test {category} - Direct Plan - Growth",
        amc=f"AMC {code}",
        scheme_type="Open Ended",
        category=category,
        asset_class=asset_class,
        plan="direct",
        option="growth",
        latest_nav=Decimal(f"{navs[-1]:.4f}"),
        latest_nav_date=days[-1],
    )
    db.add(fund)
    db.flush()
    db.execute(
        insert(NavHistory),
        [
            {"fund_id": fund.id, "nav_date": d, "nav": Decimal(f"{n:.4f}")}
            for d, n in zip(days, navs, strict=True)
        ],
    )
    return fund


@pytest.fixture
def funds(db):
    made = {
        "equity": make_fund(db, 960_001, "Equity Scheme - Large Cap Fund", "equity", 10, 0.12),
        "debt": make_fund(db, 960_002, "Debt Scheme - Corporate Bond Fund", "debt", 20, 0.07),
        "split": make_fund(
            db, 960_003, "Debt Scheme - Liquid Fund", "debt", 10, 0.06, split_on=SPLIT_ON
        ),
    }
    db.commit()
    return made


def make_goal(client, headers, **overrides):
    body = {"goal_type": "education", "name": "College", "target_amount": 2_000_000,
            "target_year": THIS_YEAR + 10, "monthly_sip": 10_000} | overrides  # fmt: skip
    response = client.post("/api/goals", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def txn(client, headers, fund, kind="buy", day=None, expect=201, **extra):
    body = {"fund_id": fund.id, "txn_type": kind, "txn_date": (day or START).isoformat()} | {
        k: (v.isoformat() if isinstance(v, date) else v) for k, v in extra.items()
    }
    response = client.post("/api/portfolio/transactions", json=body, headers=headers)
    assert response.status_code == expect, response.text
    return response.json()


def holdings(db, user_email="user@example.com"):
    user = db.scalar(select(User).where(User.email == user_email))
    rows = db.scalars(select(Holding).where(Holding.user_id == user.id).order_by(Holding.id))
    return [(h.goal_id, h.fund_id, h.units, h.cost, h.realised_gain) for h in rows]


def first_weekday_on_or_after(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


# --- Access ----------------------------------------------------------------------------------


def test_requires_login(client):
    assert client.get("/api/portfolio").status_code == 401
    assert client.post("/api/portfolio/transactions", json={}).status_code == 401


def test_empty_portfolio(client, auth_headers):
    body = client.get("/api/portfolio", headers=auth_headers).json()
    assert body["holdings"] == [] and body["alerts"] == []
    assert body["totals"]["value"] == 0 and body["totals"]["xirr"] is None


# --- Recording transactions -------------------------------------------------------------------


def test_purchase_uses_that_days_nav_and_updates_holdings(client, db, auth_headers, funds):
    day = first_weekday_on_or_after(START + timedelta(days=30))
    body = txn(client, auth_headers, funds["equity"], day=day, amount=10_000)
    nav = round(nav_on(10, 0.12, day), 4)
    assert body["nav"] == pytest.approx(nav)
    # Stamp duty (0.005%) is deducted before units are allotted.
    assert body["units"] == pytest.approx(int(9999.5 / nav * 1000) / 1000)
    assert body["fund_name"].startswith("Test Equity") and body["goal_id"] is None

    [(goal_id, fund_id, units, cost, _)] = holdings(db)
    assert (goal_id, fund_id, cost) == (None, funds["equity"].id, Decimal("10000.00"))
    assert float(units) == pytest.approx(body["units"])

    portfolio = client.get("/api/portfolio", headers=auth_headers).json()
    [holding] = portfolio["holdings"]
    assert holding["value"] == pytest.approx(
        body["units"] * float(funds["equity"].latest_nav), abs=0.01
    )
    assert holding["sleeve"] == "large_cap"
    # The NAV grows 12% a year, so the purchase's XIRR is 12% less the stamp duty.
    assert holding["xirr"] == pytest.approx(12.0, abs=0.05)
    assert portfolio["totals"]["xirr"] == holding["xirr"]


def test_weekend_uses_the_previous_nav_but_not_a_stale_one(client, auth_headers, funds):
    saturday = START + timedelta(days=(5 - START.weekday()) % 7 + 7)
    friday = saturday - timedelta(days=1)
    body = txn(client, auth_headers, funds["equity"], day=saturday, amount=5000)
    assert body["nav"] == pytest.approx(round(nav_on(10, 0.12, friday), 4))

    before_launch = START - timedelta(days=30)
    response = txn(
        client, auth_headers, funds["equity"], day=before_launch, amount=5000, expect=422
    )
    assert "no NAV on" in response["detail"]
    future = txn(
        client, auth_headers, funds["equity"], day=TODAY + timedelta(days=1), amount=1, expect=422
    )
    assert "future" in future["detail"]


def test_validation(client, auth_headers, funds):
    assert txn(client, auth_headers, funds["equity"], expect=422)["detail"]  # no amount
    txn(client, auth_headers, funds["equity"], kind="sell", expect=422)  # neither amount nor units
    txn(client, auth_headers, funds["equity"], amount=-5, expect=422)
    body = {"fund_id": 999_999_999, "txn_type": "buy", "txn_date": START.isoformat(), "amount": 100}
    assert (
        client.post("/api/portfolio/transactions", json=body, headers=auth_headers).status_code
        == 404
    )


def test_redemption_by_units_books_a_fifo_gain(client, db, auth_headers, funds):
    fund = funds["debt"]
    d1 = first_weekday_on_or_after(START + timedelta(days=10))
    d2 = first_weekday_on_or_after(START + timedelta(days=400))
    d3 = first_weekday_on_or_after(START + timedelta(days=800))
    b1 = txn(client, auth_headers, fund, day=d1, amount=10_000)
    b2 = txn(client, auth_headers, fund, day=d2, amount=10_000)
    sold_units = round(b1["units"] + b2["units"] / 2, 3)
    s = txn(client, auth_headers, fund, kind="sell", day=d3, units=sold_units)
    assert s["amount"] == pytest.approx(round(sold_units * s["nav"], 2))

    [(_, _, units, cost, realised)] = holdings(db)
    assert float(units) == pytest.approx(b1["units"] + b2["units"] - sold_units, abs=1e-6)
    # FIFO: the whole first lot and half of the second were sold.
    expected_cost_sold = 10_000 + 10_000 * (sold_units - b1["units"]) / b2["units"]
    assert float(realised) == pytest.approx(s["amount"] - expected_cost_sold, abs=0.02)
    assert float(cost) == pytest.approx(20_000 - expected_cost_sold, abs=0.02)


def test_over_redemption_is_refused_and_nothing_changes(client, db, auth_headers, funds):
    fund = funds["equity"]
    b = txn(client, auth_headers, fund, day=START + timedelta(days=7), amount=10_000)
    before = holdings(db)
    response = txn(client, auth_headers, fund, kind="sell", day=START + timedelta(days=60),
                   units=b["units"] + 1, expect=422)  # fmt: skip
    assert "cannot redeem" in response["detail"]
    assert holdings(db) == before
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1
    # Units bought later cannot pay for an earlier redemption.
    txn(client, auth_headers, fund, kind="sell", day=START + timedelta(days=3), units=1, expect=422)


def test_delete_keeps_holdings_consistent(client, db, auth_headers, funds):
    fund = funds["equity"]
    b = txn(client, auth_headers, fund, day=START + timedelta(days=7), amount=10_000)
    s = txn(
        client, auth_headers, fund, kind="sell", day=START + timedelta(days=90), units=b["units"]
    )
    response = client.delete(f"/api/portfolio/transactions/{b['id']}", headers=auth_headers)
    assert response.status_code == 409
    assert "Delete the redemption first" in response.json()["detail"]
    assert (
        client.delete(f"/api/portfolio/transactions/{s['id']}", headers=auth_headers).status_code
        == 204
    )
    assert (
        client.delete(f"/api/portfolio/transactions/{b['id']}", headers=auth_headers).status_code
        == 204
    )
    assert holdings(db) == []


def test_users_and_goals_are_private(client, auth_headers, funds):
    other = login_headers(client, "other@example.com")
    their_goal = make_goal(client, other)
    txn(client, auth_headers, funds["equity"], amount=1000, goal_id=their_goal, expect=404)
    theirs = txn(client, other, funds["equity"], amount=1000)
    assert (
        client.delete(
            f"/api/portfolio/transactions/{theirs['id']}", headers=auth_headers
        ).status_code
        == 404
    )
    assert client.get("/api/portfolio/transactions", headers=auth_headers).json() == []
    assert client.get(f"/api/portfolio/goals/{their_goal}", headers=auth_headers).status_code == 404


# --- SIPs, unit changes, rebuilds -------------------------------------------------------------


def test_sip_records_monthly_instalments_and_xirr(client, db, auth_headers, funds):
    goal_id = make_goal(client, auth_headers)
    start = START + timedelta(days=5)
    end = start + timedelta(days=740)  # 25 instalments: months 0 to 24
    response = client.post(
        "/api/portfolio/transactions/sip",
        json={"fund_id": funds["equity"].id, "goal_id": goal_id, "amount": 5000,
              "start_date": start.isoformat(), "end_date": end.isoformat()},
        headers=auth_headers,
    )  # fmt: skip
    assert response.status_code == 201, response.text
    created = response.json()
    assert len(created) == 25
    assert {t["note"] for t in created} == {"SIP"} and {t["goal_id"] for t in created} == {goal_id}

    [(g, _, units, cost, _)] = holdings(db)
    assert g == goal_id and cost == Decimal("125000.00")
    assert float(units) == pytest.approx(sum(t["units"] for t in created), abs=1e-6)
    status = client.get("/api/portfolio", headers=auth_headers).json()["goals"][0]
    assert status["xirr"] == pytest.approx(12.0, abs=0.1)
    assert status["status"] in {"on_track", "off_track"}


def test_sip_needs_navs_for_every_instalment(client, auth_headers, funds):
    response = client.post(
        "/api/portfolio/transactions/sip",
        json={"fund_id": funds["equity"].id, "amount": 1000,
              "start_date": (START - timedelta(days=60)).isoformat()},
        headers=auth_headers,
    )  # fmt: skip
    assert response.status_code == 422 and "no NAV" in response.json()["detail"]


def test_units_bought_before_a_unit_change_are_restated(client, db, auth_headers, funds):
    fund = funds["split"]
    day = first_weekday_on_or_after(START + timedelta(days=100))
    body = txn(client, auth_headers, fund, day=day, amount=10_000)
    assert body["nav"] == pytest.approx(round(nav_on(10, 0.06, day), 4))  # old ₹10 units
    [(_, _, units, _, _)] = holdings(db)
    assert float(units) == pytest.approx(body["units"] / 100, abs=1e-6)  # in today's units
    holding = client.get("/api/portfolio", headers=auth_headers).json()["holdings"][0]
    assert holding["xirr"] == pytest.approx(6.0, abs=0.05)  # no fake -99% from the change

    progress = client.get("/api/portfolio/transactions", headers=auth_headers).json()
    assert progress[0]["units"] == body["units"]  # the transaction keeps the statement's units


def test_materialised_holdings_equal_a_full_rebuild(client, db, auth_headers, funds):
    goal_id = make_goal(client, auth_headers)
    for i, key in enumerate(["equity", "debt", "equity", "split"]):
        txn(client, auth_headers, funds[key], day=START + timedelta(days=20 + 50 * i),
            amount=10_000 + i, goal_id=goal_id if i % 2 else None)  # fmt: skip
    b = txn(client, auth_headers, funds["debt"], day=START + timedelta(days=300), amount=7000)
    txn(
        client,
        auth_headers,
        funds["debt"],
        kind="sell",
        day=START + timedelta(days=500),
        amount=3000,
    )
    assert b["units"] > 0
    stored = sorted(holdings(db), key=str)
    user = db.scalar(select(User).where(User.email == "user@example.com"))
    service.rebuild_user(db, user.id)
    assert sorted(holdings(db), key=str) == stored


def test_deleting_a_goal_releases_its_transactions(client, db, auth_headers, funds):
    goal_id = make_goal(client, auth_headers)
    txn(client, auth_headers, funds["equity"], amount=10_000, goal_id=goal_id)
    txn(client, auth_headers, funds["equity"], day=START + timedelta(days=40), amount=5000)
    [g1, g2] = sorted(holdings(db), key=lambda h: h[0] is None)
    assert client.delete(f"/api/goals/{goal_id}", headers=auth_headers).status_code == 204
    [(goal, _, units, cost, _)] = holdings(db)
    assert goal is None
    assert units == g1[2] + g2[2] and cost == g1[3] + g2[3]
    assert db.scalar(select(func.count()).select_from(Transaction)) == 2


# --- Goal status, drift and progress ----------------------------------------------------------


def recommend_mix(db, goal_id, weights, years):
    db.add(
        Recommendation(
            goal_id=goal_id, as_of=LATEST, risk_category="moderate", years_to_goal=years,
            equity_share=0.6, expected_return=0.1, volatility=0.1,
            allocation=[{"sleeve": s, "label": s, "weight": w} for s, w in weights.items()],
            funds=[], reasons=[], inputs={},
            created_at=datetime.now(UTC),
        )
    )  # fmt: skip
    db.commit()


def test_drift_alerts_and_trades(client, db, auth_headers, funds):
    goal_id = make_goal(client, auth_headers, target_amount=100_000, monthly_sip=0)
    txn(client, auth_headers, funds["equity"], amount=60_000, goal_id=goal_id)
    txn(client, auth_headers, funds["debt"], amount=40_000, goal_id=goal_id)

    body = client.get("/api/portfolio", headers=auth_headers).json()
    assert [a["kind"] for a in body["alerts"]] == ["no_recommendation"]
    assert body["goals"][0]["rebalance_needed"] is None

    recommend_mix(db, goal_id, {"large_cap": 30, "long_debt": 70}, years=10)
    body = client.get("/api/portfolio", headers=auth_headers).json()
    status = body["goals"][0]
    assert status["status"] == "on_track"  # ₹1 lakh target, well funded
    assert status["rebalance_needed"] is True
    assert status["equity_target"] == 30
    assert status["equity_actual"] > 60  # equity grew faster than bonds
    assert [a["kind"] for a in body["alerts"]] == ["rebalance"]
    assert body["alerts"][0]["message"].startswith("Equity is 6")  # the equity share drifted

    progress = client.get(f"/api/portfolio/goals/{goal_id}", headers=auth_headers).json()
    rows = {r["row"]: r for r in progress["rebalance"]["rows"]}
    assert rows["large_cap"]["trade"] < 0 < rows["long_debt"]["trade"]
    assert rows["large_cap"]["trade"] + rows["long_debt"]["trade"] == pytest.approx(0, abs=100)
    assert progress["rebalance"]["threshold"] == 5


def test_off_track_and_stale_recommendation_alerts(client, db, auth_headers, funds):
    goal_id = make_goal(client, auth_headers, target_amount=50_000_000, monthly_sip=1000)
    txn(client, auth_headers, funds["equity"], amount=10_000, goal_id=goal_id)
    recommend_mix(db, goal_id, {"large_cap": 100}, years=12)  # made when 12 years away
    alerts = client.get("/api/portfolio", headers=auth_headers).json()["alerts"]
    kinds = [a["kind"] for a in alerts]
    assert kinds == ["off_track", "stale_recommendation"]  # warnings first
    assert "would close the gap" in alerts[0]["message"]


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (0, "₹0"),
        (999, "₹999"),
        (874_512, "₹8,74,512"),
        (12_345_678.4, "₹1,23,45,678"),
        (-1500, "−₹1,500"),
    ],
)
def test_rupees_use_indian_grouping(amount, text):
    assert inr(amount) == text


def test_goal_progress_history_and_projection(client, auth_headers, funds):
    goal_id = make_goal(client, auth_headers, target_year=THIS_YEAR + 5)
    response = client.post(
        "/api/portfolio/transactions/sip",
        json={"fund_id": funds["equity"].id, "goal_id": goal_id, "amount": 10_000,
              "start_date": (START + timedelta(days=3)).isoformat()},
        headers=auth_headers,
    )  # fmt: skip
    assert response.status_code == 201
    progress = client.get(f"/api/portfolio/goals/{goal_id}", headers=auth_headers).json()
    history, status = progress["history"], progress["status"]
    assert len(history) >= 36
    assert history[-1]["date"] == LATEST.isoformat()
    assert history[-1]["value"] == pytest.approx(status["value"], rel=1e-6)
    assert history[-1]["invested"] == pytest.approx(status["cost"])
    # The fund earned 12% against the plan's 10%: ahead of plan.
    assert status["expected_return"] == 10 and status["vs_plan"] > 0
    assert history[-1]["plan"] == pytest.approx(status["plan_value"], abs=0.01)
    assert len(progress["projection"]) == 6  # today + 5 years
    assert progress["target"]["value"] == status["inflated_target"]
    assert progress["projection"][-1]["value"] == pytest.approx(status["projected_value"], rel=0.01)
    assert progress["holdings"][0]["goal_name"] == "College"
