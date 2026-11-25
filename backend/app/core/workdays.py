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


def in_nz_business_hours(now: datetime) -> bool:
    """Monday to Friday, 9:30 to 4:30 New Zealand time."""
    local = now.astimezone(NZ_TIME)
    minutes = local.hour * 60 + local.minute
    return local.weekday() < 5 and 9 * 60 + 30 <= minutes < 16 * 60 + 30
