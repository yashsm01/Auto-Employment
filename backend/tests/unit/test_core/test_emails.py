import pytest

from app.core.emails import find_emails, is_valid_email


def test_find_emails_reads_application_addresses_from_an_advert():
    text = "Send your CV to Jobs@Example.co.nz. Questions? hr@example.co.nz or jobs@example.co.nz"

    assert find_emails(text) == ["jobs@example.co.nz", "hr@example.co.nz"]


def test_find_emails_skips_no_reply_and_job_board_addresses():
    text = "noreply@example.co.nz, no-reply@x.com, alerts@seek.co.nz, apply@linkedin.com"

    assert find_emails(text) == []


@pytest.mark.parametrize(
    ("address", "valid"),
    [
        ("jobs@example.co.nz", True),
        ("first.last+cv@example.com", True),
        ("jobs@example", False),
        ("jobs example@x.com", False),
        ("jobs@x.com\r\nBcc: other@y.com", False),
        ("", False),
    ],
)
def test_is_valid_email(address, valid):
    assert is_valid_email(address) is valid
