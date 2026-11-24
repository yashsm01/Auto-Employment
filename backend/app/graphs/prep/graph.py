from langgraph.graph import END, StateGraph

from .nodes import check_gaps, explore, extract, gather, load_job, plan, save, write
from .state import PrepState


def build():
    g = StateGraph(PrepState)
    g.add_node("load_job", load_job.run)
    g.add_node("plan", plan.run)
    g.add_node("gather", gather.run)
    g.add_node("extract", extract.run)
    g.add_node("check_gaps", check_gaps.run)
    g.add_node("explore", explore.run)
    g.add_node("write", write.run)
    g.add_node("save", save.run)

    g.set_entry_point("load_job")
    g.add_edge("load_job", "plan")
    g.add_edge("plan", "gather")
    g.add_edge("gather", "extract")
    g.add_edge("extract", "check_gaps")
    g.add_conditional_edges(
        "check_gaps", check_gaps.after_gaps, {"explore": "explore", "write": "write"}
    )
    g.add_edge("explore", "write")
    g.add_edge("write", "save")
    g.add_edge("save", END)
    return g.compile()
