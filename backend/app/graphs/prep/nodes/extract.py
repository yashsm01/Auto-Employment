from langchain_core.runnables import RunnableConfig

from app.graphs.prep.collect import extract_new
from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    pages = list(state["pages"])
    extracted = list(state["extracted"])
    facts = list(state["facts"])
    dropped = list(state["dropped"])
    notes = list(state["notes"])
    extract_new(deps, pages, extracted, facts, dropped, notes, state["employer"])
    return {"extracted": extracted, "facts": facts, "dropped": dropped, "notes": notes}
