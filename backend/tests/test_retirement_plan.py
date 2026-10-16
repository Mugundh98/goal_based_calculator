"""Unit tests for the retirement formulas (no database).

Expected values come from hand calculations or independent month-by-month loops; the worked
example is the one in the Phase 6 document.
"""

from dataclasses import replace

import pytest

from app.finance import tvm
from app.finance.retirement import (
    RetirementInputs,
    corpus_needed,
    drawdown,
    first_monthly_withdrawal,
    plan_retirement,
    sustainable_withdrawal_rate,
    withdrawal_amount,
)
from app.finance.tvm import FinanceInputError

RUPEE = 0.01

# Worked example: 34 today, retire at 60, plan to 85, ₹40,000 a month in today's money.
EXAMPLE = RetirementInputs(
    current_age=34,
    retirement_age=60,
    life_expectancy=85,
    monthly_expense=40_000,
    inflation_rate=0.06,
    pre_retirement_return=0.10,
    post_retirement_return=0.08,
    current_savings=500_000,
    monthly_sip=10_000,
)


def pv_by_loop(first: float, growth: float, annual_rate: float, years: int) -> float:
    """Independent check: discount every single monthly payment back to the start."""
    i = (1 + annual_rate) ** (1 / 12) - 1
    return sum(
        first * (1 + growth) ** (month // 12) / (1 + i) ** month for month in range(years * 12)
    )


# --- Present value formulas -----------------------------------------------------------------------


def test_annuity_due_present_factor():
    # 12 payments of ₹1 at 1% a month, first one today: (1 - 1.01^-12) / 0.01 x 1.01
    assert tvm.annuity_due_present_factor(0.01, 12) == pytest.approx(11.36763, abs=1e-5)
    assert tvm.annuity_due_present_factor(0.0, 12) == 12


@pytest.mark.parametrize(
    "growth, rate, years", [(0.06, 0.08, 25), (0.06, 0.06, 20), (0.10, 0.07, 30), (0.0, 0.09, 1)]
)
def test_growing_annuity_matches_payment_by_payment_discounting(growth, rate, years):
    assert tvm.present_value_growing_annuity(1_000, growth, rate, years) == pytest.approx(
        pv_by_loop(1_000, growth, rate, years)
    )


def test_growing_annuity_when_growth_equals_return():
    """q = 1: every year's payments are worth the same today, so PV = one year x years."""
    one_year = 1_000 * tvm.annuity_due_present_factor(tvm.monthly_rate(0.06), 12)
    assert tvm.present_value_growing_annuity(1_000, 0.06, 0.06, 20) == pytest.approx(one_year * 20)


def test_growing_annuity_without_growth_is_a_plain_annuity():
    assert tvm.present_value_growing_annuity(1_000, 0.0, 0.08, 2) == pytest.approx(
        1_000 * tvm.annuity_due_present_factor(tvm.monthly_rate(0.08), 24)
    )


# --- Corpus -------------------------------------------------------------------------------------


def test_worked_example_corpus():
    # ₹40,000 grown by 6% for 26 years = 40,000 x 1.06^26
    assert first_monthly_withdrawal(EXAMPLE) == pytest.approx(181_975.32, abs=RUPEE)
    assert corpus_needed(EXAMPLE) == pytest.approx(42_505_424.85, abs=RUPEE)


def test_exact_corpus_lasts_exactly_until_life_expectancy():
    first, corpus = first_monthly_withdrawal(EXAMPLE), corpus_needed(EXAMPLE)
    balances, ran_out = drawdown(corpus, first, 0.06, 0.08, 25)
    assert ran_out is None
    assert len(balances) == 25
    assert balances[-1] == pytest.approx(0, abs=1)  # the last withdrawal empties it
    # 1% less money runs out in the final year.
    _, short = drawdown(corpus * 0.99, first, 0.06, 0.08, 25)
    assert 24 <= short < 25


def test_withdrawals_rise_once_a_year():
    assert withdrawal_amount(100, 0.06, 0) == withdrawal_amount(100, 0.06, 11) == 100
    assert withdrawal_amount(100, 0.06, 12) == pytest.approx(106)
    assert withdrawal_amount(100, 0.06, 24) == pytest.approx(112.36)


def test_higher_return_or_lower_inflation_needs_a_smaller_corpus():
    base = corpus_needed(EXAMPLE)
    assert corpus_needed(replace(EXAMPLE, post_retirement_return=0.09)) < base
    assert corpus_needed(replace(EXAMPLE, inflation_rate=0.05)) < base
    assert corpus_needed(replace(EXAMPLE, life_expectancy=90)) > base


# --- The full plan ----------------------------------------------------------------------------


def test_worked_example_plan():
    p = plan_retirement(EXAMPLE)
    assert p.first_monthly_withdrawal == 181_975.32
    assert p.corpus_needed == 42_505_424.85
    assert p.corpus_multiple == 19.46  # corpus = 19.46 x the first year's spending
    assert p.withdrawal_rate == pytest.approx(0.051375, abs=1e-6)
    a = p.accumulation
    assert a.savings_value == pytest.approx(5_959_088.27)  # 5 lakh x 1.10^26
    assert a.sip_value == pytest.approx(13_801_161.03)
    assert a.projected_value == pytest.approx(19_760_249.30)
    assert a.funded_percent == 46.4
    assert a.required_sip == 26_481
    assert p.money_lasts_until == 70.2  # the projected ₹1.98 Cr runs out at 70


def test_corpus_multiple_and_withdrawal_rate_are_reciprocals():
    p = plan_retirement(EXAMPLE)
    assert p.corpus_multiple * p.withdrawal_rate == pytest.approx(1, abs=1e-3)


def test_lifetime_covers_every_age_once():
    p = plan_retirement(EXAMPLE)
    assert [y.age for y in p.lifetime] == list(range(34, 86))
    assert [y.year for y in p.lifetime] == list(range(0, 52))
    assert p.lifetime[0].balance == 500_000
    assert p.lifetime[26].balance == pytest.approx(19_760_249.30)  # at retirement
    assert {y.phase for y in p.lifetime[:27]} == {"accumulation"}
    assert {y.phase for y in p.lifetime[27:]} == {"retirement"}
    assert p.lifetime[-1].balance == 0  # ran out at 70


def test_investing_the_required_sip_makes_the_money_last():
    required = plan_retirement(EXAMPLE).accumulation.required_sip
    p = plan_retirement(replace(EXAMPLE, monthly_sip=required))
    assert p.accumulation.on_track
    assert p.money_lasts_until is None


def test_step_up_lowers_the_starting_sip():
    flat = plan_retirement(EXAMPLE).accumulation.required_sip
    stepped = plan_retirement(replace(EXAMPLE, step_up_rate=0.10)).accumulation.required_sip
    assert stepped < flat


def test_savings_already_enough():
    p = plan_retirement(replace(EXAMPLE, current_savings=10_000_000))
    assert p.accumulation.required_sip == 0
    assert p.money_lasts_until is None


@pytest.mark.parametrize(
    "changes",
    [
        {"retirement_age": 34},  # not after the current age
        {"retirement_age": 30},
        {"life_expectancy": 60},  # not after retirement
    ],
)
def test_impossible_ages_rejected(changes):
    with pytest.raises(FinanceInputError):
        replace(EXAMPLE, **changes)


# --- Withdrawal rates and the 4% rule -------------------------------------------------------------


def test_sustainable_withdrawal_rate():
    # India-like: 6% inflation, 8% return, 30 years -> 4.47% (close to Bengen's 4%) ...
    assert sustainable_withdrawal_rate(0.06, 0.08, 30) == pytest.approx(0.044682, abs=1e-6)
    # ... but only 3.93% if the corpus earns just 1% more than inflation, as in a debt-heavy mix.
    assert sustainable_withdrawal_rate(0.06, 0.07, 30) < 0.04
    # Without growth or return: exactly 1/30 of the corpus a year.
    assert sustainable_withdrawal_rate(0.0, 0.0, 30) == pytest.approx(1 / 30)
