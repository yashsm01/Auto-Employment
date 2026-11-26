"""Employer contact details: what the employer's own pages say, and who they name for hiring."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import psycopg

from app.chains.recruiter_chain import RecruiterChain, RecruiterFound
from app.core.emails import find_emails
from app.core.errors import NotFound, ProviderError
from app.core.phones import nz_e164
from app.core.urls import safe_url, without_fragment
from app.providers.company.website_reader import PageReader, is_allowed_url
from app.repositories import companies_repo, contacts_repo
from app.schemas.contacts import EmployerContacts, Recruiter
from app.services.contact_extract import PageContacts, email_kind, extract_contacts, same_site
from app.services.prep_service import normalise

RECHECK_AFTER = timedelta(days=30)
# Home, contact and careers: never more than this many reads for one employer.
MAX_READS = 3
MAX_QUOTE_WORDS = 25
RECRUITER_ROLE = re.compile(
    r"recruit|talent|human resources|\bhr\b|people|hiring|careers", re.IGNORECASE
)
RATING = re.compile(r"(\d{1,2}(?:\.\d)?) \((\d+)\)")
NO_WEBSITE = "No website to read."
NOT_SET_UP = "Website reading is not set up."
RECRUITER_FAILED = "Could not check for a hiring contact."


@dataclass
class ContactTools:
    reader: PageReader | None
    recruiter: RecruiterChain | None


@dataclass
class _Page:
    url: str
    text: str
    found: PageContacts


def verify_recruiter(found: RecruiterFound, page_text: str) -> bool:
    """A named person is kept only when the name, quote, role and email all appear on the page."""
    if not found.name.strip() or normalise(found.name) not in normalise(page_text):
        return False
    quote = found.quote.strip()
    if not quote or len(quote.split()) > MAX_QUOTE_WORDS:
        return False
    if normalise(quote) not in normalise(page_text):
        return False
    if not RECRUITER_ROLE.search(found.role):
        return False
    return not found.email or found.email.strip().casefold() in find_emails(page_text)


def _reason(error: ProviderError) -> str:
    return str(error).removeprefix(f"{error.provider}: ")


def _readable(url: str, website: str) -> bool:
    """Our own site's http(s) pages only. Job boards and LinkedIn are never read."""
    return bool(safe_url(url)) and is_allowed_url(url) and same_site(url, website)


@dataclass
class _Site:
    pages: list[_Page]
    complete: bool  # every page we tried to read was read
    transient: bool  # a read failed for a reason that may pass, so the site is retried soon


_TRANSIENT = re.compile(r"request failed \(.*\)|HTTP (?:429|5\d\d)")


def _transient(reason: str) -> bool:
    """A timeout, a dropped connection, HTTP 429 or a 5xx. A refusal is not transient."""
    return bool(_TRANSIENT.fullmatch(reason))


def _web_address(website: str) -> str:
    """Job sources often give a bare host such as www.example.co.nz. Only those get https://."""
    try:
        has_scheme = bool(urlsplit(website).scheme)
    except ValueError:
        return website
    return website if has_scheme else f"https://{website}"


def _key(url: str) -> str:
    """A page's identity: without its fragment or a trailing slash."""
    return without_fragment(url).rstrip("/")


def _read(reader: PageReader, url: str, label: str, notes: list[str]) -> tuple[str | None, bool]:
    """The page text, or None with whether the failure was transient."""
    try:
        return reader.read(url), False
    except ProviderError as error:
        reason = _reason(error)
        notes.append(f"Could not read the {label} ({reason}).")
        return None, _transient(reason)


def _read_site(reader: PageReader, website: str, notes: list[str]) -> _Site:
    """The home page, then the contact and careers pages it links to, at most MAX_READS in all."""
    home_text, transient = _read(reader, website, "website", notes)
    if home_text is None:
        return _Site([], complete=False, transient=transient)
    home = extract_contacts(home_text, website)
    pages = [_Page(website, home_text, home)]
    complete = True
    reads = 1
    seen = {_key(website)}
    for url, label in ((home.contact_url, "contact page"), (home.careers_url, "careers page")):
        if not url or not _readable(url, website) or _key(url) in seen or reads >= MAX_READS:
            continue
        seen.add(_key(url))
        reads += 1
        text, failed = _read(reader, url, label, notes)
        if text is None:
            complete = False
            transient = transient or failed
        else:
            pages.append(_Page(url, text, extract_contacts(text, url)))
    return _Site(pages, complete=complete, transient=transient)


def _recruiter(found: RecruiterFound, page: _Page) -> dict[str, Any]:
    phone = None
    numbers = {nz_e164(display) for display in page.found.phones}
    if found.phone and nz_e164(found.phone) in numbers:
        phone = found.phone
    return {
        "name": found.name.strip(),
        "title": found.role.strip(),
        "email": found.email.strip().casefold() if found.email else None,
        "phone": phone,
        "source_url": page.url,
    }


def _check_recruiters(
    tools: ContactTools, pages: list[_Page], name: str, notes: list[str]
) -> tuple[bool, list[dict[str, Any]]]:
    """Ask the AI about the contact and careers pages only. Returns (any check finished, people)."""
    if tools.recruiter is None:
        return False, []
    finished = False
    people: list[dict[str, Any]] = []
    names: set[str] = set()
    for page in pages[1:]:
        try:
            answer = tools.recruiter.run(page.text, name)
        except ProviderError:
            notes.append(RECRUITER_FAILED)
            continue
        finished = True
        for found in answer.contacts:
            key = found.name.strip().casefold()
            if key in names or not verify_recruiter(found, page.text):
                continue
            names.add(key)
            people.append(_recruiter(found, page))
    return finished, people


def _linkedin(pages: list[_Page]) -> tuple[str, str] | None:
    """The first LinkedIn company link, the home page first. It is shown, never read."""
    for page in pages:
        url = safe_url(page.found.linkedin_url)
        if url:
            return url, page.url
    return None


def _site_facts(pages: list[_Page], skip: set[str]) -> list[tuple[str, str, str]]:
    """What the pages say, as (field, value, source page), in the order they appear."""
    home = pages[0]
    rows: list[tuple[str, str, str]] = []
    for page in pages:
        for email in page.found.emails:
            if email not in skip:
                field = "hiring_email" if email_kind(email) == "hiring" else "email"
                rows.append((field, email, page.url))
        rows.extend(("phone", phone, page.url) for phone in page.found.phones)
    # Links are shown, not read. A link to the home page itself (an anchor) is not one.
    for field, url in (("contact_page", home.found.contact_url),
                       ("careers_page", home.found.careers_url)):
        if url and safe_url(url) and is_allowed_url(url) and _key(url) != _key(home.url):
            rows.append((field, url, home.url))
    linkedin = _linkedin(pages)
    if linkedin:
        rows.append(("linkedin", linkedin[0], linkedin[1]))
    return rows


def lookup(
    conn: psycopg.Connection,
    company_id: UUID,
    tools: ContactTools,
    now: datetime,
    force: bool = False,
) -> EmployerContacts:
    """Read the employer's own pages and store what they say. Notes describe this run."""
    company = _company(conn, company_id)
    checked = company["contacts_checked_at"]
    if not force and checked and now - checked < RECHECK_AFTER:
        return view(conn, company_id)
    if tools.reader is None:
        return view(conn, company_id).model_copy(update={"notes": [NOT_SET_UP]})

    notes: list[str] = []
    transient = False
    website = company["website"]
    if not website:
        notes.append(NO_WEBSITE)
    else:
        website = _web_address(website)
        if not (safe_url(website) and is_allowed_url(website)):
            notes.append("Could not read the website (address not allowed).")
        else:
            site = _read_site(tools.reader, website, notes)
            transient = site.transient
            if site.pages:
                _store_site(conn, company_id, company["name"], site, tools, now, notes)
    # A transient failure leaves the site due, so the next automatic lookup reads it again.
    if not transient:
        contacts_repo.set_checked(conn, company_id, now)
    return view(conn, company_id).model_copy(update={"notes": notes})


def _store_site(
    conn: psycopg.Connection,
    company_id: UUID,
    name: str,
    site: _Site,
    tools: ContactTools,
    now: datetime,
    notes: list[str],
) -> None:
    pages = site.pages
    finished, people = _check_recruiters(tools, pages, name, notes)
    recruiter_emails = {person["email"] for person in people if person["email"]}
    general = [
        email for page in pages for email in page.found.emails
        if email_kind(email) == "general" and email not in recruiter_emails
    ]
    if site.complete:
        # Every page was read, so what the site no longer shows is gone.
        companies_repo.delete_website_facts(conn, company_id, companies_repo.CONTACT_FIELDS)
    for position, (field, value, url) in enumerate(_site_facts(pages, recruiter_emails)):
        # Newest first, and in page order within this lookup.
        companies_repo.upsert_website_fact(
            conn, company_id, field, value, url, now - timedelta(microseconds=position)
        )
    linkedin = _linkedin(pages)
    if linkedin:
        contacts_repo.fill_linkedin(conn, company_id, linkedin[0])
    if general:
        contacts_repo.fill_email(conn, company_id, general[0])
    if finished:
        contacts_repo.delete_website_recruiters(conn, company_id)
        for person in people:
            contacts_repo.add_recruiter(conn, company_id, **person, checked_at=now)


def view(conn: psycopg.Connection, company_id: UUID) -> EmployerContacts:
    company = _company(conn, company_id)
    facts = companies_repo.list_facts(conn, company_id)
    recruiters = contacts_repo.list_recruiters(conn, company_id)
    recruiter_emails = {row["email"] for row in recruiters if row["email"]}

    phone, phone_source = _phone(facts, company["phone"])
    rating, rating_count = _rating(_first(facts, "rating", None))
    linkedin = _first(facts, "linkedin", "website") or company["linkedin_url"]
    return EmployerContacts(
        phone=phone,
        phone_source=phone_source,
        emails=_emails(facts, "email", recruiter_emails),
        hiring_emails=_emails(facts, "hiring_email", recruiter_emails),
        website=safe_url(company["website"]),
        contact_page=safe_url(_first(facts, "contact_page", "website")),
        careers_page=safe_url(_first(facts, "careers_page", "website")),
        linkedin=safe_url(linkedin),
        hours=_hours(_first(facts, "opening_hours", None)),
        rating=rating,
        rating_count=rating_count,
        recruiters=[
            Recruiter(
                name=row["name"],
                role=row["title"] or "",
                email=row["email"],
                phone=row["phone"],
                source_url=row["source_url"],
            )
            for row in recruiters
        ],
        checked_at=company["contacts_checked_at"],
    )


def _company(conn: psycopg.Connection, company_id: UUID) -> dict[str, Any]:
    company = contacts_repo.get_company(conn, company_id)
    if company is None:
        raise NotFound("employer not found")
    return company


def _first(facts: list[dict[str, Any]], field: str, source: str | None) -> str | None:
    for fact in facts:
        if fact["field"] == field and (source is None or fact["source"] == source):
            return fact["value"]
    return None


def _emails(facts: list[dict[str, Any]], field: str, exclude: set[str]) -> list[str]:
    """Addresses from the employer's own pages, minus any that belong to a named recruiter."""
    return [
        fact["value"] for fact in facts
        if fact["field"] == field and fact["source"] == "website"
        and fact["value"] not in exclude
    ]


def _phone(facts: list[dict[str, Any]], job_phone: str | None) -> tuple[str | None, str | None]:
    """Maps first, then the employer's site, then a phone seen in a job advert."""
    for source, label in (("places", "Google Maps"), ("website", "Website")):
        value = _first(facts, "phone", source)
        if value:
            return value, label
    return (job_phone, "Job advert") if job_phone else (None, None)


def _hours(value: str | None) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()] if value else []


def _rating(value: str | None) -> tuple[float | None, int | None]:
    match = RATING.fullmatch(value.strip()) if value else None
    if not match:
        return None, None
    return float(match[1]), int(match[2])
