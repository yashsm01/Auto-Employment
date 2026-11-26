from datetime import date

from app.schemas.tailoring import ContactDetails
from app.services.outbox_service import follow_up_body, sign_cover_note, signature


def test_signature_combines_phone_and_whatsapp_when_the_same():
    contact = ContactDetails(
        name="Sample Person", phone="+64 21 000 0000", whatsapp="021 000 0000"
    )

    assert signature(contact) == (
        "Ngā mihi,\nSample Person\nPhone and WhatsApp: +64 21 000 0000"
    )


def test_signature_lists_both_when_they_differ():
    contact = ContactDetails(
        name="Sample Person", phone="021 000 0000", whatsapp="+64 22 111 1111"
    )

    assert signature(contact) == (
        "Ngā mihi,\nSample Person\nPhone: 021 000 0000\nWhatsApp: +64 22 111 1111"
    )


def test_signature_with_only_one_number_or_none():
    assert signature(ContactDetails(name="Sample Person")) == "Ngā mihi,\nSample Person"
    assert signature(ContactDetails()) == "Ngā mihi"
    assert signature(ContactDetails(whatsapp="022 111 1111")) == "Ngā mihi\nWhatsApp: 022 111 1111"


def test_a_cover_note_sign_off_is_replaced_by_the_signature():
    contact = ContactDetails(name="Sample Person", phone="021 000 0000")
    body = "Kia ora,\n\nI'm keen.\n\nNgā mihi,\nSample Person"

    assert sign_cover_note(body, contact) == (
        "Kia ora,\n\nI'm keen.\n\nNgā mihi,\nSample Person\nPhone: 021 000 0000"
    )


def test_a_cover_note_without_the_sign_off_gets_the_numbers_at_the_end():
    contact = ContactDetails(name="Sample Person", phone="021 000 0000")

    assert sign_cover_note("Kia ora,\n\nI'm keen.", contact) == (
        "Kia ora,\n\nI'm keen.\n\nPhone: 021 000 0000"
    )


def test_a_cover_note_is_unchanged_when_there_are_no_numbers():
    body = "Kia ora,\n\nI'm keen.\n\nNgā mihi,\nSample Person"

    assert sign_cover_note(body, ContactDetails(name="Sample Person")) == body


def test_follow_up_text():
    first = follow_up_body(
        "Data Engineer", date(2026, 11, 24), ContactDetails(name="Sample Person"), 1
    )
    second = follow_up_body("Data Engineer", date(2026, 11, 24), ContactDetails(), 2)

    assert "sent on 24 November 2026" in first
    assert first.endswith("Ngā mihi,\nSample Person")
    assert "once more" in second
    assert second.endswith("Ngā mihi")


def test_follow_up_sign_off_carries_the_numbers():
    contact = ContactDetails(name="Sample Person", phone="021 000 0000")

    body = follow_up_body("Data Engineer", date(2026, 11, 24), contact, 1)

    assert body.endswith("Ngā mihi,\nSample Person\nPhone: 021 000 0000")
