from langchain_core.runnables import RunnableConfig

from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service, tailoring_service


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    deps = get_deps(config)
    sections = state["sections"]
    if sections is None or deps.tailor_chain is None:
        note = resume_build_service.plain_cover_note(state["job"], state["contact"].name)
        return {"tailored": None, "cover_note": note, "ai_used": False}

    draft = deps.tailor_chain.run(sections, state["job"], state["facts"])
    tailored = tailoring_service.assemble(sections, draft)
    body = tailoring_service.cover_note_body(tailored.cover_note, state["contact"].name)
    tailored = tailored.model_copy(update={"cover_note": body})
    return {"tailored": tailored, "cover_note": tailored.cover_note, "ai_used": True}
