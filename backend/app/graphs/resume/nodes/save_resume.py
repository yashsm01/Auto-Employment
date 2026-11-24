from pathlib import Path

from langchain_core.runnables import RunnableConfig

from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    resume_id = resume_build_service.save(get_deps(config).conn, state, Path(state["pdf_path"]))
    return {"resume_id": resume_id}
