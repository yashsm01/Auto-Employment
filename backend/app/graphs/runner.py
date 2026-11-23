"""Runs a graph in one database transaction and records the outcome in graph_runs."""

import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.errors import Conflict
from app.graphs.lead import graph as lead_graph
from app.graphs.lead.deps import LeadDeps
from app.graphs.lead.state import LeadState
from app.repositories import runs_repo

logger = logging.getLogger(__name__)

_GRAPHS = {"lead": lead_graph.build}
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
    return {
        "fetched": len(state.get("fetched", [])),
        "new_jobs": len(state.get("stored", [])),
        "scored": state.get("scored_count", 0),
        "shortlisted": len(state.get("passed_ids", [])),
        "errors": state.get("errors", []),
    }


def run_graph(name: str, graph_input: dict[str, Any], deps: LeadDeps) -> GraphRunResult:
    """Run a graph. All its writes are rolled back if any step fails."""
    conn = deps.conn
    run_id = runs_repo.start(conn, name, graph_input)
    conn.commit()
    if run_id is None:
        raise Conflict(f"The {name} search is already running")

    try:
        with conn.transaction():
            final = _GRAPHS[name]().invoke(graph_input, config={"configurable": {"deps": deps}})
            output = _summarise(final)
            runs_repo.finish(conn, run_id, output)
    except Exception as error:
        logger.exception("Graph %s failed (run %s)", name, run_id)
        message = f"{type(error).__name__}: {error}"
        runs_repo.fail(conn, run_id, message, _failed_node(error))
        conn.commit()
        return GraphRunResult(id=run_id, status="error", output={}, error=message)

    return GraphRunResult(id=run_id, status="ok", output=output)
