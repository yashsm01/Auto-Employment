"""Reads uploaded resumes safely. Only PDF and Word (.docx) files are accepted."""

import io
import re
import zipfile
from pathlib import PurePosixPath

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
    return ContactDetails(name=name, email=email.group(0) if email else None, phone=phone)


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(0).strip()
    digits = sum(character.isdigit() for character in value)
    if not 8 <= digits <= 15 or _YEAR_RANGE.fullmatch(value):
        return match.group(0)
    return "[phone removed]"


def redact_contact_details(text: str) -> str:
    """Remove email addresses and phone numbers before text goes to an AI provider."""
    return _PHONE.sub(_mask_phone, _EMAIL.sub("[email removed]", text))
