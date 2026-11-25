from datetime import UTC, datetime

import pytest

from app.core.phones import nz_e164
from app.core.workdays import in_nz_business_hours


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("03-688 1234", "+6436881234"),
        ("021 123 4567", "+64211234567"),
        ("+64 22 437 9369", "+64224379369"),
        ("64 3 688 1234", "+6436881234"),
        ("0800 123 456", "+64800123456"),
        ("12345", None),
        ("", None),
        (None, None),
    ],
)
def test_nz_numbers_become_international(raw, expected):
    assert nz_e164(raw) == expected


@pytest.mark.parametrize(
    ("utc", "open_"),
    [
        (datetime(2026, 11, 23, 21, 0, tzinfo=UTC), True),   # Tue 10:00 NZ
        (datetime(2026, 11, 23, 19, 0, tzinfo=UTC), False),  # Tue 08:00 NZ
        (datetime(2026, 11, 24, 3, 45, tzinfo=UTC), False),  # Tue 16:45 NZ
        (datetime(2026, 11, 27, 22, 0, tzinfo=UTC), False),  # Sat 11:00 NZ
    ],
)
def test_calls_happen_only_in_nz_business_hours(utc, open_):
    assert in_nz_business_hours(utc) is open_
