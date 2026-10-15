"""AMFI daily NAV file (NAVAll.txt): download and parse.

AMFI publishes the latest NAV of every mutual fund scheme in India as one semicolon-separated
text file, refreshed every business evening. It is not a plain CSV - section lines between the
data rows carry the scheme type, SEBI category and fund house:

    Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;...
    Open Ended Schemes(Equity Scheme - Large Cap Fund)        <- scheme type + category
    Axis Mutual Fund                                          <- fund house (AMC)
    120465;INF846K01DP8;-;Axis Large Cap Fund;Direct Plan;Growth;62.1500;15-Oct-2026

so the parser is a small state machine that remembers the last section and AMC it saw.
Columns are located by their HEADER NAME, not position: AMFI added the Plan and Option columns
in 2026, and a positional parser would have silently read the wrong fields.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

NAV_ALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"

SECTION = re.compile(r"^(?P<type>.+? Schemes?)\s*\((?P<category>.+)\)$")
NOT_AVAILABLE = {"", "N.A.", "NA", "-"}

# Header names (lower case) -> field. Old files have no Plan/Option columns.
COLUMNS = {
    "scheme code": "scheme_code",
    "isin div payout/ isin growth": "isin_growth",
    "isin div reinvestment": "isin_reinvestment",
    "scheme name": "name",
    "plan": "plan",
    "option": "option",
    "net asset value": "nav",
    "date": "date",
}
REQUIRED = {"scheme_code", "name", "nav", "date"}


@dataclass(frozen=True)
class AmfiRow:
    scheme_code: int
    name: str
    amc: str
    scheme_type: str  # "Open Ended", "Close Ended", "Interval Fund"
    category: str  # "Large Cap Fund"
    asset_class: str  # normalised, see classify_asset_class
    plan: str  # direct / regular
    option: str  # growth / idcw / bonus / other
    isin_growth: str | None
    isin_reinvestment: str | None
    nav: Decimal
    nav_date: date


@dataclass
class ParsedNavFile:
    rows: list[AmfiRow] = field(default_factory=list)
    # Data-quality report: rows dropped and why (stored in job_runs.details).
    skipped: Counter = field(default_factory=Counter)

    @property
    def rows_read(self) -> int:
        return len(self.rows) + self.skipped.total()


# --- Classification ---------------------------------------------------------------------------


def split_section(text: str) -> tuple[str, str, str]:
    """'Open Ended Schemes(Equity Scheme - Large Cap Fund)' -> scheme type, group, category."""
    match = SECTION.match(text)
    if match is None:
        raise ValueError(f"not a section line: {text!r}")
    scheme_type = re.sub(r"\s+Schemes?$", "", match["type"]).strip()
    group, _, category = _clean(match["category"]).partition(" - ")
    return scheme_type, group.strip(), (category or group).strip()


def classify_asset_class(group: str, category: str) -> str:
    """Map AMFI's many (and changing) category labels to a few asset classes.

    AMFI uses old and new SEBI names side by side ("Equity Scheme", "Equity Schemes",
    "Income/Debt Oriented Schemes", ...), so matching is by keyword.
    """
    text = f"{group} {category}".lower()
    if "exchange traded" in text or re.search(r"\betfs?\b", text):
        return "etf"
    if "index" in text:
        return "index"
    if "fund of funds" in text or "fof" in text:
        return "fund_of_funds"
    if any(word in text for word in ("solution oriented", "retirement", "children", "life cycle")):
        return "solution_oriented"
    group = group.lower()
    if "equity" in group or group in ("growth", "elss"):
        return "equity"
    if "hybrid" in group:
        return "hybrid"
    if "debt" in group or group in ("income", "gilt", "money market"):
        return "debt"
    return "other"


def classify_plan(plan: str, name: str) -> str:
    """Direct plans (bought from the AMC, no distributor commission) or regular plans."""
    return "direct" if "direct" in (plan or name).lower() else "regular"


def classify_option(option: str, name: str) -> str:
    """Growth (gains stay invested), IDCW (payouts, formerly 'dividend') or bonus."""
    text = (option or name).lower()
    if "growth" in text:
        return "growth"
    if "idcw" in text or "dividend" in text or "income distribution" in text:
        return "idcw"
    if "bonus" in text:
        return "bonus"
    return "other"


# --- Parsing ----------------------------------------------------------------------------------


def _clean(value: str) -> str:
    """Collapse runs of spaces ("Other  ETFs" -> "Other ETFs")."""
    return re.sub(r"\s+", " ", value).strip()


def _isin(value: str) -> str | None:
    value = value.strip()
    return value if len(value) == 12 else None


@dataclass(frozen=True)
class _Section:
    scheme_type: str = ""
    group: str = ""
    category: str = ""
    amc: str = ""


def _parse_row(cells: dict[str, str], section: _Section) -> AmfiRow | str:
    """One data row -> AmfiRow, or the reason it was rejected (a data-quality check)."""
    try:
        scheme_code = int(cells["scheme_code"])
    except ValueError:
        return "bad_scheme_code"
    if cells["nav"] in NOT_AVAILABLE:
        return "nav_not_available"
    try:
        nav = Decimal(cells["nav"].replace(",", ""))
    except InvalidOperation:
        return "bad_nav"
    if nav <= 0:  # e.g. segregated portfolios written down to zero
        return "nav_not_positive"
    try:
        nav_date = datetime.strptime(cells["date"], "%d-%b-%Y").date()
    except ValueError:
        return "bad_date"
    return AmfiRow(
        scheme_code=scheme_code,
        name=_clean(cells["name"]),
        amc=section.amc,
        scheme_type=section.scheme_type,
        category=section.category,
        asset_class=classify_asset_class(section.group, section.category),
        plan=classify_plan(cells.get("plan", ""), cells["name"]),
        option=classify_option(cells.get("option", ""), cells["name"]),
        isin_growth=_isin(cells.get("isin_growth", "")),
        isin_reinvestment=_isin(cells.get("isin_reinvestment", "")),
        nav=nav,
        nav_date=nav_date,
    )


def parse_nav_all(text: str) -> ParsedNavFile:
    """Parse the whole NAVAll.txt file. Bad rows are counted, never fatal."""
    result = ParsedNavFile()
    columns: dict[str, int] | None = None
    section = _Section()
    seen: dict[int, int] = {}  # scheme code -> index in result.rows

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ";" not in line:  # a section line or a fund house line
            if SECTION.match(line):
                scheme_type, group, category = split_section(line)
                section = _Section(scheme_type, group, category, section.amc)
            else:
                section = _Section(section.scheme_type, section.group, section.category, line)
            continue

        values = [value.strip() for value in line.split(";")]
        if columns is None:
            columns = {
                COLUMNS[name.lower()]: index
                for index, name in enumerate(values)
                if name.lower() in COLUMNS
            }
            if missing := REQUIRED - columns.keys():
                raise ValueError(f"NAVAll header is missing {sorted(missing)}")
            continue
        if len(values) <= max(columns.values()):
            result.skipped["malformed_row"] += 1
            continue

        row = _parse_row({name: values[index] for name, index in columns.items()}, section)
        if isinstance(row, str):
            result.skipped[row] += 1
            continue
        # A scheme listed twice would make one INSERT ... ON CONFLICT touch the same row
        # twice, which PostgreSQL rejects. Keep the newer NAV.
        if row.scheme_code in seen:
            result.skipped["duplicate_scheme_code"] += 1
            index = seen[row.scheme_code]
            if row.nav_date >= result.rows[index].nav_date:
                result.rows[index] = row
            continue
        seen[row.scheme_code] = len(result.rows)
        result.rows.append(row)

    if columns is None:
        raise ValueError("NAVAll file has no header row")
    return result


def decode(content: bytes) -> str:
    """Decode line by line: the file is UTF-8, but a few lines carry Windows-1252 bytes
    (a curly apostrophe typed in a fund name), which would otherwise become garbage."""
    lines = []
    for line in content.split(b"\n"):
        try:
            lines.append(line.decode("utf-8"))
        except UnicodeDecodeError:
            lines.append(line.decode("cp1252", errors="replace"))
    return "\n".join(lines)


def fetch_nav_all(client: httpx.Client) -> str:
    response = client.get(NAV_ALL_URL)
    response.raise_for_status()
    return decode(response.content)
