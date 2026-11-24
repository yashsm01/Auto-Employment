from langchain_core.runnables import RunnableConfig

from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.services.prep_service import missing_kinds


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    budget = get_deps(config).budget
    missing = missing_kinds(state["facts"], state["plan"].needs)
    explore_next = bool(missing) and budget.can("explore") and budget.can("model")
    return {"missing": missing, "explore_next": explore_next}


def after_gaps(state: PrepState) -> str:
    return "explore" if state.get("explore_next") else "write"
