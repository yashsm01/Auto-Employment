from datetime import date

from app.services.outbox_service import attachment_name, follow_up_body, subject_for


def test_subject_and_file_name_never_carry_line_breaks_from_a_job_title():
    title = "Data\r\nEngineer\tBcc: other@example.com"

    assert subject_for(title, "Sample Person") == (
        "Application for Data Engineer Bcc: other@example.com – Sample Person"
    )
    assert "\n" not in attachment_name(title, "Sample Person")
    assert attachment_name("Dev / Ops: Lead", None) == "Resume - Dev Ops Lead.pdf"


def test_follow_up_text():
    first = follow_up_body("Data Engineer", date(2026, 11, 24), "Sample Person", 1)
    second = follow_up_body("Data Engineer", date(2026, 11, 24), None, 2)

    assert "sent on 24 November 2026" in first
    assert first.endswith("Ngā mihi,\nSample Person")
    assert "once more" in second
    assert second.endswith("Ngā mihi")
