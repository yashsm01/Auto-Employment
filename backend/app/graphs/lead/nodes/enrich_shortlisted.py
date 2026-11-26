from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import enrich_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    deps = get_deps(config)
    if deps.employer_tools is None:
        return {"employers_researched": 0}
    count, errors = enrich_service.research_employers(
        deps.conn, state["passed_ids"], deps.employer_tools, deps.max_employer_profiles, deps.now
    )
    return {"employers_researched": count, "errors": [*state["errors"], *errors]}
