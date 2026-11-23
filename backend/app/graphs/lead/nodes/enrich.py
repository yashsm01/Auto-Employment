from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import enrich_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    return {"stored": enrich_service.store_jobs(get_deps(config).conn, state["clean_jobs"])}
