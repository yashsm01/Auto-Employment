from datetime import UTC, date, datetime

from app.core.workdays import add_working_days, nz_today


def test_five_working_days_skip_the_weekend():
    assert add_working_days(date(2026, 11, 27), 5) == date(2026, 12, 4)  # Fri -> Fri


def test_a_weekend_start_counts_from_monday():
    assert add_working_days(date(2026, 11, 28), 1) == date(2026, 11, 30)  # Sat -> Mon


def test_today_is_the_new_zealand_date():
    assert nz_today(datetime(2026, 11, 30, 11, 30, tzinfo=UTC)) == date(2026, 12, 1)



def test_christmas_and_mondayised_boxing_day_are_skipped():
    # Thu 24 Dec 2026 -> Fri 25 Christmas, weekend, Mon 28 (Boxing Day falls on Saturday).
    assert add_working_days(date(2026, 12, 24), 1) == date(2026, 12, 29)


def test_matariki_and_easter_are_skipped():
    assert add_working_days(date(2026, 7, 9), 1) == date(2026, 7, 13)  # Matariki Fri 10 Jul
    assert add_working_days(date(2026, 4, 2), 1) == date(2026, 4, 7)   # Good Friday, Easter Mon


def test_no_calls_on_a_mondayised_waitangi_day():
    from app.core.workdays import in_nz_business_hours

    # Waitangi Day 6 Feb 2027 is a Saturday, so Monday 8 Feb is the holiday. 10am NZ = 21:00 UTC.
    assert in_nz_business_hours(datetime(2027, 2, 7, 21, 0, tzinfo=UTC)) is False
