"""Runs the lead search every day while the backend is running."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import Settings
from app.core.errors import Conflict
from app.db.client import connect
from app.repositories import profiles_repo, runs_repo
from app.workers.lead_job import run_lead_search
from app.workers.prep_job import process_prep_queue
from app.workers.tailor_job import process_tailoring_queue

logger = logging.getLogger(__name__)

NZ_TIME = ZoneInfo("Pacific/Auckland")
MISFIRE_GRACE_SECONDS = 3600


def is_catch_up_due(last_run: datetime | None, now: datetime, hour: int) -> bool:
    """True if the most recent scheduled time passed without a successful run."""
    if last_run is None:
        return True
    local = now.astimezone(NZ_TIME)
    slot = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if local < slot:
        slot -= timedelta(days=1)
    return last_run < slot


def run_scheduled_search(settings: Settings) -> None:
    """Never raises, because a failed run must not stop the scheduler."""
    try:
        with connect(settings.database_url) as conn:
            profile_id = profiles_repo.first_profile_id(conn)
            if profile_id is None:
                logger.warning("Scheduled search skipped: no profile")
                return
            result = run_lead_search(conn, settings, profile_id)
            logger.info("Scheduled search finished: %s", result.status)
    except Conflict:
        logger.info("Scheduled search skipped: a search is already running")
    except Exception:
        logger.exception("Scheduled search failed")


def _catch_up(settings: Settings) -> None:
    try:
        with connect(settings.database_url) as conn:
            last_run = runs_repo.last_finished_at(conn, "lead")
    except Exception:
        logger.exception("Could not check the last search time")
        return
    if is_catch_up_due(last_run, datetime.now(UTC), settings.daily_search_hour):
        run_scheduled_search(settings)


def start_scheduler(settings: Settings) -> BackgroundScheduler | None:
    if not settings.scheduler_enabled or not settings.database_url:
        return None
    scheduler = BackgroundScheduler(timezone=NZ_TIME)
    scheduler.add_job(
        run_scheduled_search,
        CronTrigger(hour=settings.daily_search_hour, minute=0, timezone=NZ_TIME),
        args=[settings],
        id="daily-lead-search",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=MISFIRE_GRACE_SECONDS,
    )
    scheduler.add_job(_catch_up, "date", args=[settings], id="startup-catch-up")
    # Picks up resumes left waiting, for example after the backend restarts.
    scheduler.add_job(
        process_tailoring_queue,
        "interval",
        minutes=15,
        args=[settings],
        id="tailoring-queue",
        max_instances=1,
        coalesce=True,
    )
    # Picks up deep searches left waiting.
    scheduler.add_job(
        process_prep_queue,
        "interval",
        minutes=15,
        args=[settings],
        id="prep-queue",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
