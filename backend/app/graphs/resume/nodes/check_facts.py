from langchain_core.runnables import RunnableConfig

from app.core.errors import ProviderError
from app.graphs.resume.deps import get_deps
from app.graphs.resume.state import ResumeState
from app.services import resume_build_service, tailoring_service


def run(state: ResumeState, config: RunnableConfig) -> ResumeState:
    tailored, sections = state["tailored"], state["sections"]
    if tailored is None or sections is None:
        return {}

    tailored, notes = tailoring_service.check_facts(sections, state["raw_text"], tailored)
    check_chain = get_deps(config).check_chain
    if check_chain is not None:
        try:
            result = check_chain.run(sections, tailored, state["facts"], state["job"])
        except ProviderError:
            notes.append("The AI fact check was unavailable, so only the automatic checks ran.")
        else:
            tailored, ai_notes = tailoring_service.apply_ai_check(sections, tailored, result)
            notes.extend(ai_notes)

    # The checks above only ever see the body. The greeting and sign-off are added last.
    body = tailored.cover_note or resume_build_service.plain_cover_body(state["job"])
    note = tailoring_service.frame_cover_note(body, state["contact"].name)
    tailored = tailored.model_copy(update={"cover_note": note})
    return {"tailored": tailored, "cover_note": note, "notes": notes}
