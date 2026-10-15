"""Unit tests for the time-value-of-money formulas (no database).

Expected values were calculated by hand / with a month-by-month loop and are listed in the
Phase 3 document, so the tables can be copied into the report.
"""

import pytest

from app.finance import tvm
from app.finance.tvm import FinanceInputError

RUPEE = 0.01  # results must match to the paisa


def simulate_sip(monthly: float, annual_rate: float, months: int, step_up: float = 0.0) -> float:
    """Independent check: invest at the start of each month, then grow for one month."""
    i = (1 + annual_rate) ** (1 / 12) - 1
    value, amount = 0.0, monthly
    for month in range(months):
        if month and month % 12 == 0:
            amount *= 1 + step_up
        value = (value + amount) * (1 + i)
    return value


# --- Rates ------------------------------------------------------------------------------------


def test_monthly_rate_compounds_back_to_the_annual_rate():
    i = tvm.monthly_rate(0.12)
    assert i == pytest.approx(0.009488793, abs=1e-9)  # not 0.01 (= 12 / 12)
    assert (1 + i) ** 12 - 1 == pytest.approx(0.12)


def test_real_return_uses_fisher_not_subtraction():
    assert tvm.real_return(0.12, 0.06) == pytest.approx(0.0566038, abs=1e-7)  # not 0.06


def test_cagr_doubling_in_six_years():
    assert tvm.cagr(100_000, 200_000, 6) == pytest.approx(0.1224620, abs=1e-7)  # "rule of 72"


@pytest.mark.parametrize(
    "start, end, years", [(0, 100, 5), (-1, 100, 5), (100, -1, 5), (100, 200, 0)]
)
def test_cagr_rejects_meaningless_input(start, end, years):
    with pytest.raises(FinanceInputError):
        tvm.cagr(start, end, years)


# --- Lump sums --------------------------------------------------------------------------------


def test_future_value_of_lump_sum():
    # ₹1,00,000 at 10% for 10 years = 1,00,000 x 1.1^10
    assert tvm.future_value(100_000, 0.10, 10) == pytest.approx(259_374.25, abs=RUPEE)


def test_present_value_of_future_amount():
    # ₹10,00,000 needed in 10 years, discounted at 8%
    assert tvm.present_value(1_000_000, 0.08, 10) == pytest.approx(463_193.49, abs=RUPEE)


def test_present_and_future_value_are_inverses():
    assert tvm.present_value(tvm.future_value(12_345, 0.09, 7), 0.09, 7) == pytest.approx(12_345)


def test_inflate_goal_cost():
    # ₹20 lakh of education today, 10% education inflation, 15 years
    assert tvm.inflate(2_000_000, 0.10, 15) == pytest.approx(8_354_496.34, abs=RUPEE)


def test_zero_years_changes_nothing():
    assert tvm.future_value(50_000, 0.12, 0) == 50_000


def test_lump_sum_rejects_meaningless_input():
    with pytest.raises(FinanceInputError):
        tvm.future_value(1, 0.1, -1)  # negative period
    with pytest.raises(FinanceInputError):
        tvm.monthly_rate(-1)  # -100% a year


# --- SIPs -------------------------------------------------------------------------------------


def test_sip_future_value_matches_worked_example():
    # ₹10,000 a month for 10 years at 12% a year
    assert tvm.sip_future_value(10_000, 0.12, 120) == pytest.approx(2_240_358.90, abs=RUPEE)


@pytest.mark.parametrize("rate, months", [(0.12, 120), (0.08, 37), (0.15, 1), (0.05, 360)])
def test_sip_formula_matches_month_by_month_simulation(rate, months):
    assert tvm.sip_future_value(7_500, rate, months) == pytest.approx(
        simulate_sip(7_500, rate, months)
    )


def test_sip_at_zero_return_is_just_the_total_invested():
    assert tvm.sip_future_value(10_000, 0.0, 120) == 1_200_000


def test_sip_is_an_annuity_due():
    """Invested at the start of the month: one month in, the first instalment has grown."""
    assert tvm.sip_future_value(10_000, 0.12, 1) == pytest.approx(10_094.89, abs=RUPEE)


def test_step_up_sip_matches_simulation():
    # ₹5,000 a month, raised 10% every year, for 10 years at 12%
    value = tvm.step_up_sip_future_value(5_000, 0.12, 10, 0.10)
    assert value == pytest.approx(1_634_449.24, abs=RUPEE)
    assert value == pytest.approx(simulate_sip(5_000, 0.12, 120, step_up=0.10))


def test_step_up_of_zero_equals_flat_sip():
    assert tvm.step_up_sip_future_value(5_000, 0.12, 10, 0.0) == pytest.approx(
        tvm.sip_future_value(5_000, 0.12, 120)
    )


# --- Required SIP -----------------------------------------------------------------------------


def test_required_sip_worked_example():
    # Education goal: ₹83,54,496 in 15 years at 12%, with ₹2,00,000 already saved
    sip = tvm.required_sip(8_354_496.34, 0.12, 180, current_savings=200_000)
    assert sip == pytest.approx(15_253.84, abs=RUPEE)


def test_required_sip_reaches_the_target_exactly():
    sip = tvm.required_sip(5_000_000, 0.10, 240, current_savings=300_000)
    reached = tvm.sip_future_value(sip, 0.10, 240) + tvm.future_value(300_000, 0.10, 20)
    assert reached == pytest.approx(5_000_000)


def test_required_sip_is_zero_when_savings_are_enough():
    assert tvm.required_sip(100_000, 0.08, 60, current_savings=100_000) == 0


def test_required_sip_without_return():
    assert tvm.required_sip(120_000, 0.0, 12) == pytest.approx(10_000)


def test_required_sip_when_no_time_left():
    with pytest.raises(FinanceInputError):
        tvm.required_sip(100_000, 0.08, 0)


def test_required_step_up_sip_reaches_the_target():
    start = tvm.required_step_up_sip(5_000_000, 0.12, 15, 0.10, current_savings=100_000)
    reached = tvm.step_up_sip_future_value(start, 0.12, 15, 0.10) + tvm.future_value(
        100_000, 0.12, 15
    )
    assert reached == pytest.approx(5_000_000)
    # Stepping up lets you start lower than a flat SIP.
    assert start < tvm.required_sip(5_000_000, 0.12, 180, current_savings=100_000)
