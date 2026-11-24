from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg
from langchain_core.runnables import RunnableConfig

from app.chains.score_chain import ScoreChain
from app.providers.jobs.base import JobSource
from app.providers.llm.gemini import Embedder
from app.services.enrich_service import EmployerTools


@dataclass
class LeadDeps:
    conn: psycopg.Connection
    sources: Sequence[JobSource]
    score_chain: ScoreChain
    now: datetime
    embedder: Embedder | None = None
    keep_similarity: float = 0.6
    employer_tools: EmployerTools | None = None
    max_employer_profiles: int = 10
    source_notes: list[dict[str, Any]] = field(default_factory=list)


def get_deps(config: RunnableConfig) -> LeadDeps:
    return config["configurable"]["deps"]
