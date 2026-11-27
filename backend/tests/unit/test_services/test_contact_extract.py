import pytest

from app.providers.company.careers import find_careers_link
from app.services.contact_extract import email_kind, extract_contacts, same_site

PAGE = """[Contact us](https://example.co.nz/contact) [Careers](/careers)
Email [info@example.co.nz](mailto:info@example.co.nz) or jobs@example.co.nz. Call 03-688 1234.
[LinkedIn](https://www.linkedin.com/company/example-freight/) INFO@example.co.nz
Owner: kiwi.plumbing@gmail.com · Write to jobs [at] example.co.nz"""


def test_finds_emails_phones_and_links_once():
    found = extract_contacts(PAGE, "https://example.co.nz/")
    assert found.emails == ["info@example.co.nz", "jobs@example.co.nz", "kiwi.plumbing@gmail.com"]
    assert found.phones == ["03-688 1234"]
    assert found.contact_url == "https://example.co.nz/contact"
    assert found.careers_url == "https://example.co.nz/careers"
    assert found.linkedin_url == "https://www.linkedin.com/company/example-freight/"


def test_obfuscated_addresses_are_not_guessed():
    assert "jobs@example.co.nz" not in extract_contacts("jobs [at] example.co.nz", "https://e.nz").emails


def test_phones_are_deduplicated_by_nz_number():
    found = extract_contacts("Call 03 688 1234 or +64 3 688 1234 today.", "https://e.nz")
    assert found.phones == ["03 688 1234"]


@pytest.mark.parametrize("display", [
    "021 123 4567", "027-555 1234", "0800 123 456", "0508 123 456", "(09) 123 4567",
    "03.688.1234", "+64 21 123 4567", "03-688 1234", "+64 (0) 3 688 1234",
])
def test_nz_phone_formats_are_found_as_written(display):
    assert extract_contacts(f"Call {display} now.", "https://e.nz").phones == [display]


def test_adjacent_numbers_are_split_not_merged():
    found = extract_contacts("Call 03 688 1234 027 555 1234 today.", "https://e.nz")
    assert found.phones == ["03 688 1234", "027 555 1234"]


@pytest.mark.parametrize("text", [
    "Dated 2026-11-26.", "Est. 2019 in Otago.", "Ref 1234567890123",
    "Dated 01-02-2026", "Ref 0123456789012",
])
def test_dates_years_and_plain_digit_runs_are_not_phones(text):
    assert extract_contacts(text, "https://e.nz").phones == []


def test_malformed_contact_href_does_not_raise():
    found = extract_contacts("[Contact](http://[)", "https://e.nz/")
    assert found.contact_url is None


def test_malformed_careers_href_does_not_raise():
    found = extract_contacts("[Careers](http://[) [Jobs](/jobs)", "https://e.nz/")
    assert found.careers_url == "https://e.nz/jobs"


def test_no_links_when_the_page_has_none():
    found = extract_contacts("Nothing useful here.", "https://e.nz/")
    assert found.contact_url is None
    assert found.careers_url is None
    assert found.linkedin_url is None


@pytest.mark.parametrize(("address", "kind"), [("careers@x.nz", "hiring"), ("HR@x.nz", "hiring"),
    ("recruitment@x.nz", "hiring"), ("info@x.nz", "general"), ("sam@x.nz", "general")])
def test_email_kind(address, kind):
    assert email_kind(address) == kind


@pytest.mark.parametrize(("url", "website", "expected"), [
    ("https://www.example.co.nz/contact", "https://example.co.nz/", True),
    ("https://example.co.nz/careers", "https://www.example.co.nz", True),
    ("https://other.co.nz/careers", "https://example.co.nz/", False),
    ("http://[x", "https://e.nz", False),
])
def test_same_site_ignores_www(url, website, expected):
    assert same_site(url, website) is expected


def test_a_contact_link_with_a_fragment_is_the_page_itself_without_it():
    found = extract_contacts("[Contact](/contact#form)", "https://example.co.nz/")
    assert found.contact_url == "https://example.co.nz/contact"


def test_a_careers_link_with_a_fragment_is_the_page_itself_without_it():
    assert find_careers_link("[Careers](/careers#roles)", "https://example.co.nz/") == (
        "https://example.co.nz/careers"
    )


@pytest.mark.parametrize("markdown", [
    "[Contactless payments](/x/contactless-payments)",
    "[Read more](https://example.co.nz/x/contactless-cafe-payment-insight.webp)",
    "[Contact](/images/contact.png)",
    "[Contact us](/contact-us.jpg)",
    "[Get in touch](/contact.pdf)",
    "[Contact](/contact.svg)",
    "[Contact](/contact.gif)",
    "[Contact](/contact.docx)",
])
def test_contactless_and_image_links_are_not_contact_pages(markdown):
    assert extract_contacts(markdown, "https://example.co.nz/").contact_url is None


@pytest.mark.parametrize("markdown", [
    "[Contact us](/contact-us)",
    "[Contact](https://example.co.nz/contact)",
    "[Get in touch](/get-in-touch)",
    "[Contact us](/contact.html)",
])
def test_contact_pages_are_found(markdown):
    assert extract_contacts(markdown, "https://example.co.nz/").contact_url is not None


@pytest.mark.parametrize("markdown", [
    "[Careers](/assets/careers-banner.webp)",
    "[Jobs](/jobs.pdf)",
    "[Careers](https://example.co.nz/careers.png)",
    "[Vacancies](/vacancies.docx)",
])
def test_image_and_document_links_are_never_careers_pages(markdown):
    assert find_careers_link(markdown, "https://example.co.nz/") is None
