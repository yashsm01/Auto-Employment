from langchain_core.runnables import RunnableConfig

from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.schemas.prep import PlanResult
from app.services.prep_service import REQUIRED_KINDS, call_model


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    chain = deps.chains.plan
    known = sorted({fact.kind for fact in state["facts"]})
    plan = call_model(
        deps.budget,
        chain.llm,
        chain.model,
        lambda: chain.run(state["job"], state["employer"], known),
    )
    if plan is None:
        plan = PlanResult(needs=list(REQUIRED_KINDS))
    needs = [kind for kind in plan.needs if kind not in known]
    return {"plan": plan.model_copy(update={"needs": needs})}
