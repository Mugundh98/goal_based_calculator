"""funds a user adds by hand

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-21

A fund that is not in AMFI's list: owned by one user, no scheme code. Transactions and holdings
now refer to funds with NO ACTION instead of RESTRICT, so deleting a user (which cascades to
their transactions, holdings and own funds) is checked once at the end of the statement rather
than row by row in whatever order the cascade runs. A fund still in use still cannot be deleted.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUND_REFERENCES = (
    ("transactions", "transactions_fund_id_fkey"),
    ("holdings", "holdings_fund_id_fkey"),
)


def _refer_to_funds(on_delete: str) -> None:
    for table, name in FUND_REFERENCES:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, "funds", ["fund_id"], ["id"], ondelete=on_delete)


def upgrade() -> None:
    op.add_column("funds", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "funds_owner_user_id_fkey", "funds", "users", ["owner_user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_funds_owner_user_id", "funds", ["owner_user_id"])
    op.alter_column("funds", "scheme_code", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_funds_manual", "funds", "(owner_user_id IS NULL) = (scheme_code IS NOT NULL)"
    )
    _refer_to_funds("NO ACTION")


def downgrade() -> None:
    _refer_to_funds("RESTRICT")
    # Hand-added funds cannot exist without an owner: remove them with what refers to them.
    manual = "SELECT id FROM funds WHERE owner_user_id IS NOT NULL"
    op.execute(f"DELETE FROM holdings WHERE fund_id IN ({manual})")
    op.execute(f"DELETE FROM transactions WHERE fund_id IN ({manual})")
    op.execute("DELETE FROM funds WHERE owner_user_id IS NOT NULL")
    op.drop_constraint("ck_funds_manual", "funds", type_="check")
    op.alter_column("funds", "scheme_code", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_funds_owner_user_id", table_name="funds")
    op.drop_constraint("funds_owner_user_id_fkey", "funds", type_="foreignkey")
    op.drop_column("funds", "owner_user_id")
