"""Command line for administrators (there is no "sign up as admin" in the app).

uv run python -m app.admin make-admin someone@example.com
uv run python -m app.admin revoke-admin someone@example.com
"""

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User
from app.services import audit


def set_role(email: str, role: str) -> str:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            return f"No account with e-mail {email}"
        if user.role == role:
            return f"{user.email} is already {role}"
        audit.record(
            db,
            "cli.role.change",
            entity_type="user",
            entity_id=user.id,
            details={"email": user.email, "role": {"from": user.role, "to": role}},
        )
        user.role = role
        db.commit()
        return f"{user.email} is now {role}"


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("make-admin", "revoke-admin"):
        commands.add_parser(name).add_argument("email")
    args = parser.parse_args()
    print(set_role(args.email, "admin" if args.command == "make-admin" else "user"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
