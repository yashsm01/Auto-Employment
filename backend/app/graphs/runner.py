"""Runs a graph in one database transaction and records the outcome in graph_runs."""

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.errors import Conflict
from app.graphs.lead import graph as lead_graph
from app.graphs.lead.state import LeadState
from app.graphs.prep import graph as prep_graph
from app.graphs.resume import graph as resume_graph
from app.repositories import runs_repo

logger = logging.getLogger(__name__)

_GRAPHS = {"lead": lead_graph.build, "resume": resume_graph.build, "prep": prep_graph.build}
_TASK_NOTE = re.compile(r"During task with name '([^']+)'")


@dataclass
class GraphRunResult:
    id: UUID
    status: str
    output: dict[str, Any]
    error: str | None = None


def _failed_node(error: BaseException) -> str | None:
    for note in getattr(error, "__notes__", []):
        match = _TASK_NOTE.search(note)
        if match:
            return match[1]
    return None


def _summarise(state: LeadState) -> dict[str, Any]:
    report = state.get("score_report", {})
    return {
        "fetched": len(state.get("fetched", [])),
        "new_jobs": len(state.get("stored", [])),
        "scored": state.get("scored_count", 0),
        "ai_scored": report.get("ai_scored", 0),
        "keyword_scored": report.get("keyword_scored", 0),
        "input_tokens": report.get("input_tokens", 0),
        "output_tokens": report.get("output_tokens", 0),
        "shortlisted": len(state.get("passed_ids", [])),
        "employers_researched": state.get("employers_researched", 0),
        "errors": state.get("errors", []),
        "sources": state.get("source_report", []),
    }


def _summarise_resume(state: dict[str, Any]) -> dict[str, Any]:
    resume_id = state.get("resume_id")
    return {
        "resume_id": str(resume_id) if resume_id else None,
        "ai_used": state.get("ai_used", False),
        "notes": state.get("notes", []),
    }


def _summarise_prep(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "pack_id": state.get("pack_id"),
        "cost_usd": state.get("cost_usd", 0.0),
        "facts": len(state.get("facts", [])),
        "stopped_by": state.get("stopped_by"),
    }


_SUMMARIES = {"lead": _summarise, "resume": _summarise_resume, "prep": _summarise_prep}


def run_graph(name: str, graph_input: dict[str, Any], deps: Any) -> GraphRunResult:
    """Run a graph. All its writes are rolled back if any step fails."""
    conn = deps.conn
    run_id = runs_repo.start(conn, name, graph_input, graph_input.get("application_id"))
    conn.commit()
    if run_id is None:
        raise Conflict(f"The {name} search is already running")

    try:
        with conn.transaction():
            final = _GRAPHS[name]().invoke(graph_input, config={"configurable": {"deps": deps}})
            output = _SUMMARIES[name](final)
            runs_repo.finish(conn, run_id, output)
    except Exception as error:
        logger.exception("Graph %s failed (run %s)", name, run_id)
        message = f"{type(error).__name__}: {error}"
        runs_repo.fail(conn, run_id, message, _failed_node(error))
        conn.commit()
        return GraphRunResult(id=run_id, status="error", output={}, error=message)

    return GraphRunResult(id=run_id, status="ok", output=output)
