"""Unit tests for the portfolio maths: XIRR, FIFO holdings and drift (no database)."""

import random
from datetime import date
from decimal import Decimal

import pytest

from app.finance import tvm
from app.finance.xirr import xirr, xnpv
from app.portfolio.ledger import Entry, InsufficientUnits, replay, units_for
from app.portfolio.tracking import grown_contributions, rebalance, sleeve_of

# --- XIRR ------------------------------------------------------------------------------------


def test_xirr_matches_excel_documentation_example():
    # The example in Microsoft's XIRR documentation; Excel returns 0.373362535 (37.34%).
    flows = [
        (date(2008, 1, 1), -10000),
        (date(2008, 3, 1), 2750),
        (date(2008, 10, 30), 4250),
        (date(2009, 2, 15), 3250),
        (date(2009, 4, 1), 2750),
    ]
    result = xirr(flows)
    assert result is not None and result.method == "newton"
    assert result.rate == pytest.approx(0.373362535, abs=1e-8)
    assert xnpv(result.rate, flows) == pytest.approx(0, abs=1e-6)


def test_lump_sum_xirr_equals_cagr():
    start, end = date(2020, 1, 1), date(2025, 1, 1)
    years = (end - start).days / 365
    result = xirr([(start, -100_000), (end, 161_051)])
    assert result is not None
    assert result.rate == pytest.approx(tvm.cagr(100_000, 161_051, years), abs=1e-9)


def test_sip_xirr_recovers_the_rate_every_instalment_earned():
    end = date(2025, 1, 1)
    instalments = [date(2024, m, 1) for m in range(1, 13)]
    value = sum(1000 * 1.12 ** ((end - d).days / 365) for d in instalments)
    result = xirr([(d, -1000) for d in instalments] + [(end, value)])
    assert result is not None
    assert result.rate == pytest.approx(0.12, abs=1e-8)
    # CAGR on the total invested over the whole year would understate it badly.
    assert tvm.cagr(12_000, value, 1) < 0.07


def test_losses_and_bisection_fallback():
    one_year = [(date(2024, 1, 1), -1000), (date(2024, 12, 31), 500)]  # 365 days
    assert xirr(one_year).rate == pytest.approx(-0.5, abs=1e-9)
    # Newton from 10% overshoots below -100% here; bisection must take over.
    result = xirr([(date(2023, 1, 1), -100), (date(2024, 1, 1), 1)])
    assert result is not None and result.method == "bisection"
    assert result.rate == pytest.approx(-0.99, abs=1e-6)


def test_no_rate_without_flows_of_both_signs_or_time():
    assert xirr([(date(2024, 1, 1), -100), (date(2024, 6, 1), -100)]) is None
    assert xirr([(date(2024, 1, 1), -100), (date(2024, 1, 1), 110)]) is None
    assert xirr([]) is None


# --- FIFO ledger -----------------------------------------------------------------------------


def buy(day, amount, units, i=0):
    return Entry(day, "buy", Decimal(amount), Decimal(units), i)


def sell(day, amount, units, i=0):
    return Entry(day, "sell", Decimal(amount), Decimal(units), i)


def test_fifo_sells_the_oldest_units_first():
    position = replay(
        [
            buy(date(2022, 1, 3), "1000", "100", 1),  # ₹10 a unit
            buy(date(2023, 1, 3), "2000", "100", 2),  # ₹20 a unit
            sell(date(2024, 1, 3), "4500", "150", 3),  # 100 at ₹10 + 50 at ₹20 = ₹2,000 cost
        ]
    )
    assert position.units == Decimal("50")
    assert position.cost == Decimal("1000.00")
    assert position.realised_gain == Decimal("2500.00")
    assert (position.first_date, position.last_date) == (date(2022, 1, 3), date(2024, 1, 3))


def test_order_of_entry_does_not_matter():
    entries = [buy(date(2022, m, 1), str(1000 * m), "100", m) for m in range(1, 7)]
    entries.append(sell(date(2022, 8, 1), "9000", "250", 7))
    expected = replay(entries)
    random.Random(1).shuffle(entries)
    assert replay(entries) == expected


def test_cannot_redeem_units_not_held_on_that_day():
    with pytest.raises(InsufficientUnits, match="only 100.000 units"):
        replay([buy(date(2022, 1, 3), "1000", "100"), sell(date(2022, 2, 1), "2000", "150")])
    # A redemption dated before the purchase is an over-redemption too.
    with pytest.raises(InsufficientUnits):
        replay([buy(date(2022, 3, 1), "1000", "100"), sell(date(2022, 2, 1), "500", "50")])


def test_same_day_purchase_then_redemption_and_rounding_tolerance():
    position = replay(
        [sell(date(2022, 1, 3), "1000.05", "100.0005", 2), buy(date(2022, 1, 3), "1000", "100", 1)]
    )
    assert position.units == 0 and position.cost == 0
    assert position.realised_gain == Decimal("0.05")


def test_units_allotted_after_stamp_duty_to_three_decimals():
    assert units_for(Decimal("10000"), Decimal("10"), "buy", date(2019, 5, 2)) == Decimal("1000")
    # 0.005% stamp duty from July 2020: ₹9,999.50 buys 999.950 units, rounded down.
    assert units_for(Decimal("10000"), Decimal("10"), "buy", date(2021, 5, 3)) == Decimal("999.950")
    assert units_for(Decimal("100"), Decimal("33.3333"), "buy", date(2019, 5, 2)) == Decimal(
        "3.000"
    )
    assert units_for(Decimal("100"), Decimal("33.3333"), "sell", date(2021, 5, 3)) == Decimal(
        "3.000"
    )


# --- Tracking --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "name", "asset_class", "expected"),
    [
        ("Equity Scheme - Large Cap Fund", "", "equity", "large_cap"),
        ("Equity Scheme - Small Cap Fund", "", "equity", "mid_small_cap"),
        ("Debt Scheme - Corporate Bond Fund", "", "debt", "long_debt"),
        ("Debt Scheme - Liquid Fund", "", "debt", "short_debt"),
        ("Equity Scheme - Flexi Cap Fund", "", "equity", "other_equity"),
        ("Hybrid Scheme - Aggressive Hybrid Fund", "", "hybrid", "other"),
        ("Other Scheme - Index Funds", "UTI Nifty 50 Index Fund - Direct", "index", "large_cap"),
        ("Other Scheme - Index Funds", "Motilal Nifty Midcap 150 Index", "index", "mid_small_cap"),
        ("Other Scheme - Index Funds", "Some Nifty 500 Index Fund", "index", "other_equity"),
        ("Other Scheme - Other  ETFs", "Gold ETF", "etf", "other"),
    ],
)
def test_sleeve_of(category, name, asset_class, expected):
    assert sleeve_of(category, name, asset_class) == expected


def test_rebalance_beyond_threshold_with_trades():
    result = rebalance(
        {"large_cap": 60_000, "long_debt": 40_000}, {"large_cap": 0.5, "long_debt": 0.5}
    )
    assert result.needed
    assert result.equity_actual == pytest.approx(0.6)
    trades = {r.row: r.trade for r in result.rows}
    assert trades == pytest.approx({"large_cap": -10_000, "long_debt": 10_000})


def test_no_alert_within_or_at_threshold():
    target = {"large_cap": 0.5, "long_debt": 0.5}
    assert not rebalance({"large_cap": 53, "long_debt": 47}, target).needed
    assert not rebalance({"large_cap": 55, "long_debt": 45}, target).needed  # exactly 5 points


def test_unrecommended_funds_count_as_drift_and_equity():
    result = rebalance(
        {"large_cap": 50, "other_equity": 10, "long_debt": 40}, {"large_cap": 0.6, "long_debt": 0.4}
    )
    assert result.equity_actual == pytest.approx(0.6)  # flexi cap is still equity
    assert result.equity_drift == pytest.approx(0)
    assert result.needed  # but large cap is 10 points under target
    assert {r.row for r in result.rows} == {"large_cap", "other_equity", "long_debt"}


def test_grown_contributions_is_the_plan_value():
    flows = [(date(2024, 1, 1), -1000.0), (date(2024, 7, 1), 200.0)]
    on = date(2024, 12, 31)
    expected = 1000 * 1.1 ** (365 / 365) - 200 * 1.1 ** ((on - date(2024, 7, 1)).days / 365)
    assert grown_contributions(flows, 0.10, on) == pytest.approx(expected)
    assert grown_contributions(flows, 0.10, date(2023, 12, 1)) == 0
