from langchain_core.runnables import RunnableConfig

from app.core.errors import ProviderError
from app.graphs.prep.collect import extract_new, place_page, read_page, search_pages
from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.schemas.prep import ExploreStep
from app.services.prep_service import call_model, missing_kinds

RESULTS_PER_SEARCH = 2


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    """Up to 3 extra steps chosen by the model, each carried out by the code."""
    deps = get_deps(config)
    chain = deps.chains.explore
    employer = state["employer"]
    pages = list(state["pages"])
    extracted = list(state["extracted"])
    facts = list(state["facts"])
    dropped = list(state["dropped"])
    notes = list(state["notes"])
    counter = {"places_calls": state["places_calls"]}
    history: list[ExploreStep] = []
    missing = list(state["missing"])

    while missing and deps.budget.allow("explore"):
        try:
            step = call_model(
                deps.budget,
                chain.llm,
                chain.model,
                lambda missing=missing: chain.run(state["job"], missing, pages, history),
            )
        except ProviderError as error:
            notes.append(f"Extra research stopped: {error}")
            break
        if step is None or step.action == "done":
            break
        history.append(step)
        argument = step.argument.strip()
        if step.action == "search":
            search_pages(deps, pages, notes, argument, limit=RESULTS_PER_SEARCH)
        elif step.action == "read":
            read_page(deps, pages, notes, argument, argument, "website")
        elif step.action == "place":
            name, _, town = argument.partition(",")
            place_page(deps, pages, name.strip() or employer, town.strip(), counter)
        extract_new(deps, pages, extracted, facts, dropped, notes, employer)
        missing = missing_kinds(facts, state["plan"].needs)

    return {
        "pages": pages,
        "extracted": extracted,
        "facts": facts,
        "dropped": dropped,
        "notes": notes,
        "places_calls": counter["places_calls"],
        "explore_history": history,
        "missing": missing,
    }
