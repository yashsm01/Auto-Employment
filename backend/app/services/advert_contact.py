"""Who an advert names to contact, and whether it asks for applications on the job site only.

Plain code, no AI. Only what the advert itself says is read.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.core.emails import find_emails
from app.core.phones import nz_e164

# A person is named after one of these words: "Talk to Jane Example" and so on.
_TRIGGER = r"(?i:contact|call|email|speak to|talk to)\s+(?:the\s+|our\s+)?"
_NAME = re.compile(_TRIGGER + r"([A-Z][a-z'-]+(?:\s+[A-Z][a-z'-]+){1,2})\b")
_ROLE = re.compile(r"\s*,\s*([A-Z][A-Za-z&/-]*(?:\s+[A-Z][A-Za-z&/-]*){0,3})")
_TRIGGER_WORD = re.compile(r"(?i:contact|call|email|speak to|talk to)")
_PHONE = re.compile(r"\+?\d[\d ()-]{6,}\d")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
# A name with one of these words is a company, a team or a job title, not a person.
_NOT_A_PERSON = {
    word.casefold() for word in (
        "ltd", "limited", "group", "company", "co", "services", "solutions", "tech",
        "technologies", "systems", "engineering", "ministry", "council", "team", "department",
        "recruitment", "careers", "us", "our", "the", "hr", "freight", "logistics", "health",
        "software",
        "manager", "hiring", "recruiter", "talent", "engineer", "developer", "analyst",
        "consultant", "officer", "lead", "senior", "junior", "coordinator", "partner",
        "director", "head", "people",
    )
}
_SITE_ONLY_PHRASES = (
    "apply online only",
    "apply only through",
    "applications through seek only",
    "only applications submitted",
    "please do not contact",
    "no direct approaches",
    "no direct contact",
    "no agencies or direct contact",
    "no direct applications",
    "via our careers site only",
)
_GOVT_JOBS_HOST = "jobs.govt.nz"


@dataclass(frozen=True)
class AdvertContact:
    name: str | None
    role: str | None
    email: str | None
    phone: str | None


def _is_person(name: str, company: str | None) -> bool:
    """Two or three capitalised words that are neither a title, a company word nor the company."""
    if not 2 <= len(name.split()) <= 3:
        return False
    if company and name.casefold() == company.strip().casefold():
        return False
    return not any(word.casefold() in _NOT_A_PERSON for word in name.split())


def _phone(sentence: str) -> str | None:
    for match in _PHONE.finditer(sentence):
        text = match.group(0).strip()
        if nz_e164(text):
            return text
    return None


def _from_sentence(sentence: str, company: str | None) -> AdvertContact | None:
    """The contact a trigger sentence gives: a valid name plus a role, email or phone."""
    emails = find_emails(sentence)
    email = emails[0] if emails else None
    phone = _phone(sentence)
    match = _NAME.search(sentence)
    if match is None:
        return None
    candidate = match.group(1)
    after = _ROLE.match(sentence, match.end())
    name = role = None
    if after and not _is_person(candidate, company) and _is_person(after.group(1), company):
        # "Hiring Manager, Jane Smith": the title is the role, the name after it is the person.
        name, role = after.group(1), candidate
    elif _is_person(candidate, company):
        name = candidate
        role = after.group(1).strip() if after else None
    if name is None or (role is None and email is None and phone is None):
        return None
    return AdvertContact(name=name, role=role, email=email, phone=phone)


def advert_contact(description: str, company: str | None = None) -> AdvertContact | None:
    """The named contact in an advert, with the first email and NZ phone in the same sentence.

    A name counts only with a role after it or an email in the same sentence, so a bare company
    name ("Contact Example Freight Tech") gives nothing.
    """
    for sentence in _SENTENCE_END.split(description or ""):
        if not _TRIGGER_WORD.search(sentence):
            continue
        found = _from_sentence(sentence, company)
        if found is not None:
            return found
    return None


def applies_on_site_only(description: str, url: str | None) -> bool:
    """True when the advert says to apply on its own site or on a government job site only."""
    text = " ".join((description or "").split()).casefold()
    if any(phrase in text for phrase in _SITE_ONLY_PHRASES):
        return True
    try:
        host = (urlsplit(url or "").hostname or "").casefold()
    except ValueError:
        return False
    return host == _GOVT_JOBS_HOST or host.endswith(f".{_GOVT_JOBS_HOST}")
