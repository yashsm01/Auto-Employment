from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import application_service, matching_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    candidates, rejected = [], []
    for job in state["stored"]:
        keep = matching_service.passes_prefilter(state["resume"], job.draft)
        (candidates if keep else rejected).append(job)

    application_service.record_rejected(get_deps(config).conn, state["profile_id"], rejected)
    return {"candidates": candidates}
