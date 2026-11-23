from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import lead_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    deps = get_deps(config)
    return {"clean_jobs": lead_service.clean(deps.conn, state["fetched"], state["prefs"], deps.now)}
