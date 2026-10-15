"""Fund statistics checked against hand calculations (Phase 4 document, section 4)."""

import math
from datetime import date, timedelta

import pytest

from app.finance.fund_metrics import (
    annualised_volatility,
    downside_deviation,
    fund_statistics,
    max_drawdown,
    monthly_returns,
    nav_on_or_before,
    rolling_returns,
    sharpe_ratio,
    shift_months,
    sortino_ratio,
    summarise_rolling,
    trailing_return,
)
from app.finance.tvm import monthly_rate

# --- Dates ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "months", "expected"),
    [
        (date(2026, 10, 15), -36, date(2023, 10, 15)),
        (date(2026, 3, 31), -1, date(2026, 2, 28)),  # no 31 February: last day of the month
        (date(2024, 2, 29), -12, date(2023, 2, 28)),  # leap day a year earlier
        (date(2025, 1, 31), 1, date(2025, 2, 28)),
        (date(2026, 1, 15), -1, date(2025, 12, 15)),  # across a year boundary
    ],
)
def test_shift_months(day, months, expected):
    assert shift_months(day, months) == expected


def test_nav_on_or_before_uses_the_last_published_nav():
    series = [(date(2026, 1, 1), 10.0), (date(2026, 1, 3), 11.0), (date(2026, 1, 6), 12.0)]
    assert nav_on_or_before(series, date(2026, 1, 5)) == (date(2026, 1, 3), 11.0)  # holiday
    assert nav_on_or_before(series, date(2026, 1, 6)) == (date(2026, 1, 6), 12.0)  # exact
    assert nav_on_or_before(series, date(2025, 12, 31)) is None  # before the first NAV


# --- Point-to-point returns -------------------------------------------------------------------

# A fund whose NAV doubled in 5 years. 15 Oct 2023 was a Sunday, so the 3-year start is Friday.
FUND = [
    (date(2021, 10, 15), 100.0),
    (date(2023, 10, 13), 125.0),
    (date(2025, 10, 14), 160.0),
    (date(2026, 10, 15), 200.0),
]


def test_trailing_returns_hand_calculated():
    # 1 year: 200 / 160 - 1 = 25%
    assert trailing_return(FUND, 1) == pytest.approx(0.25)
    # 3 years: start = last NAV on or before 15 Oct 2023 = 125 (13 Oct); 1.6^(1/3) - 1
    assert trailing_return(FUND, 3) == pytest.approx(0.169607, abs=1e-6)
    # 5 years: 2^(1/5) - 1
    assert trailing_return(FUND, 5) == pytest.approx(0.148698, abs=1e-6)


def test_trailing_return_needs_the_full_period():
    assert trailing_return(FUND[1:], 5) is None  # only 3 years old
    assert trailing_return([], 1) is None


# --- Rolling returns --------------------------------------------------------------------------


def test_rolling_returns_hand_calculated():
    series = [
        (date(2020, 1, 1), 100.0),
        (date(2021, 1, 1), 110.0),
        (date(2022, 1, 1), 121.0),
        (date(2022, 6, 1), 99.0),
    ]
    # Windows end on each date with a full year of history before it:
    # 1 Jan 2021: 110/100 = +10%; 1 Jan 2022: 121/110 = +10%;
    # 1 Jun 2022: start = NAV on or before 1 Jun 2021 = 110 -> 99/110 = -10%
    returns = rolling_returns(series, 1)
    assert returns == pytest.approx([0.10, 0.10, -0.10])

    summary = summarise_rolling(returns)
    assert summary.count == 3
    assert summary.average == pytest.approx(0.1 / 3)
    assert (summary.minimum, summary.maximum) == pytest.approx((-0.10, 0.10))
    assert summary.positive_share == pytest.approx(2 / 3)


def test_rolling_returns_empty_when_history_is_too_short():
    assert rolling_returns(FUND[2:], 3) == []
    assert summarise_rolling([]) is None


# --- Monthly returns and risk -----------------------------------------------------------------

# NAV on the 15th of four consecutive months: +10%, -10%, +10%.
MONTHLY = [
    (date(2026, 7, 15), 100.0),
    (date(2026, 8, 14), 105.0),  # mid-month NAVs are ignored: only month-apart samples count
    (date(2026, 8, 15), 110.0),
    (date(2026, 9, 15), 99.0),
    (date(2026, 10, 15), 108.9),
]
RETURNS = [0.10, -0.10, 0.10]


def test_monthly_returns_sampled_one_month_apart_from_the_latest_nav():
    assert monthly_returns(MONTHLY, 3) == pytest.approx(RETURNS)
    assert monthly_returns(MONTHLY, 4) == []  # needs 4 months before 15 Oct


def test_monthly_returns_use_previous_nav_on_holidays():
    # 15 Sep missing (holiday): the 14 Sep NAV is used.
    series = [(date(2026, 8, 15), 100.0), (date(2026, 9, 14), 90.0), (date(2026, 10, 15), 99.0)]
    assert monthly_returns(series, 2) == pytest.approx([-0.10, 0.10])


def test_volatility_hand_calculated():
    # mean = 1/30; squared deviations 0.0044, 0.0178, 0.0044 -> sample variance 1/75
    # sd = 0.11547 a month; x sqrt(12) = sqrt(12/75) = 0.4 exactly
    assert annualised_volatility(RETURNS) == pytest.approx(0.4)
    assert annualised_volatility([0.05]) is None


def test_sharpe_hand_calculated():
    # With a 0% risk-free rate: (1/30) / (1/sqrt(75)) x sqrt(12) = sqrt(900) / 30 = 1.0
    assert sharpe_ratio(RETURNS, 0.0) == pytest.approx(1.0)
    # 12% a year risk-free = 0.948879% a month, subtracted from every month's return
    rf = monthly_rate(0.12)
    expected = (1 / 30 - rf) / (1 / math.sqrt(75)) * math.sqrt(12)
    assert sharpe_ratio(RETURNS, 0.12) == pytest.approx(expected)
    assert expected == pytest.approx(0.7153, abs=1e-4)


def test_sortino_hand_calculated():
    # Only the -10% month is a shortfall: downside deviation = sqrt(0.01 / 3) = 0.057735
    assert downside_deviation(RETURNS, 0.0) == pytest.approx(math.sqrt(0.01 / 3))
    # (1/30) / 0.057735 x sqrt(12) = 2.0 - double the Sharpe ratio: the up months don't count
    assert sortino_ratio(RETURNS, 0.0) == pytest.approx(2.0)


def test_ratios_undefined_without_risk():
    assert sharpe_ratio([0.01, 0.01, 0.01], 0.0) is None  # no variation at all
    assert sortino_ratio([0.01, 0.02, 0.03], 0.0) is None  # never below the risk-free rate


def test_max_drawdown_hand_calculated():
    navs = [100, 120, 90, 130, 65, 140]
    series = [(date(2026, 1, 1) + timedelta(days=k), float(nav)) for k, nav in enumerate(navs)]
    drawdown = max_drawdown(series)
    # 120 -> 90 is -25%, but 130 -> 65 is -50%: the largest fall from any earlier peak
    assert drawdown.depth == pytest.approx(-0.50)
    assert drawdown.peak[1] == 130 and drawdown.trough[1] == 65


def test_max_drawdown_of_a_rising_fund_is_zero():
    series = [(date(2026, 1, k), float(k)) for k in range(1, 6)]
    assert max_drawdown(series).depth == 0


# --- Everything together ----------------------------------------------------------------------


def _daily_series(start: date, days: int, daily_growth: float) -> list:
    return [(start + timedelta(days=k), 10 * (1 + daily_growth) ** k) for k in range(days)]


def test_fund_statistics_for_a_long_steady_fund():
    series = _daily_series(date(2020, 1, 1), 6 * 365, 0.0003)
    stats = fund_statistics(series, risk_free_rate=0.06)
    # Growing 0.03% every calendar day = 1.0003^365 - 1 = 11.57% a year
    assert stats.return_1y == pytest.approx(1.0003**365 - 1, abs=1e-4)
    assert stats.return_5y == pytest.approx(1.0003**365 - 1, abs=1e-3)
    assert stats.rolling_3y.minimum == pytest.approx(stats.rolling_3y.maximum, abs=1e-3)
    assert stats.rolling_1y.positive_share == 1
    assert stats.max_drawdown == 0
    assert stats.volatility == pytest.approx(0, abs=0.01)  # nearly equal monthly returns
    assert stats.history_start == date(2020, 1, 1)


def test_fund_statistics_for_a_young_fund():
    series = _daily_series(date(2026, 1, 1), 200, 0.0003)
    stats = fund_statistics(series, risk_free_rate=0.06)
    assert stats.as_of_date == date(2026, 1, 1) + timedelta(days=199)
    assert stats.return_1y is None and stats.return_3y is None and stats.return_5y is None
    assert stats.rolling_1y is None
    assert stats.volatility is None and stats.sharpe is None and stats.max_drawdown is None


def test_fund_statistics_needs_data():
    with pytest.raises(ValueError):
        fund_statistics([], 0.06)
