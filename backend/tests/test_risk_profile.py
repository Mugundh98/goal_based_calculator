"""Unit tests for the pure risk-profiling rules (no database)."""

from datetime import date
from decimal import Decimal as D

import pytest

from app.finance import risk_profile as rp

ALL_LOWEST = {q.id: q.options[0].id for q in rp.QUESTIONS}
ALL_HIGHEST = {q.id: q.options[-1].id for q in rp.QUESTIONS}


def inputs(**overrides) -> rp.CapacityInputs:
    base = dict(
        age=35,
        employment_type="salaried",
        monthly_income=D("100000"),
        monthly_expenses=D("50000"),
        monthly_emi=D("0"),
        current_savings=D("300000"),
        dependents=0,
    )
    return rp.CapacityInputs(**{**base, **overrides})


def points(factor_key: str, **overrides) -> int:
    factor = next(f for f in rp.capacity_factors(inputs(**overrides)) if f.key == factor_key)
    return factor.points


# --- Questionnaire --------------------------------------------------------------------------


def test_questionnaire_extremes_score_0_and_100():
    assert rp.tolerance_score(ALL_LOWEST) == 0
    assert rp.tolerance_score(ALL_HIGHEST) == 100


def test_questionnaire_middle_answers():
    # objective c=2, experience c=2, drawdown c=2, portfolio c=2, risk_word b=1, equity c=2,
    # knowledge c=2  ->  13 of 28 points = 46.4  ->  46
    answers = {q.id: "c" for q in rp.QUESTIONS} | {"risk_word": "b"}
    assert rp.tolerance_score(answers) == 46


def test_maximum_points_add_up_to_28():
    assert sum(q.max_points for q in rp.QUESTIONS) == 28


def test_missing_answer_is_rejected():
    answers = dict(ALL_LOWEST)
    del answers["knowledge"]
    with pytest.raises(rp.InvalidAnswersError, match="knowledge"):
        rp.tolerance_score(answers)


def test_unknown_question_is_rejected():
    with pytest.raises(rp.InvalidAnswersError, match="favourite_colour"):
        rp.tolerance_score(ALL_LOWEST | {"favourite_colour": "a"})


def test_invalid_option_is_rejected():
    with pytest.raises(rp.InvalidAnswersError, match="risk_word"):
        rp.tolerance_score(ALL_LOWEST | {"risk_word": "e"})  # risk_word only has a-d


# --- Age --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dob, today, expected",
    [
        (date(1990, 6, 15), date(2026, 6, 14), 35),  # day before birthday
        (date(1990, 6, 15), date(2026, 6, 15), 36),  # on birthday
        (date(2000, 2, 29), date(2026, 2, 28), 25),  # leap-day birthday
        (date(2000, 2, 29), date(2026, 3, 1), 26),
    ],
)
def test_age_on(dob, today, expected):
    assert rp.age_on(dob, today) == expected


# --- Capacity factors (boundaries) ------------------------------------------------------------


@pytest.mark.parametrize(
    "age, expected", [(29, 25), (30, 20), (39, 20), (40, 15), (59, 8), (60, 3)]
)
def test_age_points(age, expected):
    assert points("age", age=age) == expected


@pytest.mark.parametrize(
    "expenses, expected",
    [
        ("60000", 20),  # 40% saved
        ("75000", 15),  # 25%
        ("90000", 10),  # 10%
        ("95000", 5),  # 5%
        ("100000", 0),  # nothing saved
        ("120000", 0),  # spending more than earning
    ],
)
def test_savings_rate_points(expenses, expected):
    assert points("savings_rate", monthly_expenses=D(expenses)) == expected


def test_savings_rate_with_no_income_scores_zero():
    assert points("savings_rate", monthly_income=D(0)) == 0


@pytest.mark.parametrize(
    "savings, expected",
    [("300000", 15), ("150000", 10), ("50000", 5), ("49999", 0)],  # 6, 3, 1, <1 months
)
def test_emergency_fund_points(savings, expected):
    assert points("emergency_fund", current_savings=D(savings)) == expected


@pytest.mark.parametrize(
    "emi, expected", [("0", 15), ("19999", 12), ("20000", 6), ("39999", 6), ("40000", 0)]
)
def test_debt_points(emi, expected):
    # expenses lowered so the EMI never makes outgoings exceed income in this test
    assert points("debt_burden", monthly_emi=D(emi), monthly_expenses=D(10000)) == expected


def test_emi_without_income_scores_zero():
    assert points("debt_burden", monthly_income=D(0), monthly_emi=D(5000)) == 0


@pytest.mark.parametrize("dependents, expected", [(0, 10), (1, 6), (2, 6), (3, 2)])
def test_dependents_points(dependents, expected):
    assert points("dependents", dependents=dependents) == expected


def test_factor_maximums_add_up_to_100():
    assert sum(f.max_points for f in rp.capacity_factors(inputs())) == 100


def test_best_possible_capacity_is_100():
    best = inputs(age=25, monthly_expenses=D(20000), current_savings=D(500000))
    assert rp.capacity_score(rp.capacity_factors(best)) == 100


def test_worked_example():
    """The example used in the Phase 2 document."""
    example = inputs(
        age=34,
        employment_type="salaried",
        monthly_income=D("120000"),
        monthly_expenses=D("60000"),
        monthly_emi=D("25000"),
        current_savings=D("300000"),
        dependents=2,
    )
    factors = {f.key: (f.value, f.points) for f in rp.capacity_factors(example)}
    assert factors == {
        "age": ("34 years", 20),
        "savings_rate": ("29%", 15),
        "emergency_fund": ("3.5 months", 10),
        "debt_burden": ("21%", 6),
        "dependents": ("2", 6),
        "employment": ("salaried", 15),
    }
    assert rp.capacity_score(rp.capacity_factors(example)) == 72


# --- Combining --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score, category",
    [
        (0, "conservative"),
        (39, "conservative"),
        (40, "moderate"),
        (69, "moderate"),
        (70, "aggressive"),
        (100, "aggressive"),
    ],
)
def test_category_thresholds(score, category):
    assert rp.category_for(score) == category


def test_final_profile_takes_the_lower_score():
    assert rp.final_profile(tolerance=85, capacity=45) == (45, "moderate")
    assert rp.final_profile(tolerance=30, capacity=90) == (30, "conservative")


def test_explanations():
    assert "both point to a moderate" in rp.explanation(50, 60)
    assert "your finances support a moderate" in rp.explanation(85, 45)
    assert "your preference is respected" in rp.explanation(30, 90)
