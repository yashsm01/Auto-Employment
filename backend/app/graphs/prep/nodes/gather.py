from langchain_core.runnables import RunnableConfig

from app.graphs.prep.collect import new_page, place_page, read_page, search_pages
from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.providers.company.careers import find_careers_link
from app.providers.company.website_reader import is_allowed_url
from app.schemas.prep import PageSource
from app.services.prep_service import is_link

PLACES_SKIPPED_NOTE = "Google Maps was skipped this month to stay within the free amount."


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    employer = state["employer"]
    notes = list(state["notes"])
    counter = {"places_calls": state["places_calls"]}
    pages = [
        PageSource(
            id="s1",
            url=state["job_url"],
            title="Job post",
            kind="job_post",
            text=state["job"].description,
        )
    ]

    extra = (state.get("extra") or "").strip()
    if extra:
        if is_link(extra):
            read_page(deps, pages, notes, extra, "Your link", "user")
        else:
            new_page(pages, url=None, title="Your extra details", kind="user", text=extra)

    job_url = state["job_url"]
    if job_url and is_allowed_url(job_url):
        read_page(deps, pages, notes, job_url, "Job advert page", "website")

    if not state["reused"]:
        website = state["website"]
        if website:
            home = read_page(deps, pages, notes, website, f"{employer} website", "website")
            careers = find_careers_link(home.text, website) if home else None
            if careers and careers.rstrip("/") != website.rstrip("/"):
                read_page(deps, pages, notes, careers, f"{employer} careers page", "website")
        if deps.places is not None and not deps.places_allowed:
            notes.append(PLACES_SKIPPED_NOTE)
        else:
            town = state["job"].location or state.get("origin") or ""
            place_page(deps, pages, employer, town, counter)

    for query in state["plan"].queries:
        if not deps.budget.can("page"):
            deps.budget.allow("page")  # records why the run stopped reading
            break
        search_pages(deps, pages, notes, query)

    return {"pages": pages, "notes": notes, "places_calls": counter["places_calls"]}
