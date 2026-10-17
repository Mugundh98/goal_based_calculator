"""Grounding check: did every number in an answer come from a tool result or from the user?

Language models are bad at arithmetic and may invent figures. The prompt tells the model to
use only numbers from tools; this check verifies it afterwards. Each number in the answer
(with ₹, %, lakh/L, crore/Cr or k) is compared with every number in the tool results, the
question and the recent conversation. Numbers that match nothing are stored with the answer
(and shown as a warning), which also feeds the chatbot evaluation in Phase 12.
"""

import re
from collections.abc import Iterable
from typing import Any

# 1,23,456.78 · 12.5 · 7 followed by an optional unit.
_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(\s?(?:%|percent\b|lakhs?\b|L\b|crores?\b|Cr\b|k\b))?",
    re.IGNORECASE,
)
_SCALE = {"lakh": 1e5, "lakhs": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7, "k": 1e3}
SMALL = 12  # bare integers up to 12 are counts, months or list numbers, not results
RELATIVE = 0.01  # money and other figures may be rounded by up to 1%
PERCENT_POINTS = 0.51  # a percentage rounded to a whole number


def numbers_in_text(text: str) -> list[tuple[str, float, str]]:
    """(as written, value in base units, unit) for every number in the text."""
    found = []
    for match in _NUMBER.finditer(text):
        raw, unit = match.group(1), (match.group(2) or "").strip().lower()
        value = float(raw.replace(",", ""))
        unit = "%" if unit in ("%", "percent") else unit
        found.append((match.group(0).strip(), value * _SCALE.get(unit, 1), unit))
    return found


def numbers_in_data(data: Any) -> Iterable[float]:
    """Every number in a tool result, including numbers written inside its strings."""
    if isinstance(data, bool) or data is None:
        return
    if isinstance(data, int | float):
        yield float(data)
    elif isinstance(data, str):
        for _, value, _ in numbers_in_text(data):
            yield value
    elif isinstance(data, dict):
        for value in data.values():
            yield from numbers_in_data(value)
    elif isinstance(data, list | tuple):
        for value in data:
            yield from numbers_in_data(value)


def _matches(value: float, unit: str, sources: list[float]) -> bool:
    # Magnitudes only: "behind plan by ₹38,483" reports the tool's -38483 in words.
    value = abs(value)
    for source in (abs(s) for s in sources):
        if unit == "%":
            if abs(value - source) <= PERCENT_POINTS:
                return True
        elif abs(value - source) <= max(RELATIVE * abs(source), 0.5):
            return True
    return False


def ungrounded(answer: str, sources: Iterable[Any]) -> list[str]:
    """Numbers in the answer that appear in none of the sources (texts or tool results)."""
    known = [v for source in sources for v in numbers_in_data(source)]
    missing = []
    for written, value, unit in numbers_in_text(answer):
        if not unit and value <= SMALL and value.is_integer():
            continue
        if not _matches(value, unit, known):
            missing.append(written)
    return list(dict.fromkeys(missing))  # unique, in order
