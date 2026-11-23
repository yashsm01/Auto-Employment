from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import lead_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    resume, prefs = lead_service.load_context(get_deps(config).conn, state["profile_id"])
    return {"resume": resume, "prefs": prefs, "errors": []}
