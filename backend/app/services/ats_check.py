"""Rule-based ATS check for the master CV. It reports each rule as ok or not, with no score.

The text is what pypdf reads from the PDF, which is the text an applicant tracking system sees.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from app.core.resume_layout import (
    EDUCATION,
    INTERESTS,
    KEY_SKILLS,
    PROFILE,
    REFEREES,
    WORK_HISTORY,
)
from app.schemas.master_cv import AtsItem, AtsReport, MasterCV, MasterCVView

MAX_PAGES = 2
MIN_PROFILE_WORDS = 50
MAX_PROFILE_WORDS = 150
MAX_FILE_BYTES = 2_621_440  # 2.5 MB
MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
DATE_RANGE = re.compile(rf"^{MONTH} \d{{4}} [–-] (Present|{MONTH} \d{{4}})$")
# A personal detail counts only as a field label: at the start of a line or after "·" or "|",
# followed by ":" or "-". Ordinary words such as "Gender equality" or an employer name pass.
PERSONAL_DETAILS = re.compile(
    r"(?:^|[·|])[ \t]*(date of birth|dob|marital status|nationality|gender|religion)[ \t]*[:\-]",
    re.IGNORECASE | re.MULTILINE,
)


def _collapse(text: str) -> str:
    return " ".join(text.split()).casefold()


def _pdf_text(pdf_path: Path) -> tuple[str, int]:
    pages = PdfReader(str(pdf_path)).pages
    return "\n".join(page.extract_text() or "" for page in pages), len(pages)


def _name_and_contact(cv: MasterCV | MasterCVView, text: str) -> AtsItem:
    label = "Name and contact details at the top of the page body"
    name = (cv.contact.name or "").strip()
    if not name:
        return AtsItem(label=label, ok=False, detail="Add your name.")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if _collapse(first_line) != _collapse(name):
        return AtsItem(label=label, ok=False, detail="Put your name on the first line.")
    if not ((cv.contact.email or "").strip() or (cv.contact.phone or "").strip()):
        return AtsItem(label=label, ok=False, detail="Add an email or phone number.")
    return AtsItem(label=label, ok=True)


def _headings(cv: MasterCV | MasterCVView, text: str) -> AtsItem:
    expected = [PROFILE, KEY_SKILLS, WORK_HISTORY, EDUCATION]
    if (cv.sections.interests or "").strip():
        expected.append(INTERESTS)
    expected.append(REFEREES)
    lines = [_collapse(line) for line in text.splitlines()]
    label = "Standard section names in the NZ order"
    position = 0
    for line in lines:
        if position < len(expected) and line == _collapse(expected[position]):
            position += 1
    if position == len(expected):
        return AtsItem(label=label, ok=True)
    absent = [heading for heading in expected if _collapse(heading) not in lines]
    if absent:
        return AtsItem(label=label, ok=False, detail="Missing: " + ", ".join(absent))
    return AtsItem(label=label, ok=False, detail="Headings are out of order.")


def _dates(cv: MasterCV | MasterCVView) -> AtsItem:
    label = "Dates as month and year"
    if not cv.sections.roles:
        return AtsItem(label=label, ok=True, detail="No roles yet.")
    failing = [
        role.title.strip() or "(untitled role)"
        for role in cv.sections.roles
        if not DATE_RANGE.match(role.dates.strip())
    ]
    if failing:
        return AtsItem(label=label, ok=False, detail="Check the dates for: " + ", ".join(failing))
    return AtsItem(label=label, ok=True)


def _profile_length(cv: MasterCV | MasterCVView) -> AtsItem:
    words = len(cv.sections.summary.split())
    ok = MIN_PROFILE_WORDS <= words <= MAX_PROFILE_WORDS
    label = f"Profile of {MIN_PROFILE_WORDS} to {MAX_PROFILE_WORDS} words"
    return AtsItem(label=label, ok=ok, detail=f"{words} words")


def check(cv: MasterCV | MasterCVView, pdf_path: Path, docx_path: Path) -> AtsReport:
    text, pages = _pdf_text(pdf_path)
    pdf_bytes = pdf_path.stat().st_size
    docx_bytes = docx_path.stat().st_size

    found: list[str] = []
    for match in PERSONAL_DETAILS.finditer(text):
        label = " ".join(match.group(1).split())
        if label.casefold() not in {f.casefold() for f in found}:
            found.append(label)
    personal_ok = not found
    sizes_ok = pdf_bytes < MAX_FILE_BYTES and docx_bytes < MAX_FILE_BYTES
    items = [
        AtsItem(
            label="One column, no tables, text boxes or images",
            ok=True,
            detail="Every design is built this way.",
        ),
        _name_and_contact(cv, text),
        _headings(cv, text),
        _dates(cv),
        AtsItem(
            label=f"{MAX_PAGES} pages or fewer",
            ok=pages <= MAX_PAGES,
            detail=f"{pages} page" + ("" if pages == 1 else "s"),
        ),
        _profile_length(cv),
        AtsItem(
            label="No photo, date of birth, gender, marital status, nationality or religion",
            ok=personal_ok,
            detail="" if personal_ok else "Remove: " + ", ".join(found),
        ),
        AtsItem(
            label="Work rights stated",
            ok=bool((cv.contact.work_rights or "").strip()),
            detail="" if (cv.contact.work_rights or "").strip() else "Add your work rights.",
        ),
        AtsItem(
            label="Files under 2.5 MB",
            ok=sizes_ok,
            detail=f"PDF {round(pdf_bytes / 1024)} KB, Word {round(docx_bytes / 1024)} KB",
        ),
    ]
    return AtsReport(
        items=items, text=text, pages=pages, pdf_bytes=pdf_bytes, docx_bytes=docx_bytes
    )
