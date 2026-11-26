"""Contact details (emails, phones, contact, careers and LinkedIn links) from an employer's page."""

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin, urlsplit

from app.core.emails import find_emails
from app.core.phones import nz_e164
from app.core.urls import without_fragment
from app.providers.company.careers import find_careers_link

# NZ numbers as written on pages, bounded to NZ shapes so adjacent numbers stay separate.
# Area parts: landline (0X, or (0X)), mobile (02X), toll-free (0800, 0508); a single space,
# dot or dash may separate groups. The international form drops the leading 0 and may write (0).
# A leading 0 or +64 is required, so years and dates such as 2026-11-26 never start a match.
_SEP = r"[ .-]?"
_BODY = rf"\d{{3}}{_SEP}\d{{3,5}}"
_DOMESTIC = rf"(?:\(0[3-79]\)|0[3-79]|02\d|0(?:800|508)){_SEP}{_BODY}"
_INTERNATIONAL = rf"\+64{_SEP}(?:\(0\){_SEP})?(?:2\d|[3-79]|800|508){_SEP}{_BODY}"
_PHONE = re.compile(rf"(?<![\w+])(?:{_INTERNATIONAL}|{_DOMESTIC})(?!\d)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)")
_CONTACT = re.compile(r"contact|get in touch|get-in-touch", re.IGNORECASE)
_LINKEDIN = re.compile(r"https?://(?:www\.)?linkedin\.com/company/[^\s)\"'>]+")
_HIRING_LOCAL_PARTS = frozenset({
    "careers", "jobs", "job", "hr", "recruit", "recruitment", "recruiting",
    "talent", "people", "employment", "vacancies", "apply",
})


@dataclass
class PageContacts:
    emails: list[str]
    phones: list[str]
    contact_url: str | None
    careers_url: str | None
    linkedin_url: str | None


def email_kind(address: str) -> Literal["hiring", "general"]:
    local_part = address.split("@", 1)[0].casefold()
    return "hiring" if local_part in _HIRING_LOCAL_PARTS else "general"


def _host(url: str) -> str | None:
    """The host without www., or None when the URL is malformed (pages are untrusted)."""
    try:
        return (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return None


def same_site(url: str, website: str) -> bool:
    url_host, site_host = _host(url), _host(website)
    return bool(url_host) and url_host == site_host


def _phones(page_text: str) -> list[str]:
    """Phones as written on the page, one per NZ number."""
    seen: set[str] = set()
    phones: list[str] = []
    for match in _PHONE.finditer(page_text):
        display = match.group(0).strip()
        number = nz_e164(display)
        if number and number not in seen:
            seen.add(number)
            phones.append(display)
    return phones


def _contact_url(page_text: str, page_url: str) -> str | None:
    for text, href in _MD_LINK.findall(page_text):
        try:
            path = urlsplit(href).path
            url = without_fragment(urljoin(page_url, href))
        except ValueError:
            continue
        if _CONTACT.search(text) or _CONTACT.search(path):
            return url
    return None


def extract_contacts(page_text: str, page_url: str) -> PageContacts:
    linkedin = _LINKEDIN.search(page_text)
    return PageContacts(
        emails=find_emails(page_text),
        phones=_phones(page_text),
        contact_url=_contact_url(page_text, page_url),
        careers_url=find_careers_link(page_text, page_url),
        linkedin_url=linkedin.group(0) if linkedin else None,
    )
