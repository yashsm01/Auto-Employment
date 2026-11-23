from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import application_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    application_service.shortlist(get_deps(config).conn, state["passed_ids"])
    return {}
