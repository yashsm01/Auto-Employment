from langchain_core.runnables import RunnableConfig

from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.repositories import companies_repo, events_repo, prep_repo

FIELD_FOR_KIND = {"about": "about", "news": "recent_news"}
SOURCE_FOR_PAGE = {
    "website": "website",
    "search": "tavily",
    "places": "places",
    "user": "manual",
    "job_post": "job_post",
}


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    conn = deps.conn
    notes = list(state["notes"])
    if deps.budget.stopped_by:
        notes.append(deps.budget.stopped_by)

    pages = {page.id: page for page in state["pages"]}
    if state.get("company_id"):
        # Facts that passed the quote check help resume tailoring too. Reused facts are
        # already stored, so only this run's pages are saved.
        for fact in state["facts"]:
            page = pages.get(fact.source_id)
            field = FIELD_FOR_KIND.get(fact.kind)
            if page is None or field is None:
                continue
            companies_repo.add_fact(
                conn,
                state["company_id"],
                field,
                fact.text,
                SOURCE_FOR_PAGE[page.kind],
                "medium",
                page.url,
            )

    sources = [
        {"id": page.id, "url": page.url, "title": page.title, "kind": page.kind}
        for page in state["pages"] + state["reused_sources"]
    ]
    cost = round(deps.budget.cost_usd, 5)
    prep_repo.finish(
        conn,
        state["pack_id"],
        content=state["pack"].model_dump(),
        sources=sources,
        facts=[fact.model_dump() for fact in state["facts"]],
        notes=notes,
        cost_usd=cost,
        places_calls=state["places_calls"],
    )
    events_repo.add(
        conn,
        "note",
        application_id=state["application_id"],
        company_id=state.get("company_id"),
        payload={"text": "Deep search finished"},
    )
    return {"notes": notes, "cost_usd": cost, "stopped_by": deps.budget.stopped_by}
