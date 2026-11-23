from app.graphs.lead.state import LeadState
from app.services import lead_service


def run(state: LeadState) -> LeadState:
    return {"queries": lead_service.build_queries(state["resume"], state["prefs"])}
