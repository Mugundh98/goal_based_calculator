"""Consumer Price Index (CPI) from MOSPI, the Ministry of Statistics (api.mospi.gov.in).

The free, key-less MOSPI API returns the monthly All-India CPI. We load the headline series:
All India, Combined (rural + urban), General index. The index value is stored; inflation is
derived from it (CPI this month / CPI a year earlier - 1).

MOSPI moved CPI to base year 2024 in January 2026. At the time of writing the API serves the
base-2012 series (January 2011 - December 2025); the base year is a parameter, so the newer
series can be added when the API publishes it.
"""

import ssl
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

CPI_URL = "https://api.mospi.gov.in/api/cpi/getCPIIndex"
DEFAULT_BASE_YEAR = 2012
ALL_INDIA, COMBINED, GENERAL_INDEX = 99, 3, 0  # MOSPI codes
PAGE_SIZE = 200  # the API's maximum

MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        start=1,
    )
}


@dataclass(frozen=True)
class CpiPoint:
    period: date  # first day of the month
    cpi: Decimal
    is_final: bool


@dataclass
class CpiSeries:
    points: list[CpiPoint] = field(default_factory=list)  # oldest first
    skipped: Counter = field(default_factory=Counter)


def parse_cpi(records: list[dict]) -> CpiSeries:
    """MOSPI records ({"year": 2025, "month": "December", "index": "198.0", "status": "F"})."""
    result = CpiSeries()
    by_period: dict[date, CpiPoint] = {}
    official: set[date] = set()  # months whose kept row carries MOSPI's published inflation
    for record in records:
        try:
            period = date(int(record["year"]), MONTHS[record["month"]], 1)
            cpi = Decimal(record["index"])
        except (KeyError, TypeError, ValueError, InvalidOperation):
            result.skipped["missing_or_bad_index"] += 1
            continue
        if cpi <= 0:
            result.skipped["index_not_positive"] += 1
            continue
        has_inflation = record.get("inflation") is not None
        if period in by_period:
            # The API lists January-May 2013 twice with different values; the official row is
            # the one with a published inflation rate. Otherwise the later row wins.
            result.skipped["duplicate_month"] += 1
            if period in official and not has_inflation:
                continue
        by_period[period] = CpiPoint(period, cpi, record.get("status", "F") == "F")
        if has_inflation:
            official.add(period)
    result.points = sorted(by_period.values(), key=lambda point: point.period)
    return result


def mospi_ssl_context() -> ssl.SSLContext:
    """MOSPI's server still uses TLS "legacy renegotiation", which OpenSSL 3 refuses by default
    (UNSAFE_LEGACY_RENEGOTIATION_DISABLED). Allow it for this one host only; certificates are
    still verified."""
    context = ssl.create_default_context()
    context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    return context


def fetch_cpi(client: httpx.Client, base_year: int = DEFAULT_BASE_YEAR) -> list[dict]:
    """Every month of the headline index, following the API's pages."""
    records: list[dict] = []
    page = 1
    while True:
        response = client.get(
            CPI_URL,
            params={
                "base_year": base_year,
                "state_code": ALL_INDIA,
                "sector_code": COMBINED,
                "group_code": GENERAL_INDEX,
                "limit": PAGE_SIZE,
                "page": page,
                "format": "json",
            },
        )
        response.raise_for_status()
        body = response.json()
        records.extend(body.get("data") or [])
        total_pages = (body.get("meta_data") or {}).get("totalPages", 1)
        if page >= total_pages:
            return records
        page += 1
