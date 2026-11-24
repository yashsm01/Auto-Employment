from datetime import UTC, date, datetime

from app.core.workdays import add_working_days, nz_today


def test_five_working_days_skip_the_weekend():
    assert add_working_days(date(2026, 11, 27), 5) == date(2026, 12, 4)  # Fri -> Fri


def test_a_weekend_start_counts_from_monday():
    assert add_working_days(date(2026, 11, 28), 1) == date(2026, 11, 30)  # Sat -> Mon


def test_today_is_the_new_zealand_date():
    assert nz_today(datetime(2026, 11, 30, 11, 30, tzinfo=UTC)) == date(2026, 12, 1)
