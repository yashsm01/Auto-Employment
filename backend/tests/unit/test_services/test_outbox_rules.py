from datetime import date

from app.schemas.tailoring import ContactDetails
from app.services.outbox_service import attachment_name, follow_up_body, subject_for


def test_subject_and_file_name_never_carry_line_breaks_from_a_job_title():
    title = "Data\r\nEngineer\tBcc: other@example.com"

    assert subject_for(title, "Sample Person") == (
        "Application for Data Engineer Bcc: other@example.com – Sample Person"
    )
    assert "\n" not in attachment_name(title, "Sample Person")
    assert attachment_name("Dev / Ops: Lead", None) == "Resume - Dev Ops Lead.pdf"


def test_follow_up_text_names_the_follow_up_number():
    first = follow_up_body("Data Engineer", date(2026, 11, 24), ContactDetails(), 1)
    second = follow_up_body("Data Engineer", date(2026, 11, 24), ContactDetails(), 2)

    assert first.startswith("Kia ora,\n\nI'm following up on my application for the Data Engineer")
    assert "once more" in second
