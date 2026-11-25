"""New Zealand dates for follow-ups and calls. Weekends and national public holidays are
skipped. Regional anniversary days are not, because they depend on the province."""

from datetime import date, datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo

NZ_TIME = ZoneInfo("Pacific/Auckland")


def nz_today(now: datetime) -> date:
    return now.astimezone(NZ_TIME).date()


def nz_day_start(now: datetime) -> datetime:
    local = now.astimezone(NZ_TIME)
    return datetime(local.year, local.month, local.day, tzinfo=NZ_TIME)


# Matariki moves with the Māori lunar calendar; dates set by law (MBIE, 2021).
_MATARIKI = {
    2022: (6, 24), 2023: (7, 14), 2024: (6, 28), 2025: (6, 20), 2026: (7, 10),
    2027: (6, 25), 2028: (7, 14), 2029: (7, 6), 2030: (6, 21), 2031: (7, 11),
    2032: (7, 2), 2033: (6, 24), 2034: (7, 7), 2035: (6, 29),
    2049: (6, 25), 2050: (7, 15), 2051: (6, 30), 2052: (6, 21),
}


def _easter_sunday(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 - the algorithm's own name
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_monday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7 + 7 * (n - 1))


def _observed(days: list[date], taken: set[date]) -> None:
    """Weekend holidays move to the next free weekday (the Holidays Act's "Mondayisation")."""
    for day in days:
        while day.weekday() >= 5 or day in taken:
            day += timedelta(days=1)
        taken.add(day)


@cache
def nz_public_holidays(year: int) -> frozenset[date]:
    holidays: set[date] = set()
    _observed([date(year, 1, 1), date(year, 1, 2)], holidays)
    _observed([date(year, 2, 6)], holidays)
    _observed([date(year, 4, 25)], holidays)
    _observed([date(year, 12, 25), date(year, 12, 26)], holidays)
    easter = _easter_sunday(year)
    holidays |= {easter - timedelta(days=2), easter + timedelta(days=1)}
    holidays.add(_nth_monday(year, 6, 1))   # King's Birthday
    holidays.add(_nth_monday(year, 10, 4))  # Labour Day
    if year in _MATARIKI:
        holidays.add(date(year, *_MATARIKI[year]))
    return frozenset(holidays)


def is_working_day(day: date) -> bool:
    return day.weekday() < 5 and day not in nz_public_holidays(day.year)


def add_working_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if is_working_day(current):
            added += 1
    return current


def in_nz_business_hours(now: datetime) -> bool:
    """Working days (no weekends or public holidays), 9:30 to 4:30 New Zealand time."""
    local = now.astimezone(NZ_TIME)
    minutes = local.hour * 60 + local.minute
    return is_working_day(local.date()) and 9 * 60 + 30 <= minutes < 16 * 60 + 30
