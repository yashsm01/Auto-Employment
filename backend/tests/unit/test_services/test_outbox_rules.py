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


def test_speculative_subject_and_cv_name_use_the_enquiry_wording():
    from app.services.outbox_service import speculative_attachment_name, speculative_subject

    assert speculative_subject("Timaru Trades", "Sample Person") == (
        "Enquiry about opportunities at Timaru Trades – Sample Person"
    )
    assert speculative_subject("Timaru\r\nTrades", None) == (
        "Enquiry about opportunities at Timaru Trades"
    )
    assert speculative_attachment_name("Sample Person") == "Sample Person - CV.pdf"
    assert speculative_attachment_name("Sample/Person: CV") == "Sample Person CV - CV.pdf"
    assert speculative_attachment_name(None) == "CV.pdf"


def test_speculative_body_ends_with_the_signature_and_the_exact_stop_line():
    from app.services.outbox_service import STOP_LINE, speculative_body

    contact = ContactDetails(name="Sample Person", phone="+64 21 000 0000")
    body = speculative_body("Kia ora,\n\nI'd like to enquire.\n\nNgā mihi,\nSample Person",
                            contact)

    assert STOP_LINE == "If you'd rather I didn't contact you again, just reply and I won't."
    assert body.endswith("Phone: +64 21 000 0000\n\n" + STOP_LINE)


def test_speculative_follow_up_refers_to_the_earlier_enquiry_and_ends_with_the_stop_line():
    from app.services.outbox_service import STOP_LINE, speculative_follow_up_body

    body = speculative_follow_up_body("Timaru Trades", date(2026, 11, 24),
                                      ContactDetails(name="Sample Person"))

    assert "my earlier email about opportunities at Timaru Trades" in body
    assert body.endswith(STOP_LINE)


def test_each_kind_has_its_own_follow_up_limit():
    from app.services.outbox_service import max_follow_ups

    assert max_follow_ups("advert") == 2
    assert max_follow_ups("speculative") == 1
