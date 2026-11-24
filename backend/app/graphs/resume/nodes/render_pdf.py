from langchain_core.runnables import RunnableConfig

from app.core.resume_pdf import render_resume_pdf
from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    path = resume_build_service.new_pdf_path(get_deps(config).upload_dir)
    resume = state["tailored"] or state["sections"]
    render_resume_pdf(state["contact"], resume, path, fallback_text=state["raw_text"])
    return {"pdf_path": str(path)}
