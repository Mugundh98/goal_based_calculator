"""Parsing and validation of the source files (no database, no network)."""

import math
from datetime import date
from decimal import Decimal

import pytest

from app.data_pipeline import amfi, cpi, indices, mfapi
from tests.pipeline_samples import CPI_RECORDS, MFAPI_HISTORY, NAV_ALL

# --- AMFI NAVAll.txt --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def parsed():
    return amfi.parse_nav_all(NAV_ALL)


def by_code(parsed, code):
    return next(row for row in parsed.rows if row.scheme_code == code)


def test_amfi_rows_and_data_quality_report(parsed):
    assert [row.scheme_code for row in parsed.rows] == [
        120465, 120466, 112277, 119091, 119092, 120716, 128111,
    ]  # fmt: skip
    assert parsed.skipped == {
        "nav_not_positive": 1,  # segregated portfolio written down to 0
        "nav_not_available": 1,  # "N.A."
        "duplicate_scheme_code": 1,
        "bad_date": 1,  # 31-Sep-2026
    }
    assert parsed.rows_read == 11  # every data line is either loaded or counted as skipped


def test_amfi_sections_give_type_category_and_fund_house(parsed):
    row = by_code(parsed, 120465)
    assert (row.scheme_type, row.category, row.asset_class) == (
        "Open Ended",
        "Large Cap Fund",
        "equity",
    )
    assert row.amc == "Axis Mutual Fund"
    assert (row.plan, row.option) == ("direct", "growth")
    assert row.nav == Decimal("62.1500") and row.nav_date == date(2026, 10, 15)
    assert row.isin_growth == "INF846K01DP8" and row.isin_reinvestment is None  # "-"

    fmp = by_code(parsed, 128111)
    assert (fmp.scheme_type, fmp.category, fmp.asset_class) == (
        "Close Ended",
        "Fixed Term Plan",
        "debt",
    )
    assert fmp.amc == "ICICI Prudential Mutual Fund"


def test_amfi_plan_and_option_fall_back_to_the_name(parsed):
    # Older rows have empty Plan/Option columns: the scheme name is used instead.
    liquid = by_code(parsed, 119091)
    assert (liquid.plan, liquid.option) == ("direct", "growth")
    assert liquid.nav == Decimal("5012.34567891")  # all 8 decimals kept
    assert (by_code(parsed, 119092).plan, by_code(parsed, 119092).option) == ("regular", "idcw")
    assert by_code(parsed, 128111).option == "other"


def test_amfi_duplicate_keeps_the_newer_nav_and_cleans_spaces(parsed):
    index_fund = by_code(parsed, 120716)
    assert index_fund.nav == Decimal("172.0000") and index_fund.nav_date == date(2026, 10, 15)
    assert index_fund.name == "UTI Nifty 50 Index Fund"
    assert index_fund.asset_class == "index"


def test_amfi_columns_found_by_header_name():
    # The pre-2026 layout (no Plan/Option columns) still parses.
    old = (
        "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;"
        "Net Asset Value;Date\n"
        "Open Ended Schemes(Equity Scheme - Mid Cap Fund)\nKotak Mahindra Mutual Fund\n"
        "119775;INF174K01LS2;-;Kotak Emerging Equity Fund - Direct - Growth;150.5;15-Oct-2026\n"
    )
    row = amfi.parse_nav_all(old).rows[0]
    assert (row.category, row.plan, row.option, row.nav) == (
        "Mid Cap Fund",
        "direct",
        "growth",
        Decimal("150.5"),
    )


def test_amfi_rejects_a_file_without_the_needed_columns():
    with pytest.raises(ValueError, match="missing"):
        amfi.parse_nav_all("Scheme Code;Scheme Name\n1;x\n")
    with pytest.raises(ValueError, match="no header"):
        amfi.parse_nav_all("Open Ended Schemes(Equity Scheme - Large Cap Fund)\n")


def test_amfi_decodes_mixed_encodings():
    content = "Children’s Fund\n".encode() + "Children\x92s Fund\n".encode("latin-1")
    assert amfi.decode(content) == "Children’s Fund\nChildren’s Fund\n"


FOF_DOMESTIC = "Fund of Funds Scheme (Domestic)"


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        ("Open Ended Schemes(Equity Schemes - Flexi Cap Fund)", "equity"),  # 2026 SEBI wording
        ("Open Ended Schemes(Income/Debt Oriented Schemes - Gilt Fund)", "debt"),
        ("Open Ended Schemes(Hybrid Scheme - Arbitrage Fund)", "hybrid"),
        ("Open Ended Schemes(Other Scheme - Index Funds)", "index"),
        ("Open Ended Schemes(Index Funds - Equity Funds)", "index"),
        ("Open Ended Schemes(Other Scheme - Gold ETF)", "etf"),
        ("Open Ended Schemes(Exchange Traded Funds (ETFs) - Silver ETF)", "etf"),
        (f"Open Ended Schemes({FOF_DOMESTIC} - {FOF_DOMESTIC})", "fund_of_funds"),
        ("Open Ended Schemes(Other Scheme - FoF Overseas)", "fund_of_funds"),
        ("Open Ended Schemes(Solution Oriented Scheme - Retirement Fund)", "solution_oriented"),
        ("Close Ended Schemes(ELSS)", "equity"),
        ("Interval Fund Schemes(Income)", "debt"),
    ],
)  # fmt: skip
def test_asset_class_mapping(section, expected):
    _, group, category = amfi.split_section(section)
    assert amfi.classify_asset_class(group, category) == expected


# --- mfapi.in history -------------------------------------------------------------------------


def test_mfapi_history_sorted_deduplicated_and_validated():
    history = mfapi.parse_history(MFAPI_HISTORY)
    assert history.points == [
        (date(2021, 10, 15), Decimal("31.07500")),
        (date(2025, 10, 10), Decimal("50.00000")),
        (date(2026, 10, 14), Decimal("61.90000")),
        (date(2026, 10, 15), Decimal("62.15000")),
    ]
    assert history.skipped == {"duplicate_date": 1, "bad_row": 1}


def test_mfapi_largest_gap_reports_missing_data():
    history = mfapi.parse_history(MFAPI_HISTORY)
    # 15 Oct 2021 -> 10 Oct 2025: almost four years without a NAV in this sample
    assert history.largest_gap() == (1456, date(2025, 10, 10))
    assert mfapi.NavHistoryFile().largest_gap() == (0, None)


def test_mfapi_reads_from_cache_without_network(tmp_path):
    (tmp_path / "120465.json").write_text('{"data": [{"date": "15-10-2026", "nav": "1.5"}]}')

    class NoNetwork:
        def get(self, url):
            raise AssertionError("should not download")

    document = mfapi.load_history(NoNetwork(), 120465, tmp_path)
    assert document["data"][0]["nav"] == "1.5"


# --- Indices ----------------------------------------------------------------------------------


def test_index_closes_cleaned():
    series = indices.clean_closes(
        [
            (date(2026, 10, 15), 25000.123456),
            (date(2026, 10, 14), math.nan),  # Yahoo sometimes has holes
            (date(2026, 10, 13), 24900.0),
            (date(2026, 10, 13), 24900.0),
            (date(2026, 10, 12), 0.0),
        ]
    )
    assert series.points == [
        (date(2026, 10, 13), Decimal("24900.0")),
        (date(2026, 10, 15), Decimal("25000.1235")),
    ]
    assert series.skipped == {"missing_close": 1, "duplicate_date": 1, "close_not_positive": 1}


# --- CPI --------------------------------------------------------------------------------------


def test_cpi_parsed_and_duplicates_resolved():
    series = cpi.parse_cpi(CPI_RECORDS)
    values = {point.period: point.cpi for point in series.points}
    assert values == {
        date(2013, 4, 1): Decimal("106.7"),  # the row with MOSPI's published inflation wins
        date(2013, 5, 1): Decimal("107.5"),
        date(2024, 12, 1): Decimal("195.4"),
        date(2025, 11, 1): Decimal("197.9"),
        date(2025, 12, 1): Decimal("198.0"),
    }
    assert [p.is_final for p in series.points][-2:] == [False, True]  # "P" = provisional
    assert series.skipped == {"duplicate_month": 2, "missing_or_bad_index": 1}
