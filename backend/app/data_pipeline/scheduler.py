"""Runs the pipeline jobs on a timetable inside the API process (APScheduler).

Enabled with SCHEDULER_ENABLED=true. Enable it in ONE process only: with several API workers
each would start its own scheduler. (A second copy would not corrupt anything - the partial
unique index on job_runs lets only one run of a job proceed - but it would waste work.)

All times are India time, when the sources publish:
  AMFI NAVs        by about 11 pm on business days  -> NAVs at 23:30, then fund metrics
  NSE index closes after 3:30 pm                    -> 18:30, Monday to Friday
  MOSPI CPI        on the 12th of each month        -> the 13th at 10:00
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.data_pipeline.jobs import run_job

logger = logging.getLogger(__name__)
TIMEZONE = "Asia/Kolkata"


def daily_update() -> None:
    """Today's NAVs, then the metrics that depend on them."""
    if run_job("daily_nav", triggered_by="scheduler").status == "success":
        run_job("fund_metrics", triggered_by="scheduler")


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        timezone=TIMEZONE,
        job_defaults={
            "coalesce": True,  # after downtime, run a missed job once, not once per miss
            "max_instances": 1,
            "misfire_grace_time": 6 * 3600,  # still run if the server was down for < 6 hours
        },
    )
    scheduler.add_job(daily_update, CronTrigger(hour=23, minute=30), id="daily_update")
    scheduler.add_job(
        run_job,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30),
        args=["index_history", "scheduler"],
        id="index_history",
    )
    scheduler.add_job(
        run_job,
        CronTrigger(day=13, hour=10, minute=0),
        args=["inflation", "scheduler"],
        id="inflation",
    )
    return scheduler
