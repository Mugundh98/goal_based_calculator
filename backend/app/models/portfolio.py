"""The investor's own portfolio (Phase 9): transactions, and the holdings derived from them."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.market import Fund, Nav
from app.models.profile import Money

TRANSACTION_TYPES = ("buy", "sell")


class Transaction(Base):
    """One purchase or redemption: the source of truth for everything the tracker shows.

    Never updated in place; a mistake is corrected by deleting it and entering it again, so
    holdings only ever change through insert and delete.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("txn_type IN ('buy', 'sell')", name="ck_transactions_txn_type"),
        CheckConstraint("amount > 0 AND units > 0 AND nav > 0", name="ck_transactions_positive"),
        # The transaction list (newest first) and "all of a user's flows" for XIRR.
        Index("ix_transactions_user_date", "user_id", "txn_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # NULL = not assigned to a goal. Deleting a goal keeps its transactions (they really
    # happened) and releases them to "unassigned"; the holdings are then rebuilt.
    goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), index=True
    )
    # RESTRICT: a fund someone holds cannot disappear from the database.
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id", ondelete="RESTRICT"), index=True)
    txn_type: Mapped[str] = mapped_column(String(4))
    txn_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)  # rupees paid or received, positive
    units: Mapped[Decimal] = mapped_column(Numeric(18, 4))  # as on the statement that day
    nav: Mapped[Decimal] = mapped_column(Nav)  # price used
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fund: Mapped[Fund] = relationship()


class Holding(Base):
    """Units held in one fund for one goal: DERIVED from transactions and stored (materialised).

    Rebuilt from the transactions of that (user, goal, fund) inside the same database
    transaction that inserts or deletes one, so it can never disagree with them. Stored because
    every portfolio page needs the units and cost of all positions, and replaying the whole
    history (FIFO lots, unit changes) on each read would repeat the same work. The market value
    is NOT stored: it changes with every day's NAV and is computed when read.
    """

    __tablename__ = "holdings"
    __table_args__ = (
        # One row per user, goal and fund; NULLS NOT DISTINCT (PostgreSQL 15+) makes the
        # unassigned (goal_id NULL) position of a fund unique too.
        UniqueConstraint(
            "user_id",
            "goal_id",
            "fund_id",
            name="uq_holdings_user_goal_fund",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("units >= 0 AND cost >= 0", name="ck_holdings_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # CASCADE: derived rows are disposable; the service rebuilds them after a goal is deleted.
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"))
    fund_id: Mapped[int] = mapped_column(ForeignKey("funds.id", ondelete="RESTRICT"))
    units: Mapped[Decimal] = mapped_column(Numeric(20, 6))  # in the fund's current units
    cost: Mapped[Decimal] = mapped_column(Money)  # FIFO cost of the units held
    realised_gain: Mapped[Decimal] = mapped_column(Money, server_default="0")
    first_date: Mapped[date] = mapped_column(Date)
    last_date: Mapped[date] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    fund: Mapped[Fund] = relationship()
