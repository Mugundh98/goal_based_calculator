"""Command line for deploying (Phase 13). Full steps: docs/deployment.md

Copy the reference data from the local database (DATABASE_URL, or --source) to a hosted one:
  uv run python -m app.deploy copy-data --target "postgresql://...neon.tech/neondb?sslmode=require"

Create (or with --reset, recreate) the demo account in the database DATABASE_URL points at.
The password comes from DEMO_PASSWORD, else a random one is generated and printed once:
  uv run python -m app.deploy demo-user [--email demo@example.com] [--reset]
"""

import argparse
import os
import sys

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.deploy import copy_data, demo


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.deploy")
    commands = parser.add_subparsers(dest="command", required=True)
    copy = commands.add_parser("copy-data", help="copy reference data to another database")
    copy.add_argument("--target", required=True, help="database URL to copy into")
    copy.add_argument("--source", help="database URL to copy from (default: DATABASE_URL)")
    copy.add_argument("--table", action="append", choices=copy_data.REFERENCE_TABLES)
    copy.add_argument("--replace", action="store_true", help="empty the target tables first")
    seed = commands.add_parser("demo-user", help="create the demo account")
    seed.add_argument("--email", default=demo.DEFAULT_EMAIL)
    seed.add_argument("--name", default=demo.DEFAULT_NAME)
    seed.add_argument("--reset", action="store_true", help="delete and recreate the account")
    args = parser.parse_args()

    if args.command == "copy-data":
        source_url = args.source or get_settings().database_url
        try:
            with copy_data.connect(source_url) as source, copy_data.connect(args.target) as target:
                print(f"From {copy_data.describe(source)} to {copy_data.describe(target)}")
                copied = copy_data.copy_tables(
                    source,
                    target,
                    tuple(args.table or copy_data.REFERENCE_TABLES),
                    replace=args.replace,
                    progress=print,
                )
                target.commit()
        except copy_data.CopyError as exc:
            print(f"Nothing copied: {exc}", file=sys.stderr)
            return 1
        print(f"Copied {sum(copied.values()):,} rows into {len(copied)} tables.")
        return 0

    with SessionLocal() as db:
        try:
            result = demo.create_demo_user(
                db, args.email, os.environ.get("DEMO_PASSWORD"), args.name, reset=args.reset
            )
        except demo.DemoError as exc:
            print(exc, file=sys.stderr)
            return 1
    print(
        f"Demo account {result.user.email}: {len(result.goals)} goals, "
        f"{result.transactions} transactions, {result.recommendations} recommendations."
    )
    for note in result.notes:
        print(note)
    if not os.environ.get("DEMO_PASSWORD"):
        print(f"Password (shown once, store it somewhere safe): {result.password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
