import io
import zipfile

import pytest

from app.core.documents import extract_resume_text, redact_contact_details
from app.core.errors import BadRequest
from tests.documents import SAMPLE_RESUME_LINES, make_docx, make_pdf


def test_reads_text_from_a_pdf():
    text = extract_resume_text("resume.pdf", make_pdf(*SAMPLE_RESUME_LINES))

    assert "Data Engineer" in text
    assert "Airflow" in text


def test_reads_text_from_a_word_file():
    text = extract_resume_text("resume.docx", make_docx(*SAMPLE_RESUME_LINES))

    assert "Data Engineer" in text
    assert "Airflow" in text


@pytest.mark.parametrize("name", ["resume.doc", "resume.txt", "resume", "resume.pdf.exe"])
def test_rejects_unsupported_file_types(name):
    with pytest.raises(BadRequest):
        extract_resume_text(name, make_pdf("Python"))


def test_rejects_a_file_that_is_not_really_a_pdf():
    with pytest.raises(BadRequest):
        extract_resume_text("resume.pdf", b"this is not a pdf")


def test_rejects_a_file_that_is_not_really_a_word_document():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "hello")

    with pytest.raises(BadRequest):
        extract_resume_text("resume.docx", buffer.getvalue())


def test_rejects_a_word_file_that_expands_too_far():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (60 * 1024 * 1024))

    with pytest.raises(BadRequest):
        extract_resume_text("resume.docx", buffer.getvalue())


def test_explains_a_scanned_pdf_with_no_text():
    with pytest.raises(BadRequest, match="scanned"):
        extract_resume_text("resume.pdf", make_pdf())


def test_redacts_email_and_phone_before_text_leaves_the_app():
    text = "Sample Person\nsample.person@example.invalid | +64 21 000 0000\n(09) 123 4567\nPython"

    redacted = redact_contact_details(text)

    assert "example.invalid" not in redacted
    assert "000 0000" not in redacted
    assert "123 4567" not in redacted
    assert "Python" in redacted


def test_redaction_keeps_years_and_dates():
    text = "Developer 2019 - 2024, 3 years"

    assert redact_contact_details(text) == text
