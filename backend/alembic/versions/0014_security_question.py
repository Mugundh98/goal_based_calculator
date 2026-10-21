"""security question for password resets

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-21

"Forgot password" without e-mail: the user picks a question at sign-up (or later on the account
page) and its answer is stored as an Argon2 hash, like the password.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("security_question", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("security_answer_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "security_answer_hash")
    op.drop_column("users", "security_question")
