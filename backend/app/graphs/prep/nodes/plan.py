from langchain_core.runnables import RunnableConfig

from app.core.errors import ProviderError
from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.schemas.prep import PlanResult
from app.services.prep_service import REQUIRED_KINDS, call_model


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    chain = deps.chains.plan
    known = sorted({fact.kind for fact in state["facts"]})
    notes = list(state["notes"])
    try:
        plan = call_model(
            deps.budget,
            chain.llm,
            chain.model,
            lambda: chain.run(state["job"], state["employer"], known),
        )
    except ProviderError as error:
        notes.append(f"Planning failed ({error}), so no web searches were made.")
        plan = None
    if plan is None:
        plan = PlanResult(needs=list(REQUIRED_KINDS))
    needs = [kind for kind in plan.needs if kind not in known]
    return {"plan": plan.model_copy(update={"needs": needs}), "notes": notes}
