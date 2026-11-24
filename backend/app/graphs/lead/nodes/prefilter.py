from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import application_service, matching_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    deps = get_deps(config)
    ranked = matching_service.rank_candidates(
        state["resume"], state["stored"], deps.embedder, deps.keep_similarity
    )
    application_service.record_rejected(deps.conn, state["profile_id"], ranked.rejected)
    return {"candidates": ranked.candidates, "errors": [*state["errors"], *ranked.errors]}
