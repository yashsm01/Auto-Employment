from typing import Literal

from app.graphs.lead.state import LeadState


def after_score(state: LeadState) -> Literal["shortlist", "end"]:
    return "shortlist" if state.get("passed_ids") else "end"
