from langchain_core.runnables import RunnableConfig

from app.core.errors import ProviderError
from app.graphs.prep.deps import get_deps
from app.graphs.prep.state import PrepState
from app.services.prep_service import assemble_pack, call_model, directions_link


def run(state: PrepState, config: RunnableConfig) -> PrepState:
    deps = get_deps(config)
    chain = deps.chains.write
    sources = state["pages"] + state["reused_sources"]
    link = directions_link(state.get("origin"), state.get("address"))

    def write():
        return chain.run(
            state["job"], state["sections"], state["raw_text"], state["facts"], sources, link,
            state["contact"],
        )

    draft = None
    for attempt in range(2):  # one retry when the answer is cut off or malformed
        try:
            draft = call_model(deps.budget, chain.llm, chain.model, write, kind="write")
            break
        except ProviderError:
            if attempt == 1:
                raise
    if draft is None:
        raise ProviderError(
            "deep search", "the spending limit for one run was reached before writing the pack"
        )
    pack = assemble_pack(draft, state["facts"], state["dropped"], state["raw_text"], link)
    return {"pack": pack}
