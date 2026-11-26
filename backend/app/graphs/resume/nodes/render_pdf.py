import logging

from langchain_core.runnables import RunnableConfig

from app.core.resume_docx import render_resume_docx
from app.core.resume_pdf import render_resume_pdf
from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service

logger = logging.getLogger(__name__)
DOCX_FAILED = "The Word file could not be made this time. The PDF is ready."


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    path = resume_build_service.new_pdf_path(get_deps(config).upload_dir)
    resume = state["tailored"] or state["sections"]
    template = state.get("template", "classic")
    render_resume_pdf(
        state["contact"], resume, path, fallback_text=state["raw_text"], template=template
    )

    # The Word file sits beside the PDF with the same name. A failure there must not lose the
    # PDF, so it is logged (without any CV text), any partial file is removed, and tailoring
    # still finishes with a note.
    docx_path = path.with_suffix(".docx")
    notes = list(state.get("notes", []))
    try:
        render_resume_docx(
            state["contact"], resume, docx_path, template=template, fallback_text=state["raw_text"]
        )
    except Exception as error:
        logger.warning("Word file could not be written: %s", type(error).__name__)
        docx_path.unlink(missing_ok=True)
        notes.append(DOCX_FAILED)
    return {"pdf_path": str(path), "notes": notes}
