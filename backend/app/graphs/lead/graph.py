from langgraph.graph import END, StateGraph

from .nodes import (
    build_queries,
    dedupe,
    enrich,
    enrich_shortlisted,
    fetch_jobs,
    load_resume_profile,
    prefilter,
    score,
    shortlist,
)
from .routes import after_score
from .state import LeadState


def build():
    g = StateGraph(LeadState)
    g.add_node("load_resume_profile", load_resume_profile.run)
    g.add_node("build_queries", build_queries.run)
    g.add_node("fetch_jobs", fetch_jobs.run)
    g.add_node("dedupe", dedupe.run)
    g.add_node("enrich", enrich.run)
    g.add_node("prefilter", prefilter.run)
    g.add_node("score", score.run)
    g.add_node("shortlist", shortlist.run)
    g.add_node("enrich_shortlisted", enrich_shortlisted.run)

    g.set_entry_point("load_resume_profile")
    g.add_edge("load_resume_profile", "build_queries")
    g.add_edge("build_queries", "fetch_jobs")
    g.add_edge("fetch_jobs", "dedupe")
    g.add_edge("dedupe", "enrich")
    g.add_edge("enrich", "prefilter")
    g.add_edge("prefilter", "score")
    g.add_conditional_edges("score", after_score, {"shortlist": "shortlist", "end": END})
    g.add_edge("shortlist", "enrich_shortlisted")
    g.add_edge("enrich_shortlisted", END)
    return g.compile()
