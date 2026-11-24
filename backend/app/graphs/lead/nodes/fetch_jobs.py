from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import lead_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    deps = get_deps(config)
    jobs, errors, report = lead_service.fetch_all(
        deps.sources, state["queries"], state["prefs"].regions
    )
    note_errors = [note["detail"] for note in deps.source_notes if note["status"] == "error"]
    return {
        "fetched": jobs,
        "errors": [*state["errors"], *note_errors, *errors],
        "source_report": [*deps.source_notes, *report],
    }
