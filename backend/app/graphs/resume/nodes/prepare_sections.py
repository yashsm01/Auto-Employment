from langchain_core.runnables import RunnableConfig

from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    deps = get_deps(config)
    sections = resume_build_service.ensure_sections(
        deps.conn,
        state["base_resume_id"],
        state["cached_sections"],
        state["raw_text"],
        deps.sections_chain,
    )
    return {"sections": sections}
