from langchain_core.runnables import RunnableConfig

from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    context = resume_build_service.load_context(get_deps(config).conn, state["application_id"])
    return {**context, "notes": []}
