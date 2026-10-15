"""Unit tests for goal projections and return assumptions (no database)."""

import pytest

from app.finance.goal_plan import GoalInputs, project_goal, suggested_return

# Worked example from the Phase 3 document: a child's higher education.
EDUCATION = GoalInputs(
    target_today=2_000_000,
    years=15,
    inflation_rate=0.10,
    expected_return=0.12,
    current_savings=200_000,
    monthly_sip=15_000,
)


def test_worked_example():
    p = project_goal(EDUCATION)
    assert p.inflated_target == pytest.approx(8_354_496.34)
    assert p.savings_value == pytest.approx(1_094_713.15)
    assert p.sip_value == pytest.approx(7_138_970.99)
    assert p.projected_value == pytest.approx(8_233_684.14)
    assert p.shortfall == pytest.approx(120_812.20)
    assert p.required_sip == 15_254  # 15,253.84 rounded UP to a whole rupee
    assert p.funded_percent == 98.5  # 98.55% rounded down
    assert p.on_track is False
    assert p.real_return == pytest.approx(0.018182, abs=1e-6)


def test_investing_the_required_sip_puts_the_goal_on_track():
    required = project_goal(EDUCATION).required_sip
    p = project_goal(GoalInputs(**{**EDUCATION.__dict__, "monthly_sip": required}))
    assert p.on_track
    assert p.funded_percent == 100.0


def test_funded_percent_never_rounds_up_to_100():
    p = project_goal(GoalInputs(**{**EDUCATION.__dict__, "monthly_sip": 15_253}))
    assert not p.on_track
    assert p.funded_percent == 99.9


def test_step_up_lowers_the_required_starting_sip():
    flat = project_goal(EDUCATION).required_sip
    stepped = project_goal(GoalInputs(**{**EDUCATION.__dict__, "step_up_rate": 0.10})).required_sip
    assert stepped < flat


def test_savings_already_enough():
    p = project_goal(GoalInputs(500_000, 5, 0.06, 0.10, current_savings=1_000_000))
    assert p.required_sip == 0
    assert p.on_track
    assert p.shortfall == 0


def test_goal_due_now_with_shortfall_has_no_required_sip():
    p = project_goal(GoalInputs(500_000, 0, 0.06, 0.10, current_savings=100_000))
    assert p.inflated_target == 500_000  # no time for inflation
    assert p.required_sip is None
    assert p.shortfall == 400_000


def test_past_goal_treated_as_due_now():
    assert project_goal(GoalInputs(100, -2, 0.06, 0.10)).years_to_goal == 0


@pytest.mark.parametrize(
    "category, years, expected",
    [
        ("conservative", 10, (0.08, "risk_profile")),
        ("moderate", 10, (0.10, "risk_profile")),
        ("aggressive", 3, (0.12, "risk_profile")),  # 3 years is no longer "short"
        ("aggressive", 2, (0.07, "short_horizon")),
        (None, 10, (0.10, "default")),
        (None, 1, (0.07, "short_horizon")),
    ],
)
def test_suggested_return(category, years, expected):
    assert suggested_return(category, years) == expected
