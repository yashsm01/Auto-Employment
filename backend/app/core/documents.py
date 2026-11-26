"""Reads uploaded resumes safely. Only PDF and Word (.docx) files are accepted."""

import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any

from docx import Document
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.core.errors import BadRequest
from app.schemas.tailoring import ContactDetails

ALLOWED_SUFFIXES = {".pdf", ".docx"}
MAX_PDF_PAGES = 20
MAX_DOCX_UNPACKED_BYTES = 40 * 1024 * 1024
MAX_TEXT_CHARS = 100_000

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w.])\+?\(?\d[\d \t().-]{6,}\d(?!\w)")
_YEAR_RANGE = re.compile(r"\d{4}\s*[-–]\s*\d{4}")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w%.-]+", re.IGNORECASE)


def file_suffix(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


def _read_pdf(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise BadRequest("This file is not a valid PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise BadRequest("This PDF is password protected. Remove the password and try again.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise BadRequest(f"This PDF has more than {MAX_PDF_PAGES} pages.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PyPdfError, ValueError, KeyError, TypeError, OSError):
        raise BadRequest("This PDF could not be read.") from None


def _read_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if "word/document.xml" not in {entry.filename for entry in entries}:
                raise BadRequest("This file is not a valid Word document.")
            if sum(entry.file_size for entry in entries) > MAX_DOCX_UNPACKED_BYTES:
                raise BadRequest("This Word document is too large to read.")
        document = Document(io.BytesIO(data))
    except BadRequest:
        raise
    except (zipfile.BadZipFile, ValueError, KeyError, OSError, AttributeError):
        raise BadRequest("This Word document could not be read.") from None
    except Exception:  # python-docx raises XML and package errors of several types
        raise BadRequest("This Word document could not be read.") from None

    lines = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.extend(cell.text for cell in row.cells)
    return "\n".join(lines)


def extract_resume_text(filename: str, data: bytes) -> str:
    suffix = file_suffix(filename)
    if suffix not in ALLOWED_SUFFIXES:
        raise BadRequest("Please upload a PDF or Word (.docx) file.")

    text = (_read_pdf(data) if suffix == ".pdf" else _read_docx(data)).strip()
    if not text:
        raise BadRequest(
            "No text was found. This looks like a scanned resume. "
            "Upload a text-based PDF or Word file."
        )
    if len(text) > MAX_TEXT_CHARS:
        raise BadRequest("This resume has too much text to read.")
    return text


_NAME_WORD = re.compile(r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿĀ-ž'’.-]*$")
_NOT_NAME_WORDS = {
    "curriculum", "vitae", "resume", "résumé", "cv", "profile", "summary", "contact",
    "developer", "engineer", "analyst", "manager", "consultant", "designer", "tester",
}


def _is_phone(value: str) -> bool:
    digits = sum(character.isdigit() for character in value)
    return 8 <= digits <= 15 and not _YEAR_RANGE.fullmatch(value)


def extract_contact_details(text: str) -> ContactDetails:
    """The name, email and phone at the top of a resume, found without AI."""
    email = _EMAIL.search(text)
    phone = next(
        (m.group(0).strip() for m in _PHONE.finditer(text) if _is_phone(m.group(0).strip())), None
    )
    name = None
    for line in [line.strip() for line in text.splitlines() if line.strip()][:5]:
        words = line.split()
        if (
            2 <= len(words) <= 4
            and all(_NAME_WORD.match(word) for word in words)
            and not {word.casefold() for word in words} & _NOT_NAME_WORDS
        ):
            name = line
            break
    linkedin = _LINKEDIN.search(text)
    return ContactDetails(
        name=name,
        email=email.group(0) if email else None,
        phone=phone,
        linkedin=linkedin.group(0) if linkedin else None,
    )


def contact_for_text(stored: ContactDetails | None, text: str) -> ContactDetails:
    """The stored contact, with each blank field filled from the text.

    Used before anything is sent to an AI model, so a blank stored name or LinkedIn link does not
    leave the name or link in the text unredacted.
    """
    found = extract_contact_details(text)
    if stored is None:
        return found
    merged: dict[str, Any] = {}
    for field in ContactDetails.model_fields:
        value = getattr(stored, field)
        if isinstance(value, str) and value.strip():
            merged[field] = value.strip()
        else:
            merged[field] = getattr(found, field)
    return ContactDetails(**merged)


def ai_resume_json(value: Any, contact: ContactDetails | None) -> str:
    """A resume as JSON for an AI model: no referees, no role locations, no contact details."""
    data = value.model_dump(exclude={"referees"})
    for role in data.get("roles", []):
        role.pop("location", None)
    return redact_contact_details(json.dumps(data, ensure_ascii=False), contact)


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(0).strip()
    digits = sum(character.isdigit() for character in value)
    if not 8 <= digits <= 15 or _YEAR_RANGE.fullmatch(value):
        return match.group(0)
    return "[phone removed]"


_MIN_NAME_LENGTH = 4  # Shorter names match too many ordinary words.


def _digits_key(value: str) -> str:
    """Digits only, with the NZ country code and trunk zero dropped, for comparing numbers."""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("64"):
        digits = digits[2:]
    return digits.lstrip("0")


_LINKEDIN_HANDLE = re.compile(r"linkedin\.com/in/([^/?#\s]+)", re.IGNORECASE)


def _strip_known_contact(text: str, contact: ContactDetails | None) -> str:
    """Remove the stored name, LinkedIn URL and WhatsApp number from the text."""
    if contact is None:
        return text
    words = (contact.name or "").split()
    if len(" ".join(words)) >= _MIN_NAME_LENGTH:
        # The whole name as one phrase, whitespace may vary, whole words only. Edges use
        # lookarounds rather than  so a name ending in punctuation ("Jr.") still matches.
        phrase = r"\s+".join(re.escape(word) for word in words)
        text = re.sub(rf"(?<!\w){phrase}(?!\w)", "", text, flags=re.IGNORECASE)
    if contact.linkedin:
        handle = _LINKEDIN_HANDLE.search(contact.linkedin)
        if handle:
            # Any scheme or www prefix, any case, and a trailing slash.
            pattern = (
                r"(?:https?://)?(?:www\.)?linkedin\.com/in/"
                rf"{re.escape(handle.group(1))}(?![\w%-]|\.\w)/?"
            )
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        else:
            url = re.sub(r"^https?://(www\.)?", "", contact.linkedin.strip(), flags=re.IGNORECASE)
            if url:
                text = re.sub(re.escape(url), "", text, flags=re.IGNORECASE)
    key = _digits_key(contact.whatsapp or "")
    if len(key) >= 6:
        text = _PHONE.sub(lambda m: "" if _digits_key(m.group(0)) == key else m.group(0), text)
    return text


def redact_contact_details(text: str, contact: ContactDetails | None = None) -> str:
    """Remove contact details before text goes to an AI provider.

    Email addresses and phone numbers are always masked. When the stored contact is given, its
    name, LinkedIn URL and WhatsApp number are removed too. Location and work-rights wording in
    the body are left, because roles need their locations.
    """
    text = _strip_known_contact(text, contact)
    return _PHONE.sub(_mask_phone, _EMAIL.sub("[email removed]", text))
