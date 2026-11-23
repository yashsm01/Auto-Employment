from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import application_service, matching_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    deps = get_deps(config)
    passed = []
    for job in state["candidates"]:
        result = matching_service.score_job(
            deps.score_chain, state["resume"], state["prefs"], job.draft
        )
        application_id = application_service.record_scored(
            deps.conn, state["profile_id"], job, result, state["prefs"].shortlist_threshold
        )
        if application_id is not None:
            passed.append(application_id)
    return {"scored_count": len(state["candidates"]), "passed_ids": passed}
