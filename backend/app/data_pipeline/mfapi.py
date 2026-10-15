"""Historical NAVs for one scheme from mfapi.in, cached on disk.

AMFI's NAVAll.txt only has the LATEST NAV. For history we use mfapi.in, a free, key-less
mirror of AMFI's data: one JSON document per scheme with every NAV since launch. Responses are
cached in DATA_CACHE_DIR, so re-running a backfill (after a crash, or on a fresh database)
does not download thousands of files again.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

MFAPI_URL = "https://api.mfapi.in/mf/{scheme_code}"


GAP_WARNING_DAYS = 10  # weekends and holidays leave gaps of up to ~5 days; more is suspicious


@dataclass
class NavHistoryFile:
    points: list[tuple[date, Decimal]] = field(default_factory=list)  # oldest first
    skipped: Counter = field(default_factory=Counter)

    def largest_gap(self) -> tuple[int, date | None]:
        """Longest stretch without a NAV (days) and the date it ended - a data-quality check.

        Small gaps are normal (weekends, holidays) and handled by using the last NAV on or
        before a date; a long gap means missing data and is reported in job_runs.details.
        """
        gaps = [
            ((later - earlier).days, later)
            for (earlier, _), (later, _) in zip(self.points, self.points[1:], strict=False)
        ]
        return max(gaps, default=(0, None))


def parse_history(document: dict) -> NavHistoryFile:
    """Turn {"data": [{"date": "14-10-2026", "nav": "106.81"}, ...]} into sorted points."""
    result = NavHistoryFile()
    by_date: dict[date, Decimal] = {}
    for entry in document.get("data") or []:
        try:
            day = datetime.strptime(entry["date"], "%d-%m-%Y").date()
            nav = Decimal(entry["nav"])
        except (KeyError, TypeError, ValueError, InvalidOperation):
            result.skipped["bad_row"] += 1
            continue
        if nav <= 0:
            result.skipped["nav_not_positive"] += 1
            continue
        if day in by_date:
            result.skipped["duplicate_date"] += 1
        by_date[day] = nav
    result.points = sorted(by_date.items())
    return result


def load_history(client: httpx.Client, scheme_code: int, cache_dir: Path | None) -> dict:
    """The raw JSON for a scheme: from the cache if present, otherwise downloaded and cached."""
    cache_file = cache_dir / f"{scheme_code}.json" if cache_dir else None
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    response = client.get(MFAPI_URL.format(scheme_code=scheme_code))
    response.raise_for_status()
    document = response.json()
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(document), encoding="utf-8")
    return document
