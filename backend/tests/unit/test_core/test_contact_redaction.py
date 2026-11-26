import pytest

from app.core.documents import (
    ai_resume_json,
    contact_for_text,
    redact_contact_details,
)
from app.schemas.tailoring import BaseSections, Bullet, ContactDetails, RoleSection


def test_a_short_name_does_not_change_words_that_contain_it():
    text = "Civil Client engineer, Li Wei's team"

    assert redact_contact_details(text, ContactDetails(name="Li")) == text


def test_a_short_name_does_not_change_longer_words_that_contain_it():
    text = "Developer for Dev Ops"

    assert redact_contact_details(text, ContactDetails(name="Dev")) == text


def test_a_full_name_is_removed_as_a_phrase_and_similar_words_survive():
    text = "ALEX  MORGAN\nData Analyst\nAlexander Street"

    out = redact_contact_details(text, ContactDetails(name="Alex Morgan"))

    assert out == "\nData Analyst\nAlexander Street"


def test_a_name_ending_in_punctuation_is_removed():
    text = "Alex Morgan Jr. | Data Analyst"

    out = redact_contact_details(text, ContactDetails(name="Alex Morgan Jr."))

    assert "Alex Morgan Jr." not in out
    assert "Data Analyst" in out


@pytest.mark.parametrize(
    "shown",
    [
        "https://www.linkedin.com/in/jane-doe",
        "http://linkedin.com/in/jane-doe/",
        "www.linkedin.com/in/jane-doe",
        "linkedin.com/in/jane-doe",
        "LinkedIn.com/in/Jane-Doe",
    ],
)
def test_every_linkedin_url_variant_for_the_stored_handle_is_removed(shown):
    text = f"Find me at {shown} for more."
    contact = ContactDetails(linkedin="https://www.linkedin.com/in/jane-doe")

    out = redact_contact_details(text, contact)

    assert " ".join(out.split()) == "Find me at for more."


def test_a_stored_contact_with_a_blank_name_still_redacts_the_name_in_the_text():
    text = "Alex Morgan\nData Analyst\nalex@example.invalid"

    contact = contact_for_text(ContactDetails(name=""), text)
    out = redact_contact_details(text, contact)

    assert "Alex Morgan" not in out
    assert "Data Analyst" in out


def test_a_stored_name_is_kept_and_the_text_name_fills_the_blank_fields():
    text = "Alex Morgan\nData Analyst\nalex@example.invalid"

    contact = contact_for_text(ContactDetails(name="Alexandra Morgan", email=None), text)

    assert contact.name == "Alexandra Morgan"
    assert contact.email == "alex@example.invalid"


def test_the_ai_payload_leaves_out_referees_and_role_locations_and_contact_details():
    sections = BaseSections(
        headline="Data Engineer",
        roles=[
            RoleSection(
                title="Data Engineer",
                employer="Example Retail Ltd",
                location="Wellington",
                dates="2022 - 2024",
                bullets=[Bullet(id="r0b0", text="Built pipelines.")],
            )
        ],
        referees="Pat Referee, pat@example.invalid, 021 555 0199",
    )

    payload = ai_resume_json(sections, ContactDetails(name="Alex Morgan"))

    assert "Wellington" not in payload
    assert "Referee" not in payload and "referee" not in payload.lower()
    assert "pat@example.invalid" not in payload and "021 555 0199" not in payload
    assert "Built pipelines." in payload
