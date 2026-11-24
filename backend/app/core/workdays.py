"""New Zealand dates for follow-ups. Weekends are skipped; public holidays are not."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NZ_TIME = ZoneInfo("Pacific/Auckland")


def nz_today(now: datetime) -> date:
    return now.astimezone(NZ_TIME).date()


def nz_day_start(now: datetime) -> datetime:
    local = now.astimezone(NZ_TIME)
    return datetime(local.year, local.month, local.day, tzinfo=NZ_TIME)


def add_working_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current
