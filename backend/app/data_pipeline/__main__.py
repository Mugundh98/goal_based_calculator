"""Command line for the pipeline jobs.

uv run python -m app.data_pipeline daily_nav
uv run python -m app.data_pipeline backfill_nav --asset-class equity --limit 50
uv run python -m app.data_pipeline index_history --full
uv run python -m app.data_pipeline inflation
uv run python -m app.data_pipeline fund_metrics
uv run python -m app.data_pipeline all          # first-time setup: every job in order
"""

import argparse
import json
import logging

from app.data_pipeline.jobs import BACKFILL_ASSET_CLASSES, JOBS, run_job

SETUP_ORDER = ["daily_nav", "backfill_nav", "index_history", "inflation", "fund_metrics"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.data_pipeline")
    parser.add_argument("job", choices=[*JOBS, "all"])
    parser.add_argument(
        "--asset-class",
        action="append",
        choices=BACKFILL_ASSET_CLASSES,
        help="backfill_nav: asset classes to backfill (repeatable; default: all four)",
    )
    parser.add_argument("--limit", type=int, help="backfill_nav: at most this many funds")
    parser.add_argument("--full", action="store_true", help="index_history: whole history")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    options = {
        "backfill_nav": {
            "asset_classes": tuple(args.asset_class or BACKFILL_ASSET_CLASSES),
            "limit": args.limit,
        },
        "index_history": {"full": args.full},
    }
    for job in SETUP_ORDER if args.job == "all" else [args.job]:
        run = run_job(job, triggered_by="cli", **options.get(job, {}))
        print(
            f"{job}: {run.status} - read {run.rows_read}, wrote {run.rows_written}"
            + (f" - {run.error}" if run.error else "")
        )
        print(json.dumps(run.details, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
