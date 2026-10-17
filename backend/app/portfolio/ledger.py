"""From transactions to a holding: units held, their cost (first in, first out) and gains.

A holding is derived data: it can always be rebuilt by replaying the fund's transactions in date
order. Redemptions use the units bought first (FIFO), as registrars do when they report capital
gains on mutual fund units, so the cost of what is still held and the gain already booked are
both well defined.
Pure: Decimal arithmetic, no database.
"""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Literal

PAISE = Decimal("0.01")
ALLOTTED_UNITS = Decimal("0.001")  # registrars allot units to three decimals
# Selling within a thousandth of a unit more than is held means "sell everything": statements
# round units, and a holding should not stay open with 0.0004 units.
UNIT_TOLERANCE = Decimal("0.001")
# 0.005% of the amount is deducted before units are allotted, on purchases from 1 July 2020.
STAMP_DUTY = Decimal("0.00005")
STAMP_DUTY_FROM = date(2020, 7, 1)

Kind = Literal["buy", "sell"]


@dataclass(frozen=True)
class Entry:
    """One transaction, with its units expressed in the fund's CURRENT units (see services)."""

    day: date
    kind: Kind
    amount: Decimal  # rupees paid (buy) or received (sell), always positive
    units: Decimal
    id: int = 0


@dataclass(frozen=True)
class Position:
    units: Decimal
    cost: Decimal  # what the units still held cost (FIFO)
    realised_gain: Decimal  # gains booked by redemptions so far
    first_date: date | None
    last_date: date | None


class InsufficientUnits(ValueError):
    def __init__(self, day: date, wanted: Decimal, held: Decimal) -> None:
        super().__init__(
            f"On {day.isoformat()} only {held:,.3f} units were held; cannot redeem {wanted:,.3f}"
        )
        self.day = day
        self.wanted = wanted
        self.held = held


def units_for(amount: Decimal, nav: Decimal, kind: Kind, day: date) -> Decimal:
    """Units allotted for a purchase (after stamp duty) or redeemed for an amount."""
    if kind == "buy":
        if day >= STAMP_DUTY_FROM:
            amount = amount * (1 - STAMP_DUTY)
        return (amount / nav).quantize(ALLOTTED_UNITS, rounding=ROUND_DOWN)
    return (amount / nav).quantize(ALLOTTED_UNITS, rounding=ROUND_HALF_UP)


def ordered(entries: Iterable[Entry]) -> list[Entry]:
    """Date order; on the same day purchases first, then in the order they were entered."""
    return sorted(entries, key=lambda e: (e.day, e.kind != "buy", e.id))


def replay(entries: Iterable[Entry]) -> Position:
    """Fold the transactions into a position; raises InsufficientUnits on an over-redemption."""
    lots: deque[list[Decimal]] = deque()  # [units, cost] per purchase still (partly) held
    realised = Decimal(0)
    first: date | None = None
    last: date | None = None
    for entry in ordered(entries):
        first = first or entry.day
        last = entry.day
        if entry.kind == "buy":
            lots.append([entry.units, entry.amount])
            continue
        held = sum((lot[0] for lot in lots), Decimal(0))
        wanted = entry.units
        if wanted > held + UNIT_TOLERANCE:
            raise InsufficientUnits(entry.day, wanted, held)
        wanted = min(wanted, held)
        cost_of_sold = Decimal(0)
        while wanted > 0 and lots:
            lot = lots[0]
            take = min(lot[0], wanted)
            lot_cost = lot[1] * take / lot[0]
            cost_of_sold += lot_cost
            lot[0] -= take
            lot[1] -= lot_cost
            wanted -= take
            if lot[0] <= 0:
                lots.popleft()
        if sum((lot[0] for lot in lots), Decimal(0)) < UNIT_TOLERANCE:
            lots.clear()  # the remainder of a full redemption
        realised += entry.amount - cost_of_sold
    return Position(
        units=sum((lot[0] for lot in lots), Decimal(0)),
        cost=sum((lot[1] for lot in lots), Decimal(0)).quantize(PAISE, rounding=ROUND_HALF_UP),
        realised_gain=realised.quantize(PAISE, rounding=ROUND_HALF_UP),
        first_date=first,
        last_date=last,
    )
