"""Portfolio tracker: record transactions, keep holdings in step, value them, track each goal.

Transactions are the source of truth; `holdings` is derived from them and rebuilt for the
affected (user, goal, fund) inside the same database transaction as every insert or delete.
Writes for one user are serialised with a PostgreSQL advisory lock, so two requests can never
both redeem the same units. Market values, XIRR and goal status are computed on every read.
"""

import bisect
import calendar
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, delete, select, text
from sqlalchemy.orm import Session, joinedload

from app.finance import tvm
from app.finance.goal_plan import GoalInputs, project_goal
from app.finance.nav_adjust import adjust_series
from app.finance.xirr import xirr
from app.models import Fund, Goal, Holding, NavHistory, Recommendation, Transaction, User
from app.portfolio.ledger import PAISE, Entry, InsufficientUnits, replay, units_for
from app.portfolio.tracking import (
    DRIFT_THRESHOLD,
    ROW_LABELS,
    Rebalance,
    grown_contributions,
    rebalance,
    sleeve_of,
)
from app.schemas.portfolio import (
    Alert,
    DriftRowOut,
    GoalProgress,
    GoalStatus,
    HistoryPoint,
    HoldingRead,
    PortfolioRead,
    PortfolioTotals,
    RebalanceOut,
    SipCreate,
    TransactionCreate,
    TransactionRead,
    ValuePoint,
)
from app.services import goals as goal_service
from app.services.recommendations import history_for

PERCENT = 100
MAX_NAV_GAP_DAYS = 7  # a transaction uses the latest NAV at most a week before its date
LOCK_NAMESPACE = 9  # first key of the advisory lock (Phase 9); the second is the user id
MIN_XIRR_DAYS = 365  # annualising a few weeks' return exaggerates it
STALE_AFTER_DAYS = 365
UNITS = Decimal("0.000001")


class PortfolioError(ValueError):
    """A request that cannot be carried out; the message is shown to the user."""


class NotFound(PortfolioError):
    pass


# --- NAVs ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class NavSeries:
    """One fund's daily NAVs as published, with the unit changes found in them."""

    days: list[date]
    navs: list[Decimal]
    changes: list[tuple[date, int]] = field(default_factory=list)  # (first new-unit day, k)

    def last_on(self, day: date) -> tuple[date, Decimal] | None:
        i = bisect.bisect_right(self.days, day) - 1
        return (self.days[i], self.navs[i]) if i >= 0 else None

    def price_on(self, day: date) -> tuple[date, Decimal] | None:
        """The NAV a transaction on `day` gets: the latest at most a week earlier."""
        found = self.last_on(day)
        if found is None or (day - found[0]).days > MAX_NAV_GAP_DAYS:
            return None
        return found

    def multiplier(self, day: date) -> Decimal:
        """How many of today's units one unit held on `day` has become (inverted)."""
        result = Decimal(1)
        for changed, k in self.changes:
            if changed > day:
                result *= Decimal(10) ** k
        return result

    def adjusted_on(self, day: date) -> float | None:
        """NAV on `day` restated in today's units."""
        found = self.last_on(day)
        return float(found[1] * self.multiplier(day)) if found else None


def nav_series(db: Session, fund_id: int, since: date) -> NavSeries:
    rows = db.execute(
        select(NavHistory.nav_date, NavHistory.nav)
        .where(NavHistory.fund_id == fund_id, NavHistory.nav_date >= since)
        .order_by(NavHistory.nav_date)
    ).all()
    days = [r.nav_date for r in rows]
    navs = [r.nav for r in rows]
    _, changes = adjust_series([(d, float(n)) for d, n in zip(days, navs, strict=True)])
    return NavSeries(days, navs, [(c.day, round(math.log10(c.factor))) for c in changes])


# --- Writes ----------------------------------------------------------------------------------


def _lock(db: Session, user_id: int) -> None:
    """Serialise this user's portfolio writes until the transaction ends."""
    db.execute(text("SELECT pg_advisory_xact_lock(:a, :b)"), {"a": LOCK_NAMESPACE, "b": user_id})


def _same_goal(column: ColumnElement, goal_id: int | None) -> ColumnElement[bool]:
    return column.is_(None) if goal_id is None else column == goal_id


def _rebuild(db: Session, user_id: int, goal_id: int | None, fund_id: int) -> None:
    """Replay one position's transactions into its holdings row (InsufficientUnits on error)."""
    transactions = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user_id,
            _same_goal(Transaction.goal_id, goal_id),
            Transaction.fund_id == fund_id,
        )
    ).all()
    holding = db.scalar(
        select(Holding).where(
            Holding.user_id == user_id,
            _same_goal(Holding.goal_id, goal_id),
            Holding.fund_id == fund_id,
        )
    )
    if not transactions:
        if holding is not None:
            db.delete(holding)
        return
    first = min(t.txn_date for t in transactions)
    series = nav_series(db, fund_id, first - timedelta(days=MAX_NAV_GAP_DAYS))
    position = replay(
        Entry(t.txn_date, t.txn_type, t.amount, t.units / series.multiplier(t.txn_date), t.id)
        for t in transactions
    )
    if holding is None:
        holding = Holding(user_id=user_id, goal_id=goal_id, fund_id=fund_id)
        db.add(holding)
    holding.units = position.units.quantize(UNITS, rounding=ROUND_HALF_UP)
    holding.cost = position.cost
    holding.realised_gain = position.realised_gain
    holding.first_date = position.first_date
    holding.last_date = position.last_date


def _rebuild_or_fail(db: Session, user_id: int, goal_id: int | None, fund_id: int) -> None:
    try:
        _rebuild(db, user_id, goal_id, fund_id)
        db.flush()
    except InsufficientUnits as error:
        db.rollback()
        raise PortfolioError(str(error)) from None


def _owned_goal(db: Session, user: User, goal_id: int | None) -> Goal | None:
    if goal_id is None:
        return None
    goal = goal_service.get_goal(db, user, goal_id)
    if goal is None:
        raise NotFound("Goal not found")
    return goal


def _fund(db: Session, fund_id: int) -> Fund:
    fund = db.get(Fund, fund_id)
    if fund is None:
        raise NotFound("Fund not found")
    return fund


def _no_nav(fund: Fund, day: date) -> PortfolioError:
    latest = f" (latest NAV: {fund.latest_nav_date.isoformat()})" if fund.latest_nav_date else ""
    return PortfolioError(
        f"{fund.name} has no NAV on {day.isoformat()} or in the week before{latest}"
    )


def add_transaction(
    db: Session, user: User, data: TransactionCreate, today: date | None = None
) -> Transaction:
    if data.txn_date > (today or date.today()):
        raise PortfolioError("A transaction cannot be dated in the future")
    _owned_goal(db, user, data.goal_id)
    fund = _fund(db, data.fund_id)
    _lock(db, user.id)
    price = nav_series(db, fund.id, data.txn_date - timedelta(days=MAX_NAV_GAP_DAYS)).price_on(
        data.txn_date
    )
    if price is None:
        raise _no_nav(fund, data.txn_date)
    nav = price[1]
    amount, units = data.amount, data.units
    if units is None:
        units = units_for(amount, nav, data.txn_type, data.txn_date)
        if units <= 0:
            raise PortfolioError("The amount is too small to buy any units")
    if amount is None:
        amount = (units * nav).quantize(PAISE, rounding=ROUND_HALF_UP)
    transaction = Transaction(
        user_id=user.id,
        goal_id=data.goal_id,
        fund_id=fund.id,
        txn_type=data.txn_type,
        txn_date=data.txn_date,
        amount=amount,
        units=units,
        nav=nav,
        note=data.note,
    )
    db.add(transaction)
    db.flush()
    _rebuild_or_fail(db, user.id, data.goal_id, fund.id)
    db.commit()
    db.refresh(transaction)
    return transaction


def monthly_dates(start: date, end: date) -> list[date]:
    """The same day every month (the last day in shorter months), from start to end."""
    dates: list[date] = []
    year, month = start.year, start.month
    while True:
        day = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
        if day > end:
            return dates
        dates.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def add_sip(db: Session, user: User, data: SipCreate, today: date | None = None) -> list[int]:
    """Record a monthly SIP's past instalments as purchases; returns the new transaction ids."""
    today = today or date.today()
    end = min(data.end_date or today, today)
    _owned_goal(db, user, data.goal_id)
    fund = _fund(db, data.fund_id)
    _lock(db, user.id)
    series = nav_series(db, fund.id, data.start_date - timedelta(days=MAX_NAV_GAP_DAYS))
    created: list[Transaction] = []
    for day in monthly_dates(data.start_date, end):
        price = series.price_on(day)
        if price is None:
            raise _no_nav(fund, day)
        created.append(
            Transaction(
                user_id=user.id,
                goal_id=data.goal_id,
                fund_id=fund.id,
                txn_type="buy",
                txn_date=day,
                amount=data.amount,
                units=units_for(data.amount, price[1], "buy", day),
                nav=price[1],
                note="SIP",
            )
        )
    if not created:
        raise PortfolioError("No instalment falls between these dates")
    db.add_all(created)
    db.flush()
    _rebuild_or_fail(db, user.id, data.goal_id, fund.id)
    db.commit()
    return [t.id for t in created]


def delete_transaction(db: Session, user: User, transaction_id: int) -> None:
    transaction = db.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id)
    )
    if transaction is None:
        raise NotFound("Transaction not found")
    _lock(db, user.id)
    goal_id, fund_id = transaction.goal_id, transaction.fund_id
    db.delete(transaction)
    db.flush()
    try:
        _rebuild(db, user.id, goal_id, fund_id)
        db.flush()
    except InsufficientUnits as error:
        db.rollback()
        raise PortfolioError(
            f"A later redemption needs these units. {error}. Delete the redemption first."
        ) from None
    db.commit()


def rebuild_user(db: Session, user_id: int) -> None:
    """Throw away a user's holdings and rebuild every one from the transactions."""
    _lock(db, user_id)
    db.execute(delete(Holding).where(Holding.user_id == user_id))
    pairs = db.execute(
        select(Transaction.goal_id, Transaction.fund_id)
        .where(Transaction.user_id == user_id)
        .distinct()
    ).all()
    for goal_id, fund_id in pairs:
        _rebuild(db, user_id, goal_id, fund_id)
    db.flush()


def list_transactions(
    db: Session, user: User, goal_id: int | None = None, fund_id: int | None = None
) -> list[TransactionRead]:
    query = (
        select(Transaction)
        .options(joinedload(Transaction.fund))
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    )
    if goal_id is not None:
        query = query.where(Transaction.goal_id == goal_id)
    if fund_id is not None:
        query = query.where(Transaction.fund_id == fund_id)
    names = {g.id: g.name for g in goal_service.list_goals(db, user)}
    return [
        TransactionRead(
            id=t.id,
            fund_id=t.fund_id,
            fund_name=t.fund.name,
            goal_id=t.goal_id,
            goal_name=names.get(t.goal_id) if t.goal_id else None,
            txn_type=t.txn_type,
            txn_date=t.txn_date,
            amount=float(t.amount),
            units=float(t.units),
            nav=float(t.nav),
            note=t.note,
            created_at=t.created_at,
        )
        for t in db.scalars(query)
    ]


# --- Reads -----------------------------------------------------------------------------------

Flow = tuple[date, float]


def _rate(flows: Iterable[Flow]) -> float | None:
    """XIRR in percent, or None under a year (or when there is no rate)."""
    flows = list(flows)
    if not flows:
        return None
    days = [d for d, _ in flows]
    if (max(days) - min(days)).days < MIN_XIRR_DAYS:
        return None
    result = xirr(flows)
    return round(result.rate * PERCENT, 2) if result else None


def _flow(t: Transaction) -> Flow:
    return (t.txn_date, -float(t.amount) if t.txn_type == "buy" else float(t.amount))


@dataclass(frozen=True)
class Book:
    """Everything a portfolio read needs, loaded with a few queries."""

    holdings: list[Holding]
    flows: dict[tuple[int | None, int], list[Flow]]  # per (goal, fund)
    goals: list[Goal]
    category: str | None


def _book(db: Session, user: User) -> Book:
    holdings = list(
        db.scalars(
            select(Holding)
            .options(joinedload(Holding.fund))
            .where(Holding.user_id == user.id)
            .order_by(Holding.goal_id.nulls_last(), Holding.id)
        )
    )
    flows: dict[tuple[int | None, int], list[Flow]] = defaultdict(list)
    for t in db.scalars(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.txn_date)
    ):
        flows[(t.goal_id, t.fund_id)].append(_flow(t))
    return Book(
        holdings,
        flows,
        goal_service.list_goals(db, user),
        goal_service.risk_category(db, user),
    )


def _terminal(h: Holding) -> list[Flow]:
    """Today's value as if redeemed: the last flow of every XIRR."""
    value = _value(h)
    return [(h.fund.latest_nav_date, value)] if value > 0 and h.fund.latest_nav_date else []


def _value(h: Holding) -> float:
    return float(h.units * h.fund.latest_nav) if h.fund.latest_nav else 0.0


def holding_read(h: Holding, flows: list[Flow], goal_name: str | None) -> HoldingRead:
    value = _value(h)
    cost = float(h.cost)
    sleeve = sleeve_of(h.fund.category, h.fund.name, h.fund.asset_class)
    return HoldingRead(
        id=h.id,
        goal_id=h.goal_id,
        goal_name=goal_name,
        fund_id=h.fund_id,
        fund_name=h.fund.name,
        amc=h.fund.amc,
        category=h.fund.category,
        plan=h.fund.plan,
        option=h.fund.option,
        sleeve=sleeve,
        sleeve_label=ROW_LABELS[sleeve],
        units=float(h.units),
        avg_cost=round(cost / float(h.units), 4) if h.units > 0 else None,
        cost=cost,
        nav=float(h.fund.latest_nav) if h.fund.latest_nav else None,
        nav_date=h.fund.latest_nav_date,
        value=round(value, 2),
        gain=round(value - cost, 2),
        gain_percent=round((value - cost) / cost * PERCENT, 2) if cost > 0 else None,
        realised_gain=float(h.realised_gain),
        xirr=_rate(flows + _terminal(h)),
        first_date=h.first_date,
    )


def _latest_recommendation(db: Session, goal: Goal) -> Recommendation | None:
    found = history_for(db, goal)
    return found[0] if found else None


@dataclass(frozen=True)
class GoalView:
    status: GoalStatus
    rebalance: Rebalance | None
    recommendation: Recommendation | None
    expected_return: float  # fraction
    as_of: date | None


def _goal_view(
    db: Session,
    goal: Goal,
    holdings: list[Holding],
    flows: list[Flow],
    category: str | None,
    today: date,
) -> GoalView:
    plan = goal_service.calculate(goal, category, today)
    rate = plan.expected_return_used / PERCENT
    years = plan.years_to_goal
    value = sum(_value(h) for h in holdings)
    cost = sum(float(h.cost) for h in holdings)
    dates = [h.fund.latest_nav_date for h in holdings if h.fund.latest_nav_date]
    as_of = max(dates) if dates else None
    started = bool(flows)
    if started:
        # Once money is tracked, the holdings replace the "current savings" typed in Phase 3.
        projection = project_goal(
            GoalInputs(
                target_today=float(goal.target_amount),
                years=years,
                inflation_rate=float(goal.inflation_rate) / PERCENT,
                expected_return=rate,
                current_savings=value,
                monthly_sip=float(goal.monthly_sip),
                step_up_rate=float(goal.step_up_rate) / PERCENT,
            )
        )
        inflated, projected = projection.inflated_target, projection.projected_value
        funded, shortfall = projection.funded_percent, projection.shortfall
        required, on_track = projection.required_sip, projection.on_track
    else:
        inflated, projected = plan.inflated_target, plan.projected_value
        funded, shortfall = plan.funded_percent, plan.shortfall
        required, on_track = plan.required_sip, plan.on_track
    plan_value = grown_contributions(flows, rate, as_of or today) if started else 0.0

    recommendation = _latest_recommendation(db, goal)
    drift: Rebalance | None = None
    if recommendation is not None and value > 0:
        values: dict[str, float] = defaultdict(float)
        for h in holdings:
            values[sleeve_of(h.fund.category, h.fund.name, h.fund.asset_class)] += _value(h)
        target = {a["sleeve"]: a["weight"] / PERCENT for a in recommendation.allocation}
        drift = rebalance(values, target)

    terminal = [f for h in holdings for f in _terminal(h)]
    status = GoalStatus(
        goal_id=goal.id,
        name=goal.name,
        goal_type=goal.goal_type,
        target_year=goal.target_year,
        years_to_goal=years,
        status="not_started" if not started else ("on_track" if on_track else "off_track"),
        value=round(value, 2),
        cost=round(cost, 2),
        gain=round(value - cost, 2),
        xirr=_rate(flows + terminal),
        expected_return=plan.expected_return_used,
        plan_value=round(plan_value, 2),
        vs_plan=round(value - plan_value, 2),
        monthly_sip=float(goal.monthly_sip),
        inflated_target=inflated,
        projected_value=projected,
        funded_percent=funded,
        shortfall=shortfall,
        required_sip=required,
        rebalance_needed=drift.needed if drift else None,
        equity_actual=round(drift.equity_actual * PERCENT, 1) if drift else None,
        equity_target=round(drift.equity_target * PERCENT, 1) if drift else None,
    )
    return GoalView(status, drift, recommendation, rate, as_of)


def _inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def _alerts(view: GoalView, today: date) -> list[Alert]:
    status = view.status
    if status.status == "not_started":
        return []
    base = {"goal_id": status.goal_id, "goal_name": status.name}
    alerts: list[Alert] = []
    drift = view.rebalance
    if drift is not None and drift.needed:
        # Name the equity share when that drifted (the risk that matters most), otherwise
        # the part that drifted most.
        if abs(drift.equity_drift) > DRIFT_THRESHOLD:
            what, actual, target = "Equity", drift.equity_actual, drift.equity_target
        else:
            worst = max(drift.rows, key=lambda r: abs(r.drift))
            what, actual, target = worst.label, worst.actual, worst.target
        alerts.append(
            Alert(
                kind="rebalance",
                severity="warning",
                message=(
                    f"{what} is {actual:.0%} of this goal against {target:.0%} recommended. "
                    "Rebalance, or direct new money to the underweight part."
                ),
                **base,
            )
        )
    if status.status == "off_track":
        extra = (
            f" A monthly SIP of {_inr(status.required_sip)} would close the gap."
            if status.required_sip
            else ""
        )
        alerts.append(
            Alert(
                kind="off_track",
                severity="warning",
                message=(
                    f"Off track: at {status.expected_return:g}% a year the holdings and a SIP of "
                    f"{_inr(status.monthly_sip)} reach {_inr(status.projected_value)} of the "
                    f"{_inr(status.inflated_target)} needed in {status.target_year}.{extra}"
                ),
                **base,
            )
        )
    recommendation = view.recommendation
    if recommendation is None:
        alerts.append(
            Alert(
                kind="no_recommendation",
                severity="info",
                message="No recommendation yet: make one to check this goal's mix for drift.",
                **base,
            )
        )
    elif (
        recommendation.years_to_goal != status.years_to_goal
        or (today - recommendation.created_at.date()).days > STALE_AFTER_DAYS
    ):
        alerts.append(
            Alert(
                kind="stale_recommendation",
                severity="info",
                message=(
                    f"The recommendation is from {recommendation.created_at:%d %b %Y}, when the "
                    f"goal was {recommendation.years_to_goal} years away; refresh it, since the "
                    "safe equity share falls as the goal nears."
                ),
                **base,
            )
        )
    return alerts


def portfolio(db: Session, user: User, today: date | None = None) -> PortfolioRead:
    today = today or date.today()
    book = _book(db, user)
    names = {g.id: g.name for g in book.goals}
    holdings = [
        holding_read(
            h, book.flows[(h.goal_id, h.fund_id)], names.get(h.goal_id) if h.goal_id else None
        )
        for h in book.holdings
    ]
    cost = sum(h.cost for h in holdings)
    value = sum(h.value for h in holdings)
    all_flows = [f for flows in book.flows.values() for f in flows]
    terminal = [f for h in book.holdings for f in _terminal(h)]
    dates = [h.nav_date for h in holdings if h.nav_date and h.units > 0]
    totals = PortfolioTotals(
        cost=round(cost, 2),
        value=round(value, 2),
        gain=round(value - cost, 2),
        gain_percent=round((value - cost) / cost * PERCENT, 2) if cost > 0 else None,
        realised_gain=round(sum(h.realised_gain for h in holdings), 2),
        xirr=_rate(all_flows + terminal),
        as_of=max(dates) if dates else None,
    )
    statuses: list[GoalStatus] = []
    alerts: list[Alert] = []
    for goal in book.goals:
        mine = [h for h in book.holdings if h.goal_id == goal.id]
        flows = sorted(f for (g, _), fl in book.flows.items() if g == goal.id for f in fl)
        view = _goal_view(db, goal, mine, flows, book.category, today)
        statuses.append(view.status)
        alerts.extend(_alerts(view, today))
    alerts.sort(key=lambda a: a.severity != "warning")
    return PortfolioRead(totals=totals, holdings=holdings, goals=statuses, alerts=alerts)


def _month_ends(start: date, end: date) -> list[date]:
    """start, every month end strictly between, and end."""
    points = [start]
    year, month = start.year, start.month
    while True:
        last = date(year, month, calendar.monthrange(year, month)[1])
        if last >= end:
            break
        if last > start:
            points.append(last)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if end > start:
        points.append(end)
    return points


def goal_progress(db: Session, user: User, goal: Goal, today: date | None = None) -> GoalProgress:
    today = today or date.today()
    category = goal_service.risk_category(db, user)
    holdings = list(
        db.scalars(
            select(Holding)
            .options(joinedload(Holding.fund))
            .where(Holding.user_id == user.id, Holding.goal_id == goal.id)
            .order_by(Holding.id)
        )
    )
    transactions = list(
        db.scalars(
            select(Transaction)
            .where(Transaction.user_id == user.id, Transaction.goal_id == goal.id)
            .order_by(Transaction.txn_date, Transaction.id)
        )
    )
    flows = [_flow(t) for t in transactions]
    view = _goal_view(db, goal, holdings, flows, category, today)
    status = view.status
    end = view.as_of or today

    history: list[HistoryPoint] = []
    if transactions:
        first = transactions[0].txn_date
        series = {
            fund_id: nav_series(db, fund_id, first - timedelta(days=MAX_NAV_GAP_DAYS))
            for fund_id in {t.fund_id for t in transactions}
        }
        for point in _month_ends(first, max(end, first)):
            units: dict[int, Decimal] = defaultdict(Decimal)
            invested = 0.0
            for t in transactions:
                if t.txn_date > point:
                    break
                sign = 1 if t.txn_type == "buy" else -1
                units[t.fund_id] += sign * t.units / series[t.fund_id].multiplier(t.txn_date)
                invested += sign * float(t.amount)
            value = sum(float(u) * (series[f].adjusted_on(point) or 0.0) for f, u in units.items())
            history.append(
                HistoryPoint(
                    date=point,
                    invested=round(invested, 2),
                    value=round(value, 2),
                    plan=round(grown_contributions(flows, view.expected_return, point), 2),
                )
            )

    # Forward: today's value (or the Phase 3 savings before any transaction) plus the SIP.
    start_value = status.value if transactions else float(goal.current_savings)
    step_up = float(goal.step_up_rate) / PERCENT
    sip = float(goal.monthly_sip)
    projection = [ValuePoint(date=end, value=round(start_value, 2))]
    for year in range(1, status.years_to_goal + 1):
        grown = tvm.future_value(start_value, view.expected_return, year)
        if step_up:
            grown += tvm.step_up_sip_future_value(sip, view.expected_return, year, step_up)
        else:
            grown += tvm.sip_future_value(sip, view.expected_return, year * tvm.MONTHS_PER_YEAR)
        day = date(end.year + year, end.month, min(end.day, 28))
        projection.append(ValuePoint(date=day, value=round(grown, 2)))

    drift = view.rebalance
    rebalance_out = None
    if drift is not None and view.recommendation is not None:
        rebalance_out = RebalanceOut(
            rows=[
                DriftRowOut(
                    row=r.row,
                    label=r.label,
                    value=round(r.value, 2),
                    actual=round(r.actual * PERCENT, 1),
                    target=round(r.target * PERCENT, 1),
                    drift=round(r.drift * PERCENT, 1),
                    trade=round(r.trade, -2),  # to the nearest ₹100
                )
                for r in drift.rows
            ],
            equity_actual=round(drift.equity_actual * PERCENT, 1),
            equity_target=round(drift.equity_target * PERCENT, 1),
            equity_drift=round(drift.equity_drift * PERCENT, 1),
            needed=drift.needed,
            threshold=DRIFT_THRESHOLD * PERCENT,
            recommendation_id=view.recommendation.id,
            recommended_at=view.recommendation.created_at,
        )
    flows_by_fund: dict[int, list[Flow]] = defaultdict(list)
    for t in transactions:
        flows_by_fund[t.fund_id].append(_flow(t))
    return GoalProgress(
        status=status,
        history=history,
        projection=projection,
        target=ValuePoint(date=projection[-1].date, value=status.inflated_target),
        rebalance=rebalance_out,
        holdings=[holding_read(h, flows_by_fund[h.fund_id], goal.name) for h in holdings],
    )
