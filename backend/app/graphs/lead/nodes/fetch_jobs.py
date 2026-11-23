from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import lead_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    jobs, errors = lead_service.fetch_all(
        get_deps(config).sources, state["queries"], state["prefs"].regions
    )
    return {"fetched": jobs, "errors": [*state["errors"], *errors]}
