from langchain_core.runnables import RunnableConfig

from app.graphs.lead.deps import get_deps
from app.graphs.lead.state import LeadState
from app.services import application_service, matching_service


def run(state: LeadState, config: RunnableConfig) -> LeadState:
    deps = get_deps(config)
    decisions = application_service.load_decisions(deps.conn, state["profile_id"])
    feedback = matching_service.build_feedback(decisions)

    passed = []
    for job in state["candidates"]:
        result = matching_service.score_job(
            deps.score_chain, state["resume"], state["prefs"], job.draft, feedback
        )
        application_id = application_service.record_scored(
            deps.conn, state["profile_id"], job, result, state["prefs"].shortlist_threshold
        )
        if application_id is not None:
            passed.append(application_id)

    count = len(state["candidates"])
    make_report = getattr(deps.score_chain, "report", None)
    report = make_report() if make_report else {"ai_scored": 0, "keyword_scored": count}
    return {
        "scored_count": count,
        "passed_ids": passed,
        "score_report": report,
        "errors": [*state["errors"], *report.get("errors", [])],
    }
