"""Unit tests for restating daily NAV series across face-value changes (no database)."""

from datetime import date, timedelta

import pytest

from app.finance.nav_adjust import adjust_series

START = date(2026, 1, 1)


def daily(values):
    return [(START + timedelta(days=i), float(v)) for i, v in enumerate(values)]


def test_series_without_changes_is_untouched():
    series = daily([100, 101, 99, 102])
    assert adjust_series(series) == (series, [])


def test_one_to_ten_change_is_restated_in_todays_units():
    # 4,567 -> 460: UTI Liquid Fund's change of June 2026 (a 0.7% day on top of the factor).
    adjusted, changes = adjust_series(daily([4550, 4567, 459.9, 460.0]))
    assert [(c.day, c.factor) for c in changes] == [(START + timedelta(days=2), 0.1)]
    assert [round(v, 2) for _, v in adjusted] == [455.0, 456.7, 459.9, 460.0]
    assert adjusted[-1][1] == 460.0  # the latest NAV is exactly the published one


def test_ten_to_thousand_rupee_units():
    adjusted, changes = adjust_series(daily([10.0, 10.01, 1001.5, 1002.0]))
    assert changes[0].factor == 100
    assert adjusted[0][1] == pytest.approx(1000.0)
    assert adjusted[2][1] == 1001.5


def test_several_changes_accumulate():
    adjusted, changes = adjust_series(daily([10, 1000, 1001, 100.1, 100.2]))
    assert [c.factor for c in changes] == [100, 0.1]
    assert [round(v, 2) for _, v in adjusted] == [100.0, 100.0, 100.1, 100.1, 100.2]


def test_real_crash_is_kept():
    series = daily([100, 64, 66])  # -36%: March 2020, not a unit change
    assert adjust_series(series) == (series, [])
