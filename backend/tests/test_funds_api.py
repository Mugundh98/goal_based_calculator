"""API tests for the fund explorer and market data (real test database)."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.api.routes import market as market_routes
from app.data_pipeline import jobs
from app.models import Fund, FundMetrics, IndexHistory, JobRun, NavHistory, User
from tests.conftest import login_headers
from tests.pipeline_samples import CPI_RECORDS, NAV_ALL

METRIC_DEFAULTS = {
    "as_of_date": date(2026, 10, 15),
    "history_start": date(2016, 1, 1),
    "risk_free_rate": 6.0,
    "computed_at": datetime(2026, 10, 15, tzinfo=UTC),
}


@pytest.fixture
def market(db):
    """Seven funds from the sample AMFI file (one closed in 2017), two with metrics."""
    jobs.daily_nav(db, text=NAV_ALL)
    ids = dict(db.execute(select(Fund.scheme_code, Fund.id)).all())
    db.add_all(
        [
            FundMetrics(fund_id=ids[120465], return_1y=8.0, return_3y=15.0, volatility=14.2,
                        sharpe=0.9, max_drawdown=-12.5, **METRIC_DEFAULTS),
            FundMetrics(fund_id=ids[120716], return_1y=9.0, return_3y=10.0, volatility=13.0,
                        sharpe=0.7, max_drawdown=-14.0, **METRIC_DEFAULTS),
            NavHistory(fund_id=ids[120465], nav_date=date(2020, 10, 15), nav=Decimal("30")),
            NavHistory(fund_id=ids[120465], nav_date=date(2025, 12, 1), nav=Decimal("55")),
            IndexHistory(symbol="^NSEI", trade_date=date(2025, 10, 15), close=Decimal(20000)),
            IndexHistory(symbol="^NSEI", trade_date=date(2026, 10, 15), close=Decimal(25000)),
        ]
    )  # fmt: skip
    db.commit()
    jobs.inflation(db, records=CPI_RECORDS)
    return ids


def names(response):
    return [item["name"] for item in response.json()["items"]]


def test_market_data_requires_login(client):
    for path in ("/api/funds", "/api/funds/categories", "/api/funds/1", "/api/funds/1/nav",
                 "/api/market/summary", "/api/market/inflation", "/api/market/jobs"):  # fmt: skip
        assert client.get(path).status_code == 401, path


def test_list_hides_closed_funds_by_default(client, auth_headers, market):
    page = client.get("/api/funds", headers=auth_headers).json()
    assert page["total"] == 6  # the 2017 fixed maturity plan has matured
    assert (page["page"], page["page_size"]) == (1, 25)
    everything = client.get("/api/funds", params={"active_only": False}, headers=auth_headers)
    assert everything.json()["total"] == 7


def test_list_item_shape(client, auth_headers, market):
    item = client.get("/api/funds", params={"q": "120465"}, headers=auth_headers).json()["items"][0]
    assert item["name"] == "Axis Large Cap Fund"
    assert (item["plan"], item["option"], item["asset_class"]) == ("direct", "growth", "equity")
    assert item["latest_nav"] == 62.15 and item["latest_nav_date"] == "2026-10-15"
    assert (item["return_3y"], item["sharpe"], item["max_drawdown"]) == (15.0, 0.9, -12.5)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"q": "axis"}, 3),
        ({"q": "HDFC liquid"}, 2),  # case-insensitive
        ({"q": "UTI Mutual"}, 1),  # fund house
        ({"q": "120465"}, 1),  # scheme code
        ({"q": "%"}, 0),  # a literal %, not a wildcard
        ({"asset_class": "debt"}, 2),
        ({"category": "Large Cap Fund"}, 3),
        ({"plan": "direct", "option": "growth"}, 3),
        ({"asset_class": "equity", "plan": "regular"}, 1),
    ],
)
def test_search_and_filters(client, auth_headers, market, params, expected):
    response = client.get("/api/funds", params=params, headers=auth_headers)
    assert response.json()["total"] == expected


def test_sort_by_metric_puts_funds_without_it_last(client, auth_headers, market):
    desc = client.get(
        "/api/funds", params={"sort": "return_3y", "order": "desc"}, headers=auth_headers
    )
    assert names(desc)[:2] == ["Axis Large Cap Fund", "UTI Nifty 50 Index Fund"]
    asc = client.get(
        "/api/funds", params={"sort": "return_3y", "order": "asc"}, headers=auth_headers
    )
    assert names(asc)[:2] == ["UTI Nifty 50 Index Fund", "Axis Large Cap Fund"]
    assert all(item["return_3y"] is None for item in asc.json()["items"][2:])

    dd = client.get(
        "/api/funds", params={"sort": "max_drawdown", "order": "desc"}, headers=auth_headers
    )
    assert names(dd)[0] == "Axis Large Cap Fund"  # -12.5% is the smaller fall


def test_pagination_is_stable(client, auth_headers, market):
    pages = [
        client.get("/api/funds", params={"page": n, "page_size": 4}, headers=auth_headers).json()
        for n in (1, 2)
    ]
    assert [len(p["items"]) for p in pages] == [4, 2]
    ids = [item["id"] for p in pages for item in p["items"]]
    assert len(set(ids)) == 6  # no fund twice, none missing


@pytest.mark.parametrize(
    "params",
    [{"sort": "nav_history"}, {"order": "up"}, {"page": 0}, {"page_size": 101},
     {"asset_class": "crypto"}, {"q": "x" * 101}],
)  # fmt: skip
def test_invalid_list_parameters(client, auth_headers, market, params):
    assert client.get("/api/funds", params=params, headers=auth_headers).status_code == 422


def test_categories(client, auth_headers, market):
    rows = client.get("/api/funds/categories", headers=auth_headers).json()
    assert {"asset_class": "equity", "category": "Large Cap Fund", "count": 3} in rows
    assert not any(row["category"] == "Fixed Term Plan" for row in rows)  # only active funds


def test_fund_detail(client, auth_headers, market):
    fund = client.get(f"/api/funds/{market[120465]}", headers=auth_headers).json()
    assert fund["amc"] == "Axis Mutual Fund" and fund["scheme_type"] == "Open Ended"
    assert fund["is_active"] is True and fund["benchmark"] == "^NSEI"
    assert fund["metrics"]["return_3y"] == 15.0 and fund["metrics"]["risk_free_rate"] == 6.0

    closed = client.get(f"/api/funds/{market[128111]}", headers=auth_headers).json()
    assert closed["is_active"] is False and closed["metrics"] is None


def test_fund_detail_not_found(client, auth_headers):
    assert client.get("/api/funds/999999", headers=auth_headers).status_code == 404
    assert client.get("/api/funds/999999/nav", headers=auth_headers).status_code == 404


def test_nav_history_periods(client, auth_headers, market):
    url = f"/api/funds/{market[120465]}/nav"
    every = client.get(url, params={"period": "max"}, headers=auth_headers).json()
    assert [p["date"] for p in every["points"]] == ["2020-10-15", "2025-12-01", "2026-10-15"]
    one_year = client.get(url, params={"period": "1y"}, headers=auth_headers).json()
    assert [p["value"] for p in one_year["points"]] == [55.0, 62.15]  # from 15 Oct 2025
    assert client.get(url, params={"period": "2w"}, headers=auth_headers).status_code == 422


def test_nav_history_restates_face_value_changes(client, auth_headers, market, db):
    """Units ten times larger until December 2025 (NAV ~540), today's units after (NAV ~55):
    the chart shows the whole period in today's units."""
    fund_id = market[120465]
    db.add(NavHistory(fund_id=fund_id, nav_date=date(2025, 10, 20), nav=Decimal("540")))
    db.add(NavHistory(fund_id=fund_id, nav_date=date(2025, 11, 3), nav=Decimal("545")))
    db.commit()  # the fixture's 55 on 1 Dec 2025 is then the first NAV in the new units
    body = client.get(f"/api/funds/{fund_id}/nav", params={"period": "1y"}, headers=auth_headers)
    body = body.json()
    assert body["unit_changes"] == [{"date": "2025-12-01", "factor": 0.1}]
    assert [round(p["value"], 2) for p in body["points"]] == [54.0, 54.5, 55.0, 62.15]
    # The stored NAVs are untouched: they are what AMFI published.
    stored = db.scalar(select(NavHistory.nav).where(NavHistory.nav_date == date(2025, 10, 20)))
    assert stored == Decimal("540")


def test_market_summary(client, auth_headers, market, db):
    jobs.run_job("daily_nav", db=db, text=NAV_ALL)
    summary = client.get("/api/market/summary", headers=auth_headers).json()
    assert (summary["fund_count"], summary["active_fund_count"]) == (7, 6)
    assert summary["funds_with_metrics"] == 2
    assert summary["latest_nav_date"] == "2026-10-15"
    nifty = summary["indices"][0]
    assert (nifty["name"], nifty["latest_close"], nifty["return_1y"]) == ("Nifty 50", 25000, 25.0)
    assert summary["indices"][1]["latest_close"] is None  # no data loaded for it
    assert summary["latest_inflation"] == {
        "period": "2025-12-01",
        "cpi": 198.0,
        "inflation_yoy": 1.33,
    }
    assert [run["job_name"] for run in summary["last_runs"]] == ["daily_nav"]


def test_index_history(client, auth_headers, market):
    response = client.get(
        "/api/market/indices/^NSEI/history", params={"start": "2026-01-01"}, headers=auth_headers
    )
    assert response.json() == {
        "symbol": "^NSEI",
        "name": "Nifty 50",
        "points": [{"date": "2026-10-15", "value": 25000.0}],
    }
    assert client.get("/api/market/indices/AAPL/history", headers=auth_headers).status_code == 404


def test_inflation_endpoint(client, auth_headers, market):
    body = client.get("/api/market/inflation", headers=auth_headers).json()
    assert body["base_year"] == 2012
    assert [p["period"] for p in body["points"]][-2:] == ["2025-11-01", "2025-12-01"]


def test_job_log_newest_first(client, auth_headers, db):
    jobs.run_job("inflation", db=db, records=CPI_RECORDS)
    jobs.run_job("daily_nav", db=db, text=NAV_ALL)
    runs = client.get("/api/market/jobs", headers=auth_headers).json()
    assert [r["job_name"] for r in runs] == ["daily_nav", "inflation"]
    assert runs[0]["status"] == "success" and runs[0]["rows_written"] == 7
    only = client.get("/api/market/jobs", params={"job_name": "inflation"}, headers=auth_headers)
    assert len(only.json()) == 1


def test_only_admins_can_start_jobs(client, db, monkeypatch):
    started = []
    monkeypatch.setattr(market_routes, "run_job", lambda *args: started.append(args))

    user = login_headers(client, "user@example.com")
    assert client.post("/api/market/jobs/daily_nav/run", headers=user).status_code == 403

    admin = login_headers(client, "admin@example.com")
    db.scalar(select(User).where(User.email == "admin@example.com")).role = "admin"
    db.commit()
    response = client.post("/api/market/jobs/daily_nav/run", headers=admin)
    assert response.status_code == 202
    assert started == [("daily_nav", "admin")]  # ran as a background task
    assert client.post("/api/market/jobs/nope/run", headers=admin).status_code == 404
    assert db.scalar(select(JobRun)) is None  # (the real job was replaced in this test)
